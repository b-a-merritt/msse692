import logging

from sqlmodel import Session

from normative_conformance.errors import InvalidModel
from normative_conformance.errors import StorageUnavailable
from normative_conformance.schemas.model import ModelVersion
from normative_conformance.services.intervention.constants import INTERVENTION_MESSAGES
from normative_conformance.services.model.evaluate_model import evaluate_model
from normative_conformance.services.model.list_models import list_models

logger = logging.getLogger(__name__)


def validate_models(
    *,
    session: Session,
) -> list[ModelVersion]:
    try:
        models = list_models(session=session)
    except ValueError as error:
        raise InvalidModel("A stored model does not match the model schema") from error

    if not any(model.type == "undesired" for model in models):
        raise InvalidModel("No undesired model is available to assess")

    for model in models:
        if model.type == "undesired" and not any(
            key <= {model.model_id} for key, _ in INTERVENTION_MESSAGES
        ):
            _log_invalid(model=model, rule_id=None)
            raise InvalidModel("An undesired model has no intervention message")

        for rule in model.rules:
            # An empty case still compiles the SQL and binds every parameter.
            try:
                evaluate_model(
                    model=model.model_copy(update={"rules": [rule]}),
                    case_id="",
                    subject_speaker_id="",
                    through_sequence=0,
                    session=session,
                )
            except StorageUnavailable as error:
                _log_invalid(model=model, rule_id=rule.rule_id)
                raise InvalidModel("A stored model rule could not be evaluated") from error

    return models


def _log_invalid(*, model: ModelVersion, rule_id: str | None) -> None:
    logger.error(
        "Model failed validation",
        extra={
            "event": "model.invalid",
            "model_id": model.model_id,
            "version": model.version,
            "rule_id": rule_id,
        },
    )
