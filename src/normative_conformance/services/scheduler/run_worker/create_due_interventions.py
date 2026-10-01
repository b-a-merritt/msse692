import logging

from sqlalchemy import Engine

from normative_conformance.database import write_session
from normative_conformance.schemas.internal import Clock
from normative_conformance.services import intervention
from normative_conformance.timestamps import to_microseconds

logger = logging.getLogger(__name__)


def create_due_interventions(
    *,
    intervention_windows: dict[str, int],
    intervention_window_us: int,
    engine: Engine,
    now: Clock,
) -> None:
    current_time_us = to_microseconds(value=now())

    for case_id, opened_at_us in list(intervention_windows.items()):
        if opened_at_us + intervention_window_us > current_time_us:
            continue

        del intervention_windows[case_id]
        try:
            with write_session(engine=engine) as session:
                intervention.create_intervention(
                    case_id=case_id, since_us=opened_at_us, session=session, now=now
                )
        except Exception:
            logger.exception(
                "Intervention creation failed",
                extra={
                    "event": "intervention.failed",
                    "case_id": case_id,
                    "opened_at_us": opened_at_us,
                },
            )
