from datetime import datetime
from datetime import timezone

import pytest

from normative_conformance import models
from normative_conformance.database import write_session
from normative_conformance.services.intervention.create_intervention import create_intervention


def at(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc)


@pytest.fixture
def add_assessment(*, session, add_observation):
    observation = add_observation(start=0, end=1)
    count = 0

    def add_assessment(*, model_id, status="conformant", at=100, case_id="case", sequence=None):
        nonlocal count
        count += 1
        assessment = models.Assessment(
            evaluation_id=f"evaluation-{count}",
            case_id=case_id,
            model_id=model_id,
            model_version="1",
            evaluated_at_us=round(at * 1_000_000),
            through_sequence=sequence or observation.sequence,
            status=status,
            explanation_json="{}",
        )
        session.add(assessment)
        session.commit()
        return assessment

    return add_assessment


@pytest.fixture
def create(*, engine):
    def create(*, since=100, now=102, case_id="case"):
        with write_session(engine=engine) as session:
            return create_intervention(
                case_id=case_id,
                since_us=round(since * 1_000_000),
                session=session,
                now=lambda: at(now),
            )

    return create
