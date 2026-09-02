from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    admin_database_url: str = ""
    redis_url: str
    session_ttl_seconds: int = 604800
    session_cookie_secure: bool = False
    session_cookie_name: str = "session"
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
