from __future__ import annotations

from typing import Any

from app.config import Settings

LLM_REQUEST_TIMEOUT_MS = 120_000
LLM_MAX_RETRIES = 0


def build_extraction_llm(settings: Settings) -> Any:
    from langchain_openrouter import ChatOpenRouter

    return ChatOpenRouter(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        temperature=0,
        timeout=LLM_REQUEST_TIMEOUT_MS,
        max_retries=LLM_MAX_RETRIES,
        app_title="Insurance Tracker",
    )
