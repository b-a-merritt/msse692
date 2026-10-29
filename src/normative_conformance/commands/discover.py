from normative_conformance.config import get_settings
from normative_conformance.database import create_database_engine
from normative_conformance.database import initialize_database
from normative_conformance.database import read_session
from normative_conformance.database import write_session
from normative_conformance.services.discovery.discover_rules import discover_rules
from normative_conformance.services.discovery.load_traces import load_traces
from normative_conformance.services.discovery.store_model import store_model
from normative_conformance.services.discovery.trace import UNDESIRED_BEHAVIOR
from normative_conformance.timestamps import to_microseconds
from normative_conformance.timestamps import utc_now

NO_MODEL = "Fewer than 3 conversations ended in undesired behavior; no model was stored."


def discover() -> None:
    """Discover a model from the stored conversations and store it as the newest."""
    engine = create_database_engine(path=get_settings().app_db_path)
    try:
        initialize_database(engine=engine)
        with read_session(engine=engine) as session:
            traces = load_traces(session=session)

        # Discovery runs outside the write transaction.
        topics = discover_rules(traces=[case.events for case in traces])
        if topics is None:
            print(NO_MODEL)
            return

        with write_session(engine=engine) as session:
            model = store_model(
                topics=topics,
                assessment_ids=[
                    assessment_id
                    for case in traces
                    if case.events[-1:] == [UNDESIRED_BEHAVIOR]
                    for assessment_id in case.assessment_ids
                ],
                discovered_at_us=to_microseconds(value=utc_now()),
                session=session,
            )
        print(model.model_dump_json(indent=2))
    finally:
        engine.dispose()
