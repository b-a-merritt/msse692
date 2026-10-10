"""Enforce the suite layout without sharing scenario or infrastructure fixtures."""

from pathlib import Path

import pytest


def pytest_sessionstart(session):
    tests = Path(__file__).parent
    for path in tests.rglob("test_*.py"):
        if path.relative_to(tests).parts[0] not in {"unit", "integration"}:
            raise pytest.UsageError("Test modules must live in tests/unit or tests/integration")
