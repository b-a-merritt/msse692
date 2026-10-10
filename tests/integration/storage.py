"""Persist explicitly constructed records without supplying scenario data."""

from normative_conformance.database import write_session


def persist(*, session, record):
    session.add(record)
    session.commit()
    return record


def persist_in_database(*, engine, record):
    with write_session(engine=engine) as session:
        return persist(session=session, record=record)
