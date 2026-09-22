import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.util import CommandError
from sqlalchemy import URL
from sqlalchemy import Connection
from sqlalchemy import Engine
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session
from sqlmodel import create_engine

from normative_conformance.errors import StorageUnavailable

MIGRATIONS_LOCATION = "normative_conformance:migrations"


def _configure_connection(connection: object, record: object) -> None:
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("The application database requires SQLite.")

    # SQLAlchemy owns transactions, so disable legacy BEGIN behavior
    connection.isolation_level = None

    with connection:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
        finally:
            cursor.close()


def _begin_transaction(connection: Connection) -> None:
    """Keep reads concurrent; migrations and write sessions reserve the writer lock."""
    mode = connection.get_execution_options().get("sqlite_transaction_mode", "deferred")
    connection.exec_driver_sql("BEGIN IMMEDIATE" if mode == "immediate" else "BEGIN")


def create_database_engine(path: Path) -> Engine:
    """Create the shared engine; each request/worker opens its own Session."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(path)),
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _configure_connection)
    event.listen(engine, "begin", _begin_transaction)
    return engine


def _migration_config(connection: Connection) -> Config:
    """Point Alembic at the packaged revisions and the caller's open connection."""
    config = Config()
    config.set_main_option("script_location", MIGRATIONS_LOCATION)
    config.attributes["connection"] = connection
    return config


def initialize_database(engine: Engine) -> None:
    """Apply pending revisions atomically, or reopen a database already at head.

    Alembic treats SQLite DDL as nontransactional and would otherwise commit
    each revision on its own. Beginning here makes the upgrade an external
    transaction that Alembic joins, so a failure rolls back every revision.

    A busy database, an unknown revision, and a failing revision all surface as
    StorageUnavailable; the original error stays attached as the cause.
    """
    try:
        with (
            engine.connect().execution_options(sqlite_transaction_mode="immediate") as connection,
            connection.begin(),
        ):
            command.upgrade(_migration_config(connection), "head")
    except (CommandError, OperationalError) as error:
        raise StorageUnavailable("The application database could not be migrated.") from error


@contextmanager
def write_session(engine: Engine) -> Iterator[Session]:
    """Open a Session whose transactions acquire the SQLite writer lock first.

    The service commits each completed stage. Uncommitted work rolls back on
    exit; closing this context never commits implicitly. Call session.connection()
    before reading the clock when the timestamp must follow writer-lock acquisition.
    """
    with (
        engine.connect().execution_options(sqlite_transaction_mode="immediate") as connection,
        Session(bind=connection, expire_on_commit=False) as session,
    ):
        yield session


@contextmanager
def read_session(engine: Engine) -> Iterator[Session]:
    """Open a read-only Session and reset the pooled connection before returning it."""
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA query_only=ON")
        connection.commit()
        try:
            with Session(bind=connection, expire_on_commit=False) as session:
                yield session
        finally:
            connection.rollback()
            connection.exec_driver_sql("PRAGMA query_only=OFF")
            connection.commit()
