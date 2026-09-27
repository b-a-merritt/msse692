from datetime import datetime
from datetime import timezone
from uuid import uuid4

import pytest
from sqlalchemy import event

from normative_conformance.schemas.assessment import CaseSnapshot
from normative_conformance.services.assessment.assess_model import assess_model
from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case
from normative_conformance.services.assessment.get_last_repair import get_last_repair
from normative_conformance.services.assessment.resolve_pending import resolve_pending
from normative_conformance.services.model.get_model import get_model
from normative_conformance.services.model.get_subject_speaker_id import get_subject_speaker_id
from normative_conformance.services.model.list_models import list_models
from normative_conformance.services.observation.get_case_sequence import get_case_sequence


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


@pytest.fixture
def snapshot(*, session):
    def snapshot(*, at=100):
        return CaseSnapshot(
            case_id="case",
            evaluation_id=str(uuid4()),
            through_sequence=get_case_sequence(case_id="case", session=session),
            evaluated_at_us=round(at * 1_000_000),
        )

    return snapshot


@pytest.fixture
def assess_one(*, session, snapshot):
    def assess_one(*, model_id="high_intensity_address", version="1", at=100):
        return assess_model(
            model=get_model(model_id=model_id, version=version, session=session),
            snapshot=snapshot(at=at),
            subject_speaker_id=get_subject_speaker_id(session=session),
            last_repair=get_last_repair(case_id="case", session=session),
            session=session,
        )

    return assess_one


@pytest.fixture
def resolve(*, session, snapshot):
    def resolve(*, pending, at=110):
        return resolve_pending(
            pending=pending,
            model=get_model(
                model_id=pending.model_id, version=pending.model_version, session=session
            ),
            repair_models=[
                model for model in list_models(session=session) if model.type == "repairs"
            ],
            snapshot=snapshot(at=at),
            subject_speaker_id=get_subject_speaker_id(session=session),
            session=session,
        )

    return resolve


@pytest.fixture
def assess(*, engine, scheduler):
    def assess(*, at=100, evaluation_id=None):
        return evaluate_case(
            case_id="case",
            evaluation_id=evaluation_id or uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(at, timezone.utc),
            scheduler=scheduler,
        )

    return assess


@pytest.fixture
def check(*, engine, scheduler):
    def check(*, at=110):
        return check_repairs(
            case_id="case",
            evaluation_id=uuid4(),
            engine=engine,
            now=lambda: datetime.fromtimestamp(at, timezone.utc),
            scheduler=scheduler,
        )

    return check
