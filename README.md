# normative-conformance

## Useful commands

| Command | What it does |
|---|---|
| `uv sync` | Install/update the venv from `pyproject.toml` + `uv.lock` (dev group included) |
| `uv add <pkg>` | Add a runtime dependency |
| `uv add --group dev <pkg>` | Add a dev-only tool (excluded from production builds) |
| `uv python pin <version>` | Set the project's interpreter (writes `.python-version`) |
| `uv run <cmd>` | Run any command inside the project venv |
| `uv run fastapi dev src/normative_conformance/main.py` | Start the API with hot reload → http://localhost:8000/docs |
| `uv run ruff check .` | Lint everything |
| `uv run ruff check . --fix` | Lint and apply safe auto-fixes |
| `uv run ruff format .` | Format everything (black-compatible) |
| `uv run mypy` | Type-check `src/` in strict mode |
| `uv run pytest` | Run the test suite |
| `uv run alembic history` | List the revisions and their order |
| `uv run pre-commit install` | Arm the git hooks (one time per clone) |
| `uv run pre-commit run --all-files` | Run every hook against the whole repo |
| `uv run pre-commit autoupdate` | Bump hook versions to latest |

## Observation ingestion

Start the API with `uv run fastapi dev src/normative_conformance/main.py`, then
submit an observation through `/docs` or:

```sh
curl -X POST http://localhost:8000/api/v1/observations \
  -H 'Content-Type: application/json' \
  -d '{
    "case_id": "case-1",
    "observation_id": "chunk-1",
    "speaker_id": "subject",
    "start_at": "2026-09-26T09:00:00Z",
    "end_at": "2026-09-26T09:00:01Z",
    "transcript": "Hello",
    "signal_level_min": -50,
    "signal_level_avg": -30,
    "signal_level_max": -10
  }'
```

Submission commits the observation, then queues a case assessment request with a
new evaluation ID. It returns `202 Accepted` with the observation, a UTC
`received_at`, and the next sequence number within its case. A new case is
created automatically. Duplicate observation IDs within a case return `409`;
invalid input returns `422`. Neither requests assessment work.

The queue uses a separate SQLite database under `data/assessment_queue`, configurable
with `ASSESSMENT_QUEUE_PATH`. FastAPI's lifespan opens the queue and starts one
assessment worker thread. Requests for a case already waiting in the queue share
that request. Once evaluation starts, new observations can queue one follow-up.
This coordination assumes one application process.

The worker passes each case and evaluation ID to `assessment.evaluate_case`,
acknowledges successful work, and records evaluation failures without automatically
retrying them. Evaluation runs the database's `undesired` models. A repairable match
creates a pending assessment with a ten-second deadline starting when the match is
detected. Further matches reuse that pending assessment and its original deadline.
The worker queues a separate repair check, then checks again at the deadline if needed.
Nonrepairable matches are confirmed immediately.

Repair checks run the `repairs` models. A qualifying repair appends a non-conformant
resolution; an expired deadline appends a conformant resolution. Both link to the
original row through `resolves_assessment_id`, which can be used only once. Original
assessments remain immutable. Receipt time determines whether repair was timely,
even if the check runs late. Speech order determines the repair boundary. Repair
currently applies to whole observation chunks; phrase order within a chunk is not
represented by the boolean rule results.

The seed migration stores three undesired models and an apology model. On first
startup, `SUBJECT_SPEAKER_ID` (default `subject`) initializes `experiment_config`.
Subsequent evaluations read the subject from that immutable database configuration.
Recognized repairs reset future detection. Finalized positives are retained and
suppressed until repair permits a new occurrence. Intervention services remain stubs.

Shutdown finishes the active request before closing the queue and database.
Waiting requests survive restart and are processed when the worker starts again.
The worker also recovers deadlines for unresolved pending assessments. Recovery
of a request interrupted before it stores any assessment remains unimplemented. Queue read or
acknowledgment failures stop the worker; further submissions return `503 NOT_READY`.

If enqueueing fails after the observation commits, the API returns `503` with
code `ENQUEUE_FAILED` and `error.committed_observation`. The observation remains
stored. Resubmitting that same observation returns `409` and does not retry scheduling.

## Tests

Run `uv run pytest`. Pytest integration tests create a SQLite file under `tmp_path`
for each test and apply the real Alembic migrations, including constraints and
triggers. The application database is never used.
Schema validation tests run without a database. Ingestion tests cover the
service and HTTP endpoint, including duplicates, concurrent writes, and rollback.

## Adding a migration

Until the initial schema is used, edit `0001_initial_schema.py` directly.
Once databases depend on an existing revision, add a new revision for schema changes.

Copy the newest file in `src/normative_conformance/migrations/versions/`, change
its `revision` and `down_revision`, and replace the body. The application applies
pending revisions at startup. `alembic revision` is not wired up: revisions are
written by hand, so the project ships no script template.
