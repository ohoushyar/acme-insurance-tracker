from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_int_like(value: object) -> object:
    if isinstance(value, str):
        return int(value)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    admin_database_url: str = ""
    redis_url: str
    dramatiq_redis_url: str = ""
    session_ttl_seconds: int = 604800
    session_cookie_secure: bool = False
    session_cookie_name: str = "session"
    log_level: str = "info"
    s3_endpoint: str = ""
    s3_bucket: str = "insurance-docs"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_tls_seclevel: Annotated[
        Literal[1, 2], BeforeValidator(parse_int_like)
    ] = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
