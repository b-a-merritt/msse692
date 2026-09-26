from datetime import datetime
from datetime import timezone
from uuid import uuid4

import pytest

from normative_conformance.services.assessment.check_repairs import check_repairs
from normative_conformance.services.assessment.evaluate_case import evaluate_case


@pytest.fixture
def assess(*, engine, scheduler):
    def assess(*, at=100):
        return evaluate_case(
            case_id="case",
            evaluation_id=uuid4(),
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
