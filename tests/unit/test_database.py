import sqlite3
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import call

import pytest
from alembic.util import CommandError
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from normative_conformance import database
from normative_conformance.errors import StorageUnavailable


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


def test_engine_creation_installs_transaction_callbacks_without_connecting(*, monkeypatch):
    mkdir = Mock()
    monkeypatch.setattr(Path, "mkdir", mkdir)
    engine = Mock(spec=Engine)
    create = Mock(return_value=engine)
    listen = Mock()
    monkeypatch.setattr(database, "create_engine", create)
    monkeypatch.setattr(database.event, "listen", listen)
    assert database.create_database_engine(path=Path("example/database.sqlite3")) is engine
    mkdir.assert_called_once_with(parents=True, exist_ok=True)
    assert create.call_args.args[0].database == "example/database.sqlite3"
    assert create.call_args.kwargs == {"connect_args": {"check_same_thread": False}}
    assert listen.call_args_list == [
        call(engine, "connect", database._configure_connection),
        call(engine, "begin", database._begin_transaction),
    ]
    engine.connect.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        None,
        CommandError("Unknown revision"),
        OperationalError("DDL", {}, Exception("Driver failed")),
    ],
)
def test_migrations_join_one_explicit_writer_transaction(*, monkeypatch, failure):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    engine = Mock(spec=Engine)
    engine.connect.return_value.execution_options.return_value = connection
    upgrade = Mock(side_effect=failure)
    monkeypatch.setattr(database.command, "upgrade", upgrade)
    if failure:
        with pytest.raises(
            StorageUnavailable, match=r"^The application database could not be migrated$"
        ) as caught:
            database.initialize_database(engine=engine)
        assert caught.value.__cause__ is failure
    else:
        database.initialize_database(engine=engine)
    engine.connect.return_value.execution_options.assert_called_once_with(
        sqlite_transaction_mode="immediate"
    )
    config, revision = upgrade.call_args.args
    assert revision == "head"
    assert config.attributes["connection"] is connection
    assert config.get_main_option("script_location") == database.MIGRATIONS_LOCATION
    connection.begin.assert_called_once()
    connection.__exit__.assert_called_once()


def test_schema_revision_is_read_from_the_current_connection(*, monkeypatch):
    engine = Mock(spec=Engine)
    connection = object()
    engine.connect.return_value = nullcontext(connection)
    configure = Mock()
    configure.return_value.get_current_revision.return_value = "0001"
    monkeypatch.setattr(database.MigrationContext, "configure", configure)
    assert database.get_schema_revision(engine=engine) == "0001"
    configure.assert_called_once_with(connection)


@pytest.mark.parametrize("write", [False, True])
def test_session_context_closes_on_failure_without_implicitly_committing(*, monkeypatch, write):
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
        (
            database.write_session(engine=engine) if write else database.read_session(engine=engine)
        ) as actual,
    ):
        assert actual is session
        raise failure
    assert caught.value is failure
    session.__exit__.assert_called_once()
    assert session.__exit__.call_args.args[:2] == (ValueError, failure)
    session.commit.assert_not_called()
    if write:
        constructor.assert_called_once_with(bind=connection, expire_on_commit=False)
    else:
        constructor.assert_called_once_with(engine, expire_on_commit=False)
