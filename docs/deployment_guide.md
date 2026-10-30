# Deployment guide

Run from the repository root with writable local storage. Environment variables override `.env`; relative paths use the working directory.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `TYPE_SAFE_API_KEY` | Empty | Decision-model credential; required at startup, including for HTTP replays |
| `ASSEMBLY_API_KEY` | Empty | Transcription credential; required for live capture |
| `APP_DB_PATH` | `data/prototype.sqlite3` | SQLite database |
| `LOG_DIR` | `data/logs` | JSONL logs |
| `DECISION_MAX_BATCH_SECONDS` | `60` | Positive speech duration that ends a batch before the target's turn ends |
| `DECISION_MAX_BATCH_TURNS` | `3` | Positive number of turns that ends a batch before the target's turn ends; each turn adds topic questions to the request |
| `DECISION_IDLE_SECONDS` | `20` | Positive time without new speech that ends a batch |
| `DECISION_CONTEXT_SECONDS` | `30` | Nonnegative duration of earlier speech sent as context |
| `DEBUG` | `false` | Framework debug mode |
| `APP_NAME` | `normative-conformance` | Application title |

Use a fresh database path for this disposable schema. Run one process per database; multiple workers sharing storage are unsupported.

```bash
uv sync --locked --no-dev
export APP_DB_PATH=data/research/app.sqlite3
export LOG_DIR=data/research/logs
uv run --no-dev uvicorn normative_conformance.main:app \
  --host 127.0.0.1 --port 8000 --workers 1
```

Startup migrates storage, creates the decision-model client, and starts the worker. A missing decision-model credential stops startup; a missing transcription credential disables capture. Audio goes to the transcription provider; transcripts and context go to the decision-model provider.

## Verify and diagnose

`GET /health/ready` checks the database and worker, not provider availability or assessment completion. Follow the [user guide](user_guide.md) to submit speech and inspect results.

Application logs go to stdout and `$LOG_DIR/<UTC start time>.jsonl`. Filter by `case_id` or `capture_id`. Useful events:

- `capture.audio_forwarded`, `capture.transcript_received`, `capture.observations_stored`: recording progress.
- `capture.speaker_revisions`, `capture.completed`: corrections and successful completion.
- `capture.provider_retry`: a transcription session that failed to open and is being retried.
- `capture.failed`, `case.processing_failed`, `worker.poll_failed`: failures.
- `batch.rejected`: a batch the decision-model provider rejected and the worker skipped.

Application exception records contain type names, not exception messages. Inspect stored assessments for outcomes. See [limitations](known_issues.md) and [API errors](api.md#errors).
