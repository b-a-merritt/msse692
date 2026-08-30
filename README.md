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
| `uv run pre-commit install` | Arm the git hooks (one time per clone) |
| `uv run pre-commit run --all-files` | Run every hook against the whole repo |
| `uv run pre-commit autoupdate` | Bump hook versions to latest |
