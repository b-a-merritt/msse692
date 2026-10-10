from normative_conformance.services.model.list_models import list_models


def test_seeded_catalog_is_read_from_database(*, session):
    models = list_models(session=session)
    assert [(model.model_id, model.type, model.repair_allowance_us) for model in models] == [
        ("absolutist_phrase", "undesired", 20_000_000),
        ("agreement_phrase", "repairs", None),
        ("apology", "repairs", None),
        ("character_label", "undesired", 10_000_000),
        ("extended_turn", "undesired", 10_000_000),
        ("harm_phrase", "undesired", None),
        ("high_intensity_address", "undesired", 10_000_000),
        ("intent_disclaimer", "repairs", None),
        ("repeated_interruption", "undesired", 10_000_000),
        ("vulgar_language", "undesired", 10_000_000),
    ]
