from __future__ import annotations

import ssl
from typing import Any

import httpx

from app.config import Settings

LLM_REQUEST_TIMEOUT_MS = 120_000
LLM_MAX_RETRIES = 0
APP_TITLE = "Insurance Tracker"


def openrouter_ssl_context(*, seclevel: int) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers(f"DEFAULT:@SECLEVEL={seclevel}")
    return ctx


def openrouter_httpx_verify(settings: Settings) -> ssl.SSLContext | bool:
    if settings.openrouter_tls_seclevel == 2:
        return True
    return openrouter_ssl_context(seclevel=settings.openrouter_tls_seclevel)


def build_extraction_llm(settings: Settings) -> Any:
    import openrouter
    from langchain_openrouter import ChatOpenRouter

    verify = openrouter_httpx_verify(settings)
    timeout = httpx.Timeout(LLM_REQUEST_TIMEOUT_MS / 1000)
    headers = {"X-Title": APP_TITLE}
    sdk = openrouter.OpenRouter(
        api_key=settings.openrouter_api_key,
        x_open_router_title=APP_TITLE,
        client=httpx.Client(
            headers=headers,
            follow_redirects=True,
            verify=verify,
            timeout=timeout,
        ),
        async_client=httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            verify=verify,
            timeout=timeout,
        ),
        timeout_ms=LLM_REQUEST_TIMEOUT_MS,
    )
    return ChatOpenRouter(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        temperature=0,
        timeout=LLM_REQUEST_TIMEOUT_MS,
        max_retries=LLM_MAX_RETRIES,
        app_title=APP_TITLE,
        client=sdk,
    )
