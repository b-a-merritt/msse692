# normative-conformance

A research prototype that uses a transcription provider and a decision model to assess conversation. It stores topic scores, target-speaker behavior scores, and action recommendations in SQLite. It does not automatically create interventions.

## Run

From the repository root, install dependencies with `uv sync --locked`. Set the [provider credentials](docs/deployment_guide.md#configuration) in `.env`. Start the app:

```bash
uv run fastapi dev src/normative_conformance/main.py
```

Open [capture](http://127.0.0.1:8000/capture), [API docs](http://127.0.0.1:8000/docs), or [readiness](http://127.0.0.1:8000/health/ready). Use fresh storage for this disposable prototype schema and one server process per database.

## Documentation

- [User guide](docs/user_guide.md): capture, replay, and results.
- [API reference](docs/api.md): endpoints and streaming protocol.
- [Developer guide](docs/developer_guide.md): assessment flow and storage.
- [Deployment](docs/deployment_guide.md): configuration and diagnostics.
- [Commands](docs/commands.md): development checks.
- [Known limitations](docs/known_issues.md).
