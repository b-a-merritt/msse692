"""Formatter branches are observable only through their serialized return value."""

import json
import logging
import sqlite3

from sqlalchemy.exc import OperationalError

from normative_conformance.logging import JsonFormatter


def test_records_are_single_line_json_with_typed_fields():
    record = logging.makeLogRecord(
        {
            "name": "normative_conformance.test",
            "levelname": "INFO",
            "msg": "Fixed message",
            "event": "test.event",
            "case_id": 'case\n{"forged": true}',
            "count": 3,
            "ok": True,
            "created": 0,
        }
    )

    # Serialization and extra-field filtering have no observable state change;
    # inspect the formatter's return value without emitting or capturing logs.
    formatted = JsonFormatter(run_id="test-run").format(record)

    assert len(formatted.splitlines()) == 1
    assert json.loads(formatted) == {
        "timestamp": "1970-01-01T00:00:00.000000Z",
        "level": "INFO",
        "logger": "normative_conformance.test",
        "message": "Fixed message",
        "run_id": "test-run",
        "event": "test.event",
        "case_id": 'case\n{"forged": true}',
        "count": 3,
        "ok": True,
    }


def test_exceptions_are_formatted_by_type_without_messages():
    cause = sqlite3.OperationalError("TRANSCRIPT-MARKER")
    error = OperationalError("SELECT * FROM missing", {"x": "TRANSCRIPT-MARKER"}, cause)
    error.__cause__ = cause
    record = logging.makeLogRecord({"msg": "Failed", "exc_info": (type(error), error, None)})

    # The exception-formatting branch is observable only in the returned JSON.
    formatted = JsonFormatter(run_id="test-run").format(record)

    assert "TRANSCRIPT-MARKER" not in formatted
    assert "SELECT" not in formatted
    assert json.loads(formatted)["exception"] == [
        "sqlalchemy.exc.OperationalError",
        "sqlite3.OperationalError",
    ]


def test_start_and_stop_manage_handlers_without_emitting_logs(*, monkeypatch):
    from datetime import datetime
    from datetime import timezone
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from unittest.mock import Mock
    from unittest.mock import call

    from normative_conformance import logging as module

    directory = MagicMock(spec=Path)
    existing, fresh = Mock(spec=Path), Mock(spec=Path)
    existing.exists.return_value = True
    fresh.exists.return_value = False
    fresh.stem = "20260101T000000000000Z-1"
    directory.__truediv__.side_effect = [existing, fresh]
    timestamp = Mock()
    timestamp.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(module, "datetime", timestamp)
    stdout_handler = Mock(spec=logging.StreamHandler)
    file_handler = Mock(spec=logging.FileHandler)
    application_logger = Mock(spec=logging.Logger)
    access_logger = Mock(spec=logging.Logger)
    logging_api = SimpleNamespace(
        INFO=logging.INFO,
        NOTSET=logging.NOTSET,
        StreamHandler=Mock(return_value=stdout_handler),
        FileHandler=Mock(return_value=file_handler),
        getLogger=Mock(
            side_effect=lambda name: (
                application_logger if name == module.APP_LOGGER else access_logger
            )
        ),
    )
    monkeypatch.setattr(module, "logging", logging_api)
    monkeypatch.setattr(module, "_handlers", [])

    path = module.start_logging(log_dir=directory)

    assert path is fresh
    assert directory.__truediv__.call_args_list == [
        call("20260101T000000000000Z.jsonl"),
        call("20260101T000000000000Z-1.jsonl"),
    ]
    directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    logging_api.FileHandler.assert_called_once_with(fresh, encoding="utf-8")
    assert module._handlers == [stdout_handler, file_handler]
    assert application_logger.propagate is False
    assert access_logger.disabled is True
    formatter = stdout_handler.setFormatter.call_args.args[0]
    assert isinstance(formatter, module.JsonFormatter)
    file_handler.setFormatter.assert_called_once_with(formatter)
    assert formatter.run_id == fresh.stem
    module.stop_logging()
    module.stop_logging()
    assert module._handlers == []
    stdout_handler.close.assert_called_once()
    file_handler.close.assert_called_once()
    assert application_logger.propagate is True
    assert access_logger.disabled is False
