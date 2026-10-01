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
    debug: bool = False
    app_db_path: Path = Path("data/prototype.sqlite3")
    assessment_queue_path: Path = Path("data/assessment_queue")
    log_dir: Path = Path("data/logs")
    subject_speaker_id: str = Field(default="speaker-2", min_length=1, pattern=r"^[^/]+$")
    intervention_window_us: int = Field(default=2_000_000, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
