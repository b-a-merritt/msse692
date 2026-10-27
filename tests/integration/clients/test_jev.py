import json

import httpx2
from typesafe_sdk import RetryPolicy
from typesafe_sdk import TypeSafeClient

from normative_conformance.clients.jev import evaluate
from normative_conformance.schemas.decision import DecisionSnapshot
from normative_conformance.schemas.observation import ObservationInput


def test_sdk_serializes_questions_and_decodes_actual_http_response():
    row = ObservationInput(
        case_id="case",
        observation_id="one",
        speaker_id="A",
        start_at="1970-01-01T00:00:00Z",
        end_at="1970-01-01T00:00:01Z",
        transcript="I apologize",
        signal_level_min=-40,
        signal_level_avg=-30,
        signal_level_max=-20,
    )
    snapshot = DecisionSnapshot(
        case_id="case",
        target_speaker_id="A",
        target_revision=1,
        after_sequence=0,
        through_sequence=1,
        captured_at="1970-01-01T00:01:00Z",
        observations=[row],
        new_observation_ids=["one"],
    )
    requests = []

    def respond(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["authorization"] == "Bearer integration-key"
        payload = json.loads(request.content)
        assert payload["model"] == "jev-1.14.0"
        assert payload["state"]["observations"][0]["transcript"] == "I apologize"
        # All answers are explicit neutral/no-prompt values; only IDs and rubric labels
        # are copied mechanically from the serialized request.
        answers = {}
        for key, question in payload["questions"].items():
            if question["type"] == "noul":
                answers[key] = {"type": "noul", "noul": 0.1}
            elif question["type"] == "choice":
                choice = "remain_silent" if key == "action" else "unknown"
                answers[key] = {
                    "type": "choice",
                    "choice": choice,
                    "confidence": 1.0,
                    "probabilities": {
                        option: 1.0 if option == choice else 0.0 for option in question["criteria"]
                    },
                }
            else:
                assert question["type"] == "score"
                answers[key] = {
                    "type": "score",
                    "score": 0.0,
                    "confidence": 1.0,
                    "legend": {str(i): level for i, level in enumerate(question["criteria"])},
                    "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0, "3": 0.0},
                }
        return httpx2.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": answers,
                "usage": {"input_tokens": 200, "output_tokens": 10},
            },
        )

    with TypeSafeClient(
        api_key="integration-key",
        transport=httpx2.MockTransport(respond),
        base_url="https://api.typesafe.ai",
        compression=False,
        retry=RetryPolicy(max_retries=0),
    ) as client:
        result, _ = evaluate(snapshot=snapshot, client=client)
    assert len(requests) == 1
    assert result.action == "remain_silent"
    assert result.observations[0].primary_topic == "unknown"
    assert set(result.observations[0].behavior_scores.values()) == {0.1}
    assert result.observations[0].intensity == 0.0
