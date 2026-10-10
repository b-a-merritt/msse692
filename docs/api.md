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
| `case_id`, `observation_id`, `speaker_id` | Nonempty strings with no `/`. Observation identity is the case/observation pair |
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

The 202 response repeats these fields and adds `sequence` (1 for a new case) and `received_at` (the server's UTC receipt timestamp). It confirms storage and a scheduling request. Assessment completes asynchronously. The [user walkthrough](user_guide.md) shows the actual response and expected results.

```bash
curl --fail http://127.0.0.1:8000/api/v1/cases/docs-demo/observations
curl --fail http://127.0.0.1:8000/api/v1/cases/docs-demo/assessments
curl --fail http://127.0.0.1:8000/api/v1/models/harm_phrase/versions/1
curl --fail 'http://127.0.0.1:8000/api/v1/interventions?case_id=docs-demo&status=pending'
curl --fail -X POST http://127.0.0.1:8000/api/v1/cases/docs-demo/interventions/deliver
```

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
| 404 `NOT_FOUND` | Model version absent. Check the catalog |
| 409 `OBSERVATION_EXISTS` | Already stored. Read the existing record. No assessment retry is scheduled |
| 503 `NOT_READY` | Worker unavailable/stopping. Check readiness and restart after investigating |
| 503 `STORAGE_UNAVAILABLE` | Database or queue access failed. Inspect service health and storage availability |
| 503 `ENQUEUE_FAILED` | Scheduling failed. On ingestion, `error.committed_observation` contains the stored record. Preserve it. Duplicate submission cannot repair scheduling |
| 422 validation | FastAPI `{"detail":[...]}` response identifies invalid fields. Correct the request |
| 500 unhandled error | Unexpected failure. Inspect records before retrying a state-changing call |

Handled responses carry a server-generated `X-Request-ID` and `Cache-Control: no-store`. Match domain errors by `code`. Validation errors and framework errors, such as an unknown route, do not use the domain envelope.
