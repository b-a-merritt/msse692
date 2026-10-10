"""The migration environment requires and reuses the caller's connection."""

import pytest
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from normative_conformance.database import MIGRATIONS_LOCATION


def test_requires_a_supplied_connection():
    migration_config = Config()
    migration_config.set_main_option("script_location", MIGRATIONS_LOCATION)

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


def test_runs_migrations_in_the_callers_transaction(*, empty_engine):
    # Alembic invokes this callback positionally instead of running revision files.
    migration_config = Config()
    migration_config.set_main_option("script_location", MIGRATIONS_LOCATION)

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
