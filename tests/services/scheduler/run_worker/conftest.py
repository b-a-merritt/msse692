from datetime import datetime
from datetime import timezone
from threading import Event
from threading import Thread

import pytest

from normative_conformance import models
from normative_conformance.database import write_session
from normative_conformance.services import intervention
from normative_conformance.services.scheduler.run_worker import run_worker


@pytest.fixture
def confirm(*, engine, add_observation):
    observation = add_observation(start=0, end=1)

    def confirm(*, model_id, at, evaluation_id):
        with write_session(engine=engine) as session:
            row = models.Assessment(
                evaluation_id=str(evaluation_id),
                case_id="case",
                model_id=model_id,
                model_version="1",
                evaluated_at_us=round(at * 1_000_000),
                through_sequence=observation.sequence,
                status="conformant",
                explanation_json="{}",
            )
            session.add(row)
            session.commit()
            return row

    return confirm


@pytest.fixture
def run_until(*, scheduler, engine):
    """Run the worker on a settable clock until the test signals completion."""

    def run_until(*, clock, done):
        worker = Thread(
            target=run_worker,
            kwargs={
                "scheduler": scheduler,
                "engine": engine,
                "now": lambda: datetime.fromtimestamp(clock["at"], timezone.utc),
                "intervention_window_us": 2_000_000,
            },
        )
        worker.start()
        try:
            assert done.wait(timeout=5)
        finally:
            scheduler.stopped.set()
            worker.join(timeout=5)
        assert not worker.is_alive()

    return run_until


@pytest.fixture
def record_decisions(*, monkeypatch):
    """Record intervention decisions; the event fires once the expected number is made."""

    def record_decisions(*, count):
        decisions = []
        done = Event()
        original = intervention.create_intervention

        def create_intervention(**kwargs):
            original(**kwargs)
            decisions.append(kwargs["since_us"])
            if len(decisions) == count:
                done.set()

        monkeypatch.setattr(intervention, "create_intervention", create_intervention)
        return decisions, done

    return record_decisions
