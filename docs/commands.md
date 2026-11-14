# Useful commands

Run from the repository root. Server startup requires a decision-model credential; see [configuration](deployment_guide.md#configuration).

| Task | Command |
|---|---|
| Install development dependencies | `uv sync --locked` |
| Start development server | `uv run uvicorn conversation_monitor.main:app --reload` |
| Discover a model from the stored conversations | `uv run discover-model` |
| Install commit hooks | `uv run pre-commit install` |
| Unit tests and fresh coverage | `uv run pytest tests/unit --cov=conversation_monitor --cov-report=term-missing --cov-report=html:htmlcov/unit` |
| Integration tests | `uv run pytest tests/integration --no-cov` |
| Combined coverage, after the unit gate passes | `uv run pytest tests/integration --cov=conversation_monitor --cov-append --cov-report=html:htmlcov/combined` |
| JavaScript tests, after `nvm use` | `node --test "tests/unit/static/**/test_*.mjs"` |
| Lint | `uv run ruff check .` |
| Formatting | `uv run ruff format --check .` |
| Types | `uv run mypy` |
| All commit checks | `uv run pre-commit run --all-files` |

Unit coverage must reach 95% independently. Reports are in `htmlcov/unit` and `htmlcov/combined`. See [deployment](deployment_guide.md) for a server without reload and the [user guide](user_guide.md#http-input-and-replay) for replays.
