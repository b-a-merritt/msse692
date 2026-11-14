import sqlite3
from contextlib import nullcontext
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import call

import pytest
from alembic.util import CommandError
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from conversation_monitor import database
from conversation_monitor.errors import StorageUnavailable


def test_connection_configuration_closes_cursor_on_failure():
    connection = MagicMock(spec=sqlite3.Connection)
    cursor = connection.cursor.return_value
    error = sqlite3.OperationalError("Configuration failed")
    cursor.execute.side_effect = [None, None, error]
    with pytest.raises(sqlite3.OperationalError) as caught:
        database._configure_connection(connection, None)
    assert caught.value is error
    assert connection.isolation_level is None
    cursor.close.assert_called_once()


def test_connection_configuration_enables_integrity_and_durable_writes():
    connection = MagicMock(spec=sqlite3.Connection)
    database._configure_connection(connection, None)
    assert connection.cursor.return_value.execute.call_args_list == [
        call("PRAGMA foreign_keys=ON"),
        call("PRAGMA busy_timeout=5000"),
        call("PRAGMA journal_mode=WAL"),
        call("PRAGMA synchronous=FULL"),
    ]
    connection.cursor.return_value.close.assert_called_once()


def test_non_sqlite_connections_are_rejected():
    with pytest.raises(TypeError, match=r"^The application database requires SQLite$"):
        database._configure_connection(object(), None)


@pytest.mark.parametrize(
    "options,statement",
    [({}, "BEGIN"), ({"sqlite_transaction_mode": "immediate"}, "BEGIN IMMEDIATE")],
)
def test_transaction_mode_controls_writer_lock_acquisition(*, options, statement):
    connection = Mock()
    connection.get_execution_options.return_value = options
    database._begin_transaction(connection)
    connection.exec_driver_sql.assert_called_once_with(statement)


@pytest.mark.parametrize(
    "failure",
    [
        CommandError("Unknown revision"),
        OperationalError("DDL", {}, Exception("Driver failed")),
    ],
)
def test_migration_failures_are_reported_as_storage_unavailable(*, monkeypatch, failure):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    engine = Mock(spec=Engine)
    engine.connect.return_value.execution_options.return_value = connection
    monkeypatch.setattr(database.command, "upgrade", Mock(side_effect=failure))

    with pytest.raises(
        StorageUnavailable, match=r"^The application database could not be migrated$"
    ) as caught:
        database.initialize_database(engine=engine)

    assert caught.value.__cause__ is failure
    connection.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "open_session,constructed_with",
    [
        pytest.param(
            database.read_session,
            lambda engine, connection: call(engine, expire_on_commit=False),
            id="read",
        ),
        pytest.param(
            database.write_session,
            lambda engine, connection: call(bind=connection, expire_on_commit=False),
            id="write",
        ),
    ],
)
def test_session_context_closes_on_failure_without_implicitly_committing(
    *, monkeypatch, open_session, constructed_with
):
    engine = Mock(spec=Engine)
    connection = object()
    engine.connect.return_value.execution_options.return_value = nullcontext(connection)
    session = MagicMock(spec=Session)
    session.__enter__.return_value = session
    constructor = Mock(return_value=session)
    monkeypatch.setattr(database, "Session", constructor)
    failure = ValueError("Operation failed")
    with (
        pytest.raises(ValueError) as caught,
        open_session(engine=engine) as actual,
    ):
        assert actual is session
        raise failure
    assert caught.value is failure
    session.__exit__.assert_called_once()
    assert session.__exit__.call_args.args[:2] == (ValueError, failure)
    session.commit.assert_not_called()
    assert constructor.call_args_list == [constructed_with(engine, connection)]
