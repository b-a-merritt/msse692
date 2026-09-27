from normative_conformance.services.model.list_models import list_models


def test_seeded_catalog_is_read_from_database(*, session):
    models = list_models(session=session)
    assert {model.model_id for model in models if model.type == "undesired"} == {
        "repeated_interruption",
        "high_intensity_address",
        "extended_turn",
    }
    assert all(model.repairable for model in models if model.type == "undesired")
    assert [(model.model_id, model.repairable) for model in models if model.type == "repairs"] == [
        ("apology", False),
    ]
