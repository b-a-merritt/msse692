from datetime import datetime
from datetime import timezone
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "normative-conformance"
    debug: bool = False
    app_db_path: Path = Path("data/prototype.sqlite3")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
