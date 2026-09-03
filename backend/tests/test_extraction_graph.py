from unittest.mock import AsyncMock, MagicMock


def _declarations_pages() -> list[str]:
    return [
        (
            "POLICY DECLARATIONS\n"
            "Named Insured: Harbor Cove LLC\n"
            "Premium: $185,000\n"
            "Deductible: Wind/Hail $50,000; All Other Perils $25,000\n"
            "Policy Period: January 1 2024 to January 1 2025\n"
            "Limit of Insurance: $25,000,000\n"
        )
    ]


def _fake_llm(extracted: object) -> MagicMock:
    llm = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=extracted)
    llm.with_structured_output.return_value = structured
    llm._structured = structured
    return llm


async def test_graph_returns_structured_result_for_declarations_text() -> None:
    from app.extraction.graph import run_extraction
    from app.extraction.schema import ExtractedPolicy

    extracted = ExtractedPolicy.model_validate(
        {
            "named_insured": "Harbor Cove LLC",
            "carriers": ["Acme Insurance Company"],
            "deductibles": [
                {"peril": "Wind/Hail", "amount": "50000.00"},
                {"peril": "All Other Perils", "amount": "25000.00"},
            ],
            "locations": [
                {"label": "Building 1", "address": "100 Harbor Cove Drive"},
            ],
            "confidence": {
                "named_insured": 0.95,
                "carriers": 0.9,
                "deductibles": 0.93,
                "locations": 0.87,
            },
        }
    )
    llm = _fake_llm(extracted)

    result = await run_extraction(pages=_declarations_pages(), llm=llm)

    assert result.status == "completed"
    assert result.extracted is not None
    assert result.extracted.named_insured == "Harbor Cove LLC"
    assert len(result.extracted.deductibles) == 2
    assert result.extracted.locations[0].label == "Building 1"
    llm.with_structured_output.assert_called()
    llm._structured.ainvoke.assert_awaited()


async def test_graph_does_not_call_llm_when_text_is_empty() -> None:
    from app.extraction.graph import run_extraction

    llm = MagicMock()

    result = await run_extraction(pages=["", "  \n\t"], llm=llm)

    assert result.status == "failed"
    assert result.error_code == "EXTRACTION_FAILED"
    assert result.extracted is None
    llm.with_structured_output.assert_not_called()
    message = (result.error_message or "").lower()
    assert "scanned" in message or "extractable" in message


async def test_graph_does_not_call_llm_when_pdf_is_corrupt() -> None:
    from app.extraction.graph import run_extraction

    llm = MagicMock()

    result = await run_extraction(pdf_bytes=b"%PDF-1.4\nnot-a-real-pdf", llm=llm)

    assert result.status == "failed"
    assert result.error_code == "EXTRACTION_FAILED"
    assert result.extracted is None
    llm.with_structured_output.assert_not_called()
    message = (result.error_message or "").lower()
    assert "corrupt" in message or "encrypted" in message or "read" in message


async def test_graph_fails_job_when_structured_output_is_invalid() -> None:
    from pydantic import ValidationError

    from app.extraction.graph import run_extraction
    from app.extraction.schema import ExtractedPolicy

    try:
        ExtractedPolicy.model_validate({"effective_date": "not-a-date"})
    except ValidationError as exc:
        invalid = exc
    else:
        raise AssertionError("expected ValidationError")

    llm = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(side_effect=invalid)
    llm.with_structured_output.return_value = structured

    result = await run_extraction(pages=_declarations_pages(), llm=llm)

    assert result.status == "failed"
    assert result.error_code == "EXTRACTION_FAILED"
    assert result.extracted is None
