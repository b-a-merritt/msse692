# API reference

Default base URL: `http://127.0.0.1:8000`.

The running application's [Swagger UI](http://127.0.0.1:8000/docs) and [OpenAPI JSON](http://127.0.0.1:8000/openapi.json) expose the field schemas. Download the schema from the version you are using:

```bash
curl --fail http://127.0.0.1:8000/openapi.json -o openapi.json
```

## Endpoints

| Method and path | Input | Success response |
|---|---|---|
| `GET /health/live` | None | 200: `{"status":"live"}` |
| `GET /health/ready` | None | 200: `{"status":"ready"}`. Checks database, queue, worker |
| `PUT /api/v1/cases/{case_id}/target` | Exactly one target order or label | 200: `CaseRecord`; creates the case if absent |
| `GET /api/v1/cases/{case_id}` | Case ID | 200: `CaseRecord`; 404 if absent |
| `POST /api/v1/observations` | `ObservationInput` body | 202: `ObservationRecord` |
| `GET /api/v1/cases/{case_id}/observations` | Case ID | 200: `items` of `ObservationRecord`, newest sequence first |
| `GET /api/v1/cases/{case_id}/assessments` | Case ID | 200: `items` of `Assessment`, increasing assessment ID |
| `GET /api/v1/models` | None | 200: `items` of `ModelVersion` |
| `GET /api/v1/models/{model_id}/versions/{version}` | Model ID and version | 200: one `ModelVersion`. 404 if absent |
| `GET /api/v1/interventions` | Optional `case_id`, `status=pending` or `sent` | 200: `items` of `Intervention`, increasing intervention ID |
| `POST /api/v1/cases/{case_id}/interventions/deliver` | Case ID | 200: `items` of the case's interventions marked sent by this call |

List responses have the form `{"items":[]}` when empty. Unknown case IDs return empty observation/assessment lists. Lists are unpaginated.

## Observation input

All fields are required. Unknown fields are rejected.

| Fields | Format and constraints |
|---|---|
| `case_id`, `observation_id` | Nonempty strings with no `/`. Observation identity is the case/observation pair |
| `speaker_id` | String containing at least one non-whitespace character and no `/` |
| `start_at`, `end_at` | Timezone-aware timestamps. End must follow start. Normalized to UTC |
| `transcript` | String containing at least one non-whitespace character |
| `signal_level_min`, `signal_level_avg`, `signal_level_max` | Finite JSON numbers in dBFS, each between −120 and 0. Min ≤ avg ≤ max |

Run on fresh storage, or choose an unused case ID:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/observations \
  -H 'Content-Type: application/json' \
  -d '{
    "case_id": "docs-demo", "observation_id": "chunk-1",
    "speaker_id": "speaker-2",
    "start_at": "2026-10-10T12:00:00Z", "end_at": "2026-10-10T12:00:04Z",
    "transcript": "I swear to god",
    "signal_level_min": -50, "signal_level_avg": -30, "signal_level_max": -10
  }'
