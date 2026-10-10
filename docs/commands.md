# Useful commands

| Task | Command | Notes |
| --- | --- | --- |
| Install dependencies | `uv sync --locked` | Installs the locked development environment. |
| Run the development server | `uv run fastapi dev src/normative_conformance/main.py` | Open [readiness](http://127.0.0.1:8000/health/ready) or [interactive API docs](http://127.0.0.1:8000/docs). Stop with **Ctrl+C**. |
| Install runtime dependencies | `uv sync --locked --no-dev` | Use for a local research instance without development tools. |
| Run one server process | `uv run --no-dev uvicorn normative_conformance.main:app --host 127.0.0.1 --port 8000 --workers 1` | See the [deployment guide](deployment_guide.md#configuration) for persistent storage paths and configuration. Each instance needs its own database and queue. |
| Run all tests | `uv run pytest` | Runs unit and integration tests. |
| Run unit tests | `uv run pytest tests/unit` | Unit tests must meet the 95% branch and line coverage threshold. |
| Run integration tests | `uv run pytest tests/integration` | Runs the integration suite. |
| Run unit tests with coverage | `uv run pytest tests/unit --cov=normative_conformance --cov-report=term-missing --cov-report=html:htmlcov/unit` | Creates a separate unit coverage report. |
| Append integration coverage | `uv run pytest tests/integration --cov=normative_conformance --cov-append --cov-report=term-missing --cov-report=html:htmlcov/combined` | Run after unit coverage to create the combined report. |
| View coverage reports | Open `htmlcov/unit/index.html` or `htmlcov/combined/index.html` | The first report is unit-only and the second combines unit and integration coverage. |
| Check lint | `uv run ruff check .` |  |
| Check formatting | `uv run ruff format --check .` |  |
| Check types | `uv run mypy` |  |
| Run pre-commit checks | `uv run pre-commit run --all-files` | Install the Git hook once per clone with `uv run pre-commit install`. |
| Replay a case | `uv run python scripts/send_observations.py scripts/cases/case-3.jsonl` | Preserves recorded timing. Each application database fixes its target speaker at first startup, so use fresh storage for an independent replay. See the [case manifest](../scripts/manifest.md). |
