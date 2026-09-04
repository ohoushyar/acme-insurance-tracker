import ssl

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+asyncpg://app:app@localhost:5432/insurance_test",
        "redis_url": "redis://localhost:6379/1",
        "openrouter_api_key": "sk-test",
        "openrouter_model": "openai/gpt-4o-mini",
    }
    values.update(overrides)
    return Settings(**values)


def test_build_extraction_llm_sets_http_timeout_and_skips_sdk_retries() -> None:
    from app.extraction.llm import build_extraction_llm

    llm = build_extraction_llm(_settings())

    assert llm.request_timeout == 120_000
    assert llm.max_retries == 0
    assert llm.model_name == "openai/gpt-4o-mini"
    assert llm.temperature == 0


def test_default_tls_seclevel_keeps_full_openssl_verification() -> None:
    from app.extraction.llm import openrouter_httpx_verify

    assert _settings().openrouter_tls_seclevel == 2
    assert openrouter_httpx_verify(_settings()) is True


def test_seclevel_one_still_requires_trusted_certificates() -> None:
    from app.extraction.llm import openrouter_httpx_verify

    verify = openrouter_httpx_verify(_settings(openrouter_tls_seclevel=1))

    assert isinstance(verify, ssl.SSLContext)
    assert verify.verify_mode == ssl.CERT_REQUIRED
    assert verify.check_hostname is True
    assert verify.minimum_version == ssl.TLSVersion.TLSv1_2


def test_tls_seclevel_must_be_1_or_2() -> None:
    with pytest.raises(ValidationError):
        _settings(openrouter_tls_seclevel=0)


def test_tls_seclevel_accepts_configmap_string() -> None:
    settings = _settings(openrouter_tls_seclevel="1")

    assert settings.openrouter_tls_seclevel == 1


def test_build_extraction_llm_wires_seclevel_one_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.extraction.llm as llm_mod

    seen: dict[str, object] = {}
    real_client = httpx.Client
    real_async = httpx.AsyncClient

    def wrap_client(*args: object, **kwargs: object) -> httpx.Client:
        seen["sync"] = kwargs.get("verify", True)
        return real_client(*args, **kwargs)

    def wrap_async(*args: object, **kwargs: object) -> httpx.AsyncClient:
        seen["async"] = kwargs.get("verify", True)
        return real_async(*args, **kwargs)

    monkeypatch.setattr(llm_mod.httpx, "Client", wrap_client)
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", wrap_async)

    llm_mod.build_extraction_llm(_settings(openrouter_tls_seclevel=1))

    assert isinstance(seen["sync"], ssl.SSLContext)
    assert isinstance(seen["async"], ssl.SSLContext)
    assert seen["async"].verify_mode == ssl.CERT_REQUIRED
