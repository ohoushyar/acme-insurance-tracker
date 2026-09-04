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
    assert llm.client.sdk_configuration.timeout_ms == 120_000


def test_default_tls_seclevel_keeps_full_openssl_verification() -> None:
    from app.extraction.llm import openrouter_httpx_verify

    assert _settings().openrouter_tls_seclevel == 2
    assert openrouter_httpx_verify(_settings()) is True


def test_seclevel_one_still_verifies_certificates() -> None:
    from app.extraction.llm import openrouter_httpx_verify

    assert openrouter_httpx_verify(_settings(openrouter_tls_seclevel=1)) is True


def test_ssl_cert_file_is_used_for_verify() -> None:
    from app.extraction.llm import openrouter_httpx_verify

    verify = openrouter_httpx_verify(
        _settings(ssl_cert_file="/etc/ssl/certs/ca-bundle.crt")
    )
    assert verify == "/etc/ssl/certs/ca-bundle.crt"


def test_tls_seclevel_must_be_1_or_2() -> None:
    with pytest.raises(ValidationError):
        _settings(openrouter_tls_seclevel=0)


def test_tls_seclevel_accepts_configmap_string() -> None:
    settings = _settings(openrouter_tls_seclevel="1")

    assert settings.openrouter_tls_seclevel == 1


def test_httpx_client_kwargs_pass_proxy_and_keep_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.extraction.llm as llm_mod

    seen: dict[str, object] = {}
    real_client = httpx.Client
    real_async = httpx.AsyncClient

    def wrap_client(*args: object, **kwargs: object) -> httpx.Client:
        seen["verify"] = kwargs.get("verify", True)
        seen["proxy"] = kwargs.get("proxy")
        seen["timeout"] = kwargs.get("timeout")
        return real_client(*args, **kwargs)

    def wrap_async(*args: object, **kwargs: object) -> httpx.AsyncClient:
        seen["verify"] = kwargs.get("verify", True)
        seen["proxy"] = kwargs.get("proxy")
        seen["timeout"] = kwargs.get("timeout")
        return real_async(*args, **kwargs)

    monkeypatch.setattr(llm_mod.httpx, "Client", wrap_client)
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", wrap_async)

    llm_mod.build_extraction_llm(
        _settings(https_proxy="http://127.0.0.1:8888", openrouter_tls_seclevel=1)
    )

    assert seen["verify"] is True
    assert seen["proxy"] == "http://127.0.0.1:8888"
    timeout = seen["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 10.0
