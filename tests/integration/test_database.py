"""Database initialization, reopening, and migration failure handling."""

from importlib.resources import files
from pathlib import Path
from shutil import copytree
from shutil import ignore_patterns
from textwrap import dedent

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from normative_conformance import database
from normative_conformance.errors import StorageUnavailable
from normative_conformance.models import ConversationCase


def test_reopening_and_reinitializing_preserves_records(*, engine):
    with Session(bind=engine) as session:
        session.add(ConversationCase(case_id="retained", created_at_us=123))
        session.commit()
    engine.dispose()

    reopened = database.create_database_engine(path=Path(engine.url.database))
    try:
        database.initialize_database(engine=reopened)
        database.initialize_database(engine=reopened)
        with Session(bind=reopened) as session:
            case = session.get(ConversationCase, "retained")
            assert case is not None
            assert case.created_at_us == 123
    finally:
        reopened.dispose()


def test_unknown_revision_is_rejected_without_rewriting_it(*, engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = 'unknown'")

    with pytest.raises(StorageUnavailable) as caught:
        database.initialize_database(engine=engine)

    assert str(caught.value) == "The application database could not be migrated"
    assert caught.value.__cause__ is not None
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "unknown"
        )


def _install_failing_migration(*, tmp_path, monkeypatch):
    """Copy the migrations and add one that fails after partial writes."""
    migration_dir = tmp_path / "migrations"
    copytree(
        str(files("normative_conformance") / "migrations"),
        migration_dir,
        ignore=ignore_patterns("__pycache__"),
    )
    (migration_dir / "versions" / "0003_failure.py").write_text(
        dedent("""\
            from alembic import op

            revision = "0003"
            down_revision = "0001"

            def upgrade():
                op.execute("CREATE TABLE partial (id INTEGER PRIMARY KEY)")
                op.execute(
                    "INSERT INTO conversation_case (case_id, created_at_us) VALUES ('partial', 456)"
                )
                op.execute("INSERT INTO missing_table VALUES (1)")

            def downgrade():
                op.execute("DROP TABLE partial")
            """),
        encoding="utf-8",
    )
    monkeypatch.setattr(database, "MIGRATIONS_LOCATION", str(migration_dir))


def test_failed_migration_of_a_fresh_database_leaves_no_tables(
    *, empty_engine, tmp_path, monkeypatch
):
    _install_failing_migration(tmp_path=tmp_path, monkeypatch=monkeypatch)

    with pytest.raises(StorageUnavailable) as caught:
        database.initialize_database(engine=empty_engine)

    assert str(caught.value) == "The application database could not be migrated"
    assert isinstance(caught.value.__cause__, OperationalError)
    assert inspect(empty_engine).get_table_names() == []


def test_failed_migration_of_an_existing_database_keeps_schema_and_data(
    *, empty_engine, tmp_path, monkeypatch
):
    database.initialize_database(engine=empty_engine)
    with empty_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO conversation_case (case_id, created_at_us) VALUES ('retained', 123)"
        )
    original_tables = inspect(empty_engine).get_table_names()
    _install_failing_migration(tmp_path=tmp_path, monkeypatch=monkeypatch)

    with pytest.raises(StorageUnavailable) as caught:
        database.initialize_database(engine=empty_engine)

    assert isinstance(caught.value.__cause__, OperationalError)
    assert inspect(empty_engine).get_table_names() == original_tables
    with empty_engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0001"
        )
        assert connection.exec_driver_sql(
            "SELECT case_id, created_at_us FROM conversation_case"
        ).all() == [("retained", 123)]
