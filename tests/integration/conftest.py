"""Function-scoped storage resources; scenarios belong in each test."""

import pytest
from sqlmodel import Session

from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database


@pytest.fixture
def empty_engine(*, tmp_path):
    engine = create_database_engine(path=tmp_path / "test.sqlite3")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def engine(*, empty_engine):
    initialize_database(engine=empty_engine)
    return empty_engine


@pytest.fixture
def session(*, engine):
    with Session(bind=engine, expire_on_commit=False) as session:
        yield session