```

The 202 response repeats these fields and adds `sequence` (1 for a new case), `received_at`, and `updated_at`. Receipt and update times are server UTC timestamps and are equal at insertion. It confirms storage and a scheduling request. Assessment completes asynchronously. The [user walkthrough](user_guide.md) shows the actual response and expected results.

```bash
curl --fail http://127.0.0.1:8000/api/v1/cases/docs-demo/observations
curl --fail http://127.0.0.1:8000/api/v1/cases/docs-demo/assessments
curl --fail http://127.0.0.1:8000/api/v1/models/harm_phrase/versions/1
curl --fail 'http://127.0.0.1:8000/api/v1/interventions?case_id=docs-demo&status=pending'
curl --fail -X POST http://127.0.0.1:8000/api/v1/cases/docs-demo/interventions/deliver
```

## Observation records

Observations are append-only and identified by `(case_id, observation_id)`. Duplicate HTTP observation IDs within a case return 409. The API does not expose a correction endpoint.

The server assigns `sequence`, `received_at`, and `updated_at`; POST observation requests cannot supply them. Both timestamps are UTC and equal at insertion. Stored observations cannot be updated or deleted.

## Live capture stream

`GET /capture` serves live transcription. Before opening the stream, create a case with `PUT /api/v1/cases/{case_id}/target` and a body such as `{"target_speaker_order":2}`. The page generates a fresh case ID for each Start and displays it after creation succeeds.

`WS /api/v1/capture/audio?case_id={case_id}` opens a session with the provider for an existing case. The required case ID is a nonempty string without `/`. Missing, invalid, or unknown IDs are rejected during the WebSocket handshake, before opening a provider connection. The case lookup finishes before streaming begins.

After the provider confirms its session, the server sends:

```json
{"type":"ready","case_id":"capture-case-id","sample_rate":16000,"encoding":"pcm_s16le","channels":1,"session_id":"provider-session-id","speech_model":"universal-3-6-pro"}
```

Binary messages contain 1–1600 complete little-endian signed samples (2–3200 bytes). The page sends 100 ms packets and a shorter final packet. The server retains a small tail to keep upstream packets at least 50 ms long, forwarding every sample unchanged without silence padding. A nonempty capture must contain at least 50 ms of audio.

The server measures 20 ms frames across message boundaries. Each `levels` message contains `frames` of `{start_ms, end_ms, dbfs}` with offsets from the first sample. RMS is normalized by 32768, converted with `20 * log10(RMS)`, and clamped to −120 dBFS. The page displays the minimum, maximum, and arithmetic mean of frame dBFS values in the latest update; the average is not computed from pooled linear energy.

Partial turns, finalized turns, and speaker revisions share this outgoing shape:

```json
{
  "type": "transcript", "turn_order": 0, "final": true, "revised": false,
  "transcript": "Hello.", "speaker_id": "A",
  "words": [{"text":"Hello.","start_ms":0,"end_ms":500,"speaker_id":"A"}]
}
```

`turn_order` identifies a turn within the provider session. Repeated updates replace that turn. Corrections have `final: true` and `revised: true`; their word labels replace the prior labels. `speaker_id` is null when the provider has not attributed the speech. The page groups consecutive finalized words by their own labels and displays null attribution as **Unassigned**. A dominant turn label does not fill missing word attribution.

The server saves each finalized turn as observations before sending its `final: true`, `revised: false` message, so receiving that message means the turn is stored. Speaker revisions change only the live messages; saved observations keep the original labels.

Send the exact text `stop` to finish. The server flushes the remaining audio and partial level frame, sends provider `Terminate`, and continues receiving transcripts and revisions until provider `Termination`. Only then does it send `{"type":"stopped"}` and close with code 1000. The provider drain has a ten-second deadline. A connection ending without `stopped` is incomplete.

Capture failures use `{"type":"error","code":"providerAuth","message":"..."}` with fixed application text. Codes are `notConfigured`, `providerAuth`, `providerUnavailable`, `providerProtocol`, `providerTimeout`, `invalidAudio`, `incomplete`, `storageUnavailable`, and `assessmentUnavailable`. A storage failure rolls back the current turn; previously committed turns remain saved. An assessment scheduling failure leaves the current turn saved. Both end capture without `stopped`. Invalid audio closes with code 1008; other capture failures use 1011. These WebSocket errors are separate from the HTTP domain envelope below. The key and raw provider exceptions are never sent to the browser.

## Errors

Domain errors use this envelope. The request ID is unique to the request.

```json
{
  "error": {
    "code": "OBSERVATION_EXISTS",
    "message": "An observation with this identity already exists",
    "request_id": "00000000-0000-4000-8000-000000000001"
  }
}
```

| HTTP / code | Meaning and caller action |
|---|---|
| 404 `NOT_FOUND` | Case or model version absent. Check the requested identity |
| 409 `OBSERVATION_EXISTS` | Already stored. Read the existing record. No assessment retry is scheduled |
| 503 `NOT_READY` | Worker unavailable/stopping. Check readiness and restart after investigating |
| 503 `STORAGE_UNAVAILABLE` | Database or queue access failed. Inspect service health and storage availability |
| 503 `ENQUEUE_FAILED` | Scheduling failed. On ingestion, `error.committed_observation` contains the stored record. Preserve it. Duplicate submission cannot repair scheduling |
| 422 validation | FastAPI `{"detail":[...]}` response identifies invalid fields. Correct the request |
| 500 unhandled error | Unexpected failure. Inspect records before retrying a state-changing call |

Handled responses carry a server-generated `X-Request-ID` and `Cache-Control: no-store`. Match domain errors by `code`. Validation errors and framework errors, such as an unknown route, do not use the domain envelope.
