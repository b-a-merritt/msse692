from datetime import datetime
from datetime import timezone
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "normative-conformance"
    assembly_api_key: str = ""
    type_safe_api_key: str = ""
    debug: bool = False
    app_db_path: Path = Path("data/prototype.sqlite3")
    log_dir: Path = Path("data/logs")
    decision_batch_size: int = Field(default=4, gt=0)
    decision_context_seconds: int = Field(default=30, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
