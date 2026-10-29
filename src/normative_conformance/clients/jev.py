import json

from typesafe_sdk import TypeSafeClient

from normative_conformance.schemas.decision import DecisionAnswers
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.decision import PatternEvidence
from normative_conformance.services.decision.answers import read_answers
from normative_conformance.services.decision.questions import build_questions

MODEL = "jev-1.14.0"


def evaluate(
    *,
    snapshot: DecisionSnapshot,
    evidence: PatternEvidence | None,
    client: TypeSafeClient,
) -> tuple[DecisionAnswers, str]:
    """Ask the decision model about a snapshot and retain the request that was sent.

    Evidence is kept out of the shared state; the request records it beside the questions.
    """
    questions = build_questions(snapshot=snapshot, evidence=evidence)
    state = snapshot.model_dump(mode="json")
    request_json = json.dumps(
        {
            "model": MODEL,
            "state": state,
            "questions": {
                key: question.model_dump(mode="json") for key, question in questions.items()
            },
            "evidence": evidence.model_dump(mode="json") if evidence is not None else None,
        },
        allow_nan=False,
    )
    response = client.system_one(model=MODEL, state=state, questions=questions)
    return read_answers(snapshot=snapshot, questions=questions, response=response), request_json
