from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from typing import Any, TypedDict

import structlog
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.extraction.llm import LLM_REQUEST_TIMEOUT_MS, LLM_TIMEOUT_MESSAGE
from app.extraction.schema import ExtractedPolicy

MIN_TEXT_CHARS = 40
FALLBACK_PAGE_COUNT = 8
PAGE_HIT_THRESHOLD = 1
LLM_INVOKE_TIMEOUT_SECONDS = LLM_REQUEST_TIMEOUT_MS / 1000
log = structlog.get_logger("extraction")
PAGE_KEYWORDS = (
    "declarations",
    "named insured",
    "premium",
    "deductible",
    "policy period",
    "limit of insurance",
)
EXTRACTION_SYSTEM_PROMPT = """You extract commercial property and liability insurance
policy declarations into the given schema.

Rules:
- Return null for any field that is not clearly present. Do not guess.
- Keep every co-insurer in carriers.
- Keep every peril-specific deductible as its own list item.
- Keep every insured location/property as its own list item.
- Money fields are dollar amounts only (no % or currency words). If a
  deductible is written as "2% ($9,620)", store 9620 in amount and keep
  the percent in peril.
- Confidence is 0.0–1.0; use 0 when the value is null.
"""


class ExtractionState(TypedDict, total=False):
    pdf_bytes: bytes | None
    pages: list[str]
    selected_pages: list[str]
    selected_text: str
    extracted: ExtractedPolicy | None
    status: str
    error_code: str | None
    error_message: str | None


@dataclass
class ExtractionOutcome:
    status: str
    extracted: ExtractedPolicy | None = None
    error_code: str | None = None
    error_message: str | None = None


def _score_page(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in PAGE_KEYWORDS if keyword in lowered)


def select_declaration_pages(pages: list[str]) -> list[str]:
    hits = {
        index
        for index, page in enumerate(pages)
        if _score_page(page) >= PAGE_HIT_THRESHOLD
    }
    if not hits:
        return pages[:FALLBACK_PAGE_COUNT]
    with_neighbors: set[int] = set()
    last = len(pages) - 1
    for index in hits:
        with_neighbors.add(index)
        if index > 0:
            with_neighbors.add(index - 1)
        if index < last:
            with_neighbors.add(index + 1)
    return [pages[index] for index in sorted(with_neighbors)]


def pages_from_pdf(pdf_bytes: bytes) -> list[str]:
    reader = PdfReader(BytesIO(pdf_bytes))
    return [(page.extract_text() or "") for page in reader.pages]


def extract_text_node(state: ExtractionState) -> dict[str, Any]:
    if state.get("pages"):
        return {}
    pdf_bytes = state.get("pdf_bytes") or b""
    if not pdf_bytes:
        return {"pages": []}
    try:
        pages = pages_from_pdf(pdf_bytes)
    except PyPdfError:
        return {
            "pages": [],
            "status": "failed",
            "error_code": "EXTRACTION_FAILED",
            "error_message": (
                "This PDF could not be read. It may be corrupt or encrypted."
            ),
            "extracted": None,
        }
    return {"pages": pages}


def select_pages_node(state: ExtractionState) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    pages = state.get("pages") or []
    selected = select_declaration_pages(pages)
    selected_text = "\n\n".join(selected)
    if len(selected_text.strip()) < MIN_TEXT_CHARS:
        return {
            "selected_pages": selected,
            "selected_text": selected_text,
            "status": "failed",
            "error_code": "EXTRACTION_FAILED",
            "error_message": (
                "This document looks scanned or has no extractable text."
            ),
            "extracted": None,
        }
    return {
        "selected_pages": selected,
        "selected_text": selected_text,
        "status": "processing",
        "error_code": None,
        "error_message": None,
    }


async def extract_fields_node(
    state: ExtractionState, config: RunnableConfig
) -> dict[str, Any]:
    if state.get("status") == "failed":
        return {}
    llm = config["configurable"]["llm"]
    structured = llm.with_structured_output(ExtractedPolicy)
    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=state["selected_text"]),
    ]
    try:
        log.info(
            "extraction_llm_invoke",
            selected_chars=len(state.get("selected_text") or ""),
        )
        extracted = await asyncio.wait_for(
            asyncio.to_thread(structured.invoke, messages),
            timeout=LLM_INVOKE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        log.warning("extraction_llm_timeout")
        return {
            "extracted": None,
            "status": "failed",
            "error_code": "EXTRACTION_FAILED",
            "error_message": LLM_TIMEOUT_MESSAGE,
        }
    except (ValidationError, OutputParserException):
        return {
            "extracted": None,
            "status": "failed",
            "error_code": "EXTRACTION_FAILED",
            "error_message": (
                "Extraction returned values that could not be read. "
                "Try uploading the document again."
            ),
        }
    log.info("extraction_llm_finished")
    return {"extracted": extracted, "status": "completed"}


def _route_after_select(state: ExtractionState) -> str:
    if state.get("status") == "failed":
        return "failed"
    return "extract"


def build_extraction_graph() -> Any:
    graph = StateGraph(ExtractionState)
    graph.add_node("extract_text", extract_text_node)
    graph.add_node("select_pages", select_pages_node)
    graph.add_node("extract_fields", extract_fields_node)
    graph.add_edge(START, "extract_text")
    graph.add_edge("extract_text", "select_pages")
    graph.add_conditional_edges(
        "select_pages",
        _route_after_select,
        {"failed": END, "extract": "extract_fields"},
    )
    graph.add_edge("extract_fields", END)
    return graph.compile()


_GRAPH = None


def _graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_extraction_graph()
    return _GRAPH


async def run_extraction(
    *,
    pages: list[str] | None = None,
    pdf_bytes: bytes | None = None,
    llm: Any = None,
) -> ExtractionOutcome:
    result = await _graph().ainvoke(
        {"pages": pages or [], "pdf_bytes": pdf_bytes, "extracted": None},
        {"configurable": {"llm": llm}},
    )
    return ExtractionOutcome(
        status=result.get("status") or "failed",
        extracted=result.get("extracted"),
        error_code=result.get("error_code"),
        error_message=result.get("error_message"),
    )
