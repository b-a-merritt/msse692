"""The migration environment requires and reuses the caller's connection."""

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from normative_conformance.database import MIGRATIONS_LOCATION


@pytest.fixture
def migration_config():
    config = Config()
    config.set_main_option("script_location", MIGRATIONS_LOCATION)
    return config


def test_requires_a_supplied_connection(*, migration_config):
    scripts = ScriptDirectory.from_config(migration_config)
    with (
        EnvironmentContext(config=migration_config, script=scripts),
        pytest.raises(RuntimeError) as caught,
    ):
        scripts.run_env()

    assert str(caught.value) == (
        "Migrations run through normative_conformance.database.initialize_database, "
        "which the application calls at startup. Use alembic to list revisions"
    )


def test_runs_migrations_in_the_callers_transaction(*, empty_engine, migration_config):
    # Alembic invokes this callback positionally instead of running revision files.
    def migrate(revision, context):
        assert context.connection is connection
        context.execute("CREATE TABLE env_probe (id INTEGER PRIMARY KEY)")
        context.execute("INSERT INTO env_probe VALUES (1)")
        return []

    scripts = ScriptDirectory.from_config(migration_config)
    with empty_engine.connect() as connection, connection.begin() as transaction:
        migration_config.attributes["connection"] = connection
        with EnvironmentContext(config=migration_config, script=scripts, fn=migrate):
            scripts.run_env()

        assert connection.exec_driver_sql("SELECT id FROM env_probe").scalar_one() == 1
        transaction.rollback()

    assert not inspect(empty_engine).has_table("env_probe")


def test_upgrade_preserves_model_policy_and_existing_pending_deadlines(
    *, empty_engine, migration_config
):
    with empty_engine.connect() as connection, connection.begin():
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "0002")
        connection.exec_driver_sql("""
            INSERT INTO normative_model_version
                (model_id, name, version, type, repairable, rules_json, parameters_json)
            VALUES ('immediate', 'Immediate', '1', 'undesired', 0, '[]', '{}')
        """)
        connection.exec_driver_sql("INSERT INTO case_log VALUES ('case', 0)")
        connection.exec_driver_sql("""
            INSERT INTO observation VALUES
                ('case', 'chunk', 1, 0, 'subject', 0, 31000000, 'hello', -60, -30, 0)
        """)
        connection.exec_driver_sql("""
            INSERT INTO assessment
                (evaluation_id, case_id, model_id, model_version, evaluated_at_us,
                 through_sequence, status, explanation_json, next_due_at_us)
            VALUES ('original', 'case', 'extended_turn', '1', 100000000,
                    1, 'pending', '{}', 110000000)
        """)
        models_before = (
            connection.exec_driver_sql(
                "SELECT * FROM normative_model_version ORDER BY model_id, version"
            )
            .mappings()
            .all()
        )
        assessments_before = connection.exec_driver_sql("SELECT * FROM assessment").all()

        command.upgrade(migration_config, "head")

        expected_models = []
        for row in models_before:
            expected = dict(row)
            expected["repair_allowance_us"] = 10_000_000 if expected.pop("repairable") else None
            expected_models.append(expected)
        models_after = (
            connection.exec_driver_sql(
                "SELECT * FROM normative_model_version ORDER BY model_id, version"
            )
            .mappings()
            .all()
        )
        assert models_after == expected_models
        assert connection.exec_driver_sql("SELECT * FROM assessment").all() == assessments_before
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        with pytest.raises(IntegrityError, match="model version is immutable"):
            connection.exec_driver_sql("""
                UPDATE normative_model_version SET repair_allowance_us = 5000000
                WHERE model_id = 'extended_turn'
            """)
