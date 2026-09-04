from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import Settings

LLM_REQUEST_TIMEOUT_MS = 120_000
LLM_MAX_RETRIES = 0
LLM_TIMEOUT_MESSAGE = "The extraction service did not respond in time. Try again."
APP_TITLE = "Insurance Tracker"
OPENROUTER_PROBE_URL = "https://openrouter.ai/api/v1/models"

log = structlog.get_logger("extraction")


def openrouter_httpx_verify(settings: Settings) -> bool | str:
    if settings.ssl_cert_file:
        return settings.ssl_cert_file
    return True


def httpx_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=10.0,
        read=LLM_REQUEST_TIMEOUT_MS / 1000,
        write=30.0,
        pool=5.0,
    )


def httpx_client_kwargs(
    settings: Settings, timeout: httpx.Timeout | None = None
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "follow_redirects": True,
        "verify": openrouter_httpx_verify(settings),
        "timeout": timeout or httpx_timeout(),
        "trust_env": True,
    }
    proxy = settings.https_proxy or settings.http_proxy
    if proxy:
        kwargs["proxy"] = proxy
    return kwargs


def probe_openrouter(settings: Settings) -> None:
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
    try:
        with httpx.Client(**httpx_client_kwargs(settings, timeout)) as client:
            response = client.get(OPENROUTER_PROBE_URL)
            log.info("openrouter_probe_ok", status_code=response.status_code)
    except (httpx.HTTPError, OSError) as exc:
        log.warning(
            "openrouter_probe_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:400],
        )


def build_extraction_llm(settings: Settings) -> Any:
    import openrouter
    from langchain_openrouter import ChatOpenRouter

    timeout = httpx_timeout()
    kwargs = httpx_client_kwargs(settings, timeout)
    headers = {"X-Title": APP_TITLE}
    sdk = openrouter.OpenRouter(
        api_key=settings.openrouter_api_key,
        x_open_router_title=APP_TITLE,
        client=httpx.Client(headers=headers, **kwargs),
        async_client=httpx.AsyncClient(headers=headers, **kwargs),
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
