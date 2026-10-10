import pytest
from sqlalchemy import event


@pytest.fixture
def subject_config_reads(*, engine):
    reads = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if "FROM experiment_config" in statement:
            reads.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield reads
    finally:
        event.remove(engine, "before_cursor_execute", record)
