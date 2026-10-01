"""Application records are single-line JSON written identically to stdout and the run file."""

import json
import logging
from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from normative_conformance.logging import APP_LOGGER
from normative_conformance.logging import start_logging
from normative_conformance.logging import stop_logging

logger = logging.getLogger("normative_conformance.test")


@pytest.fixture
def start(*, tmp_path):
    """Start inside the test body: pytest replaces sys.stdout between setup and call."""
    try:
        yield lambda: start_logging(log_dir=tmp_path / "logs")
    finally:
        stop_logging()


def read_lines(*, path):
    return path.read_text(encoding="utf-8").splitlines()


def test_records_are_identical_single_line_json_with_typed_fields(*, start, capsys):
    run = start()
    logger.info(
        "Fixed message",
        extra={
            "event": "test.event",
            "case_id": 'case\n{"forged": true}',
            "count": 3,
            "ok": True,
        },
    )

    file_lines = read_lines(path=run)
    assert capsys.readouterr().out.splitlines() == file_lines
    assert len(file_lines) == 1
    record = json.loads(file_lines[0])
    assert record["message"] == "Fixed message"
    assert record["event"] == "test.event"
    assert record["run_id"] == run.stem
    assert record["level"] == "INFO"
    assert record["logger"] == "normative_conformance.test"
    assert record["timestamp"].endswith("Z")
    assert record["case_id"] == 'case\n{"forged": true}'
    assert record["count"] == 3
    assert record["ok"] is True


def test_exceptions_are_logged_by_type_without_messages(*, start, engine):
    run = start()
    marker = "TRANSCRIPT-MARKER"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT * FROM missing WHERE x = :x"), {"x": marker})
    except SQLAlchemyError:
        logger.exception("Failed", extra={"event": "test.failed"})

    content = run.read_text(encoding="utf-8")
    assert marker not in content
    assert json.loads(content)["exception"] == [
        "sqlalchemy.exc.OperationalError",
        "sqlite3.OperationalError",
    ]


def test_existing_file_gets_a_suffix_and_restarts_do_not_duplicate_handlers(
    *, tmp_path, monkeypatch
):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 1, 12, tzinfo=timezone.utc)

    monkeypatch.setattr("normative_conformance.logging.datetime", FixedDatetime)
    first = start_logging(log_dir=tmp_path)
    stop_logging()
    second = start_logging(log_dir=tmp_path)
    try:
        assert len(logging.getLogger(APP_LOGGER).handlers) == 2
        logger.info("Once", extra={"event": "test.once"})
    finally:
        stop_logging()

    assert first.name == "20261001T120000000000Z.jsonl"
    assert second.name == "20261001T120000000000Z-1.jsonl"
    assert read_lines(path=first) == []
    assert len(read_lines(path=second)) == 1
    assert logging.getLogger(APP_LOGGER).handlers == []
    assert logging.getLogger(APP_LOGGER).propagate
