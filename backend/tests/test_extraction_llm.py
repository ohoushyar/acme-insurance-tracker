from app.config import Settings


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://app:app@localhost:5432/insurance_test",
        redis_url="redis://localhost:6379/1",
        openrouter_api_key="sk-test",
        openrouter_model="openai/gpt-4o-mini",
    )


def test_build_extraction_llm_sets_http_timeout_and_skips_sdk_retries() -> None:
    from app.extraction.llm import build_extraction_llm

    llm = build_extraction_llm(_settings())

    assert llm.request_timeout == 120_000
    assert llm.max_retries == 0
    assert llm.model_name == "openai/gpt-4o-mini"
    assert llm.temperature == 0
