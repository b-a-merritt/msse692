# API reference

Base URL: `http://127.0.0.1:8000`. Full field schemas: [Swagger UI](http://127.0.0.1:8000/docs) and [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

## Endpoints

| Method and path | Result |
|---|---|
| `GET /health/live` | 200: `{"status":"live"}` |
| `GET /health/ready` | 200: `{"status":"ready"}`; checks database and worker |
| `PUT /api/v1/cases/{case_id}/target` | 200: `CaseRecord`; creates the case if absent |
| `GET /api/v1/cases/{case_id}` | 200: `CaseRecord`; 404 if absent |
| `POST /api/v1/observations` | 201: `ObservationRecord` |
| `GET /api/v1/cases/{case_id}/observations` | Ingested observations, newest sequence first |
| `GET /api/v1/cases/{case_id}/assessments` | Assessments, increasing assessment ID |
| `GET /api/v1/interventions` | Interventions, increasing ID; optional `case_id` and `status=pending` or `sent` |
| `POST /api/v1/cases/{case_id}/interventions/deliver` | Marks eligible interventions sent once and returns them |

List endpoints return 200 with `{"items":[...]}`; unknown cases have empty lists. Lists are unpaginated.

## Targets

PUT accepts exactly one of `{"target_speaker_order":1}` (1 or 2) or `{"target_speaker_id":"A"}`. Speaking order uses distinct resolved labels in ingested speech; `PENDING` does not count. A label selection clears the order. A changed target label increments `target_revision` and makes stored speech eligible for assessment.

`CaseRecord` includes the speaking order, the resolved `target_speaker_id`, and `target_revision`. A speaker selected by label has no speaking order.

## Observation input

All fields are required; unknown fields are rejected. See the [submission example](user_guide.md#http-input-and-replay).

| Fields | Constraints |
|---|---|
| `case_id`, `observation_id` | Nonempty strings without `/`; ingested identity is the case/observation pair |
| `speaker_id` | Nonblank string without `/` |
| `start_at`, `end_at` | Aware timestamps, normalized to UTC; end follows start |
| `transcript` | Nonblank string |
| `signal_level_min`, `signal_level_avg`, `signal_level_max` | Finite dBFS values between −120 and 0; min ≤ avg ≤ max |

The response adds server-assigned `sequence` and `received_at`. **201 confirms storage, not completed inference.** Duplicate ingested IDs return 409. Original observations are immutable. There is no HTTP correction endpoint.

## Assessments and interventions

Assessments include the model and prompt version, target revision and `target_speaker_id`, sequence range `(after_sequence, through_sequence]`, evaluation/completion times, classifications, and action probabilities. Classifications contain observation IDs, topic/behavior scores, selected labels, primary topic, and target-only intensity (0–3).

Scores meeting the stored `selection_threshold` are selected in name order. A primary topic outside that set is reported as `unknown`. Actions are `remain_silent`, `await_context`, `reflect_later`, or `intervene`. They do not create interventions automatically. A batch without new target speech has a null `action` and `action_confidence` and empty `action_probabilities`.

The intervention endpoints operate on existing records. Each has one source `assessment_id` and the `target_speaker_id` it addresses. Delivery requires the current target revision, sets `sent_at` once, and sends no external notification. An unfiltered listing retains unsent records for earlier targets; `status=pending` excludes them.

## Live capture stream

`GET /capture` serves the microphone page. Create a case before connecting to `WS /api/v1/capture/audio?case_id={case_id}`. Missing, invalid, or unknown IDs are rejected during the handshake.

The server confirms the provider session with:

```json
{"type":"ready","case_id":"case","sample_rate":16000,"encoding":"pcm_s16le","channels":1,"session_id":"provider-session","speech_model":"provider-model"}
```

Send binary PCM16: 1–1600 complete little-endian mono samples per message. Capture must contain at least 50 ms of audio. The page sends 100 ms packets and a final tail. `levels` messages contain `frames` of `{start_ms,end_ms,dbfs}` in 20 ms intervals; offsets start at the first sample. Displayed average level is the arithmetic mean of frame dBFS values.

Transcript messages have this shape:

```json
{"type":"transcript","turn_order":0,"final":true,"revised":false,"transcript":"Hello.","speaker_id":"A","words":[{"text":"Hello.","start_ms":0,"end_ms":500,"speaker_id":"A"}]}
```

A turn's first final is saved before its message is sent; later finals are ignored. Partial updates and revisions use the same turn order. Speaker IDs can be null for unattributed speech. Revisions are saved before `revised:true` messages. They do not change original observations, targets, or existing assessments, and do not trigger reassessment. Revised records are not exposed over HTTP.

Send exact text `stop`. The server drains final provider events, then sends `{"type":"stopped"}` and closes with code 1000. The drain timeout is ten seconds. Closing without `stopped` means incomplete capture.

Failures send `{"type":"error","code":"providerAuth","message":"..."}`. Codes: `notConfigured`, `providerAuth`, `providerUnavailable`, `providerProtocol`, `providerTimeout`, `invalidAudio`, `incomplete`, `storageUnavailable`. Invalid audio closes with 1008; other failures use 1011. Committed speech survives a later failure.

## Errors

HTTP domain errors use `{"error":{"code":"NOT_FOUND","message":"...","request_id":"..."}}`.

| HTTP / code | Meaning |
|---|---|
| 404 `NOT_FOUND` | Case absent |
| 409 `OBSERVATION_EXISTS` | Ingested identity already stored |
| 503 `NOT_READY` | Database or worker unavailable |
| 503 `STORAGE_UNAVAILABLE` | Storage operation failed |
| 422 | Framework `detail` describes invalid input |
| 500 | Unexpected failure; inspect records before retrying a write |

Handled responses carry `X-Request-ID` and `Cache-Control: no-store`. Validation errors and unknown routes do not use the domain envelope.
