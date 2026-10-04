"""JSON Lines application logs, written to stdout and one file per run."""

import json
import logging
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path

APP_LOGGER = "normative_conformance"
UVICORN_ACCESS_LOGGER = "uvicorn.access"
_STANDARD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {"message"}
_handlers: list[logging.Handler] = []


def _exception_types(*, error: BaseException | None) -> list[str]:
    """Name each exception in the chain; messages can embed SQL parameters and transcripts."""
    types: list[str] = []
    while error is not None and len(types) < 10:
        types.append(f"{type(error).__module__}.{type(error).__qualname__}")
        error = error.__cause__ or error.__context__
    return types


class JsonFormatter(logging.Formatter):
    def __init__(self, *, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": self.run_id,
        }
        entry.update(
            (key, value) for key, value in record.__dict__.items() if key not in _STANDARD_FIELDS
        )
        if record.exc_info:
            entry["exception"] = _exception_types(error=record.exc_info[1])
        # json.dumps escapes newlines, so every record stays on one line.
        return json.dumps(entry, default=str)


def start_logging(*, log_dir: Path) -> Path:
    """Send application records to stdout and a new file named for the UTC start time."""
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = log_dir / f"{stamp}.jsonl"
    suffix = 0
    while path.exists():
        suffix += 1
        path = log_dir / f"{stamp}-{suffix}.jsonl"

    formatter = JsonFormatter(run_id=path.stem)
    logger = logging.getLogger(APP_LOGGER)
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(path, encoding="utf-8")):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        _handlers.append(handler)
    logger.setLevel(logging.INFO)
    # Server logging configuration must not print each record a second time.
    logger.propagate = False
    # The request middleware logs each request as JSON, so uvicorn's text line is redundant.
    logging.getLogger(UVICORN_ACCESS_LOGGER).disabled = True
    return path


def stop_logging() -> None:
    """Remove and close only the handlers start_logging attached."""
    logger = logging.getLogger(APP_LOGGER)
    while _handlers:
        handler = _handlers.pop()
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    logging.getLogger(UVICORN_ACCESS_LOGGER).disabled = False
