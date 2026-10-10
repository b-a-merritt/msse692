"""Logging startup selects a fresh file and owns its handlers until shutdown."""

import logging
import sys
from datetime import datetime
from datetime import timezone

from normative_conformance.logging import APP_LOGGER
from normative_conformance.logging import UVICORN_ACCESS_LOGGER
from normative_conformance.logging import JsonFormatter
from normative_conformance.logging import start_logging
from normative_conformance.logging import stop_logging


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
        handlers = logging.getLogger(APP_LOGGER).handlers
        assert len(handlers) == 2
        stdout_handler, file_handler = handlers
        assert stdout_handler.stream is sys.stdout
        assert file_handler.baseFilename == str(second)
        assert stdout_handler.formatter is file_handler.formatter
        assert isinstance(file_handler.formatter, JsonFormatter)
        assert file_handler.formatter.run_id == second.stem
        assert not logging.getLogger(APP_LOGGER).propagate
        assert logging.getLogger(UVICORN_ACCESS_LOGGER).disabled
    finally:
        stop_logging()

    assert first.name == "20261001T120000000000Z.jsonl"
    assert second.name == "20261001T120000000000Z-1.jsonl"
    assert first.is_file()
    assert second.is_file()
    assert file_handler.stream is None
    assert logging.getLogger(APP_LOGGER).handlers == []
    assert logging.getLogger(APP_LOGGER).propagate
    assert not logging.getLogger(UVICORN_ACCESS_LOGGER).disabled
