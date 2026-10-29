"""The command migrates a real database and reports when there is too little to discover from."""

from importlib import import_module

from sqlalchemy import inspect

from normative_conformance.config import Settings
from normative_conformance.database import create_database_engine

module = import_module("normative_conformance.commands.discover")


def test_empty_database_is_migrated_and_stores_no_model(*, monkeypatch, tmp_path, capsys):
    path = tmp_path / "discover.sqlite3"
    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None, app_db_path=path))

    module.discover()

    assert capsys.readouterr().out == (
        "Fewer than 3 conversations ended in undesired behavior; no model was stored.\n"
    )
    engine = create_database_engine(path=path)
    try:
        assert "normative_model" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
