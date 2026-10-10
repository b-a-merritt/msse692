# AGENTS.md

Conventions for this repository. Each rule states what to do and why it exists;
add one when a review or a bug shows that it is missing.

## Mirror source directories in tests

Organize tests relative to `tests/unit/` or `tests/integration/` the same way code
is organized relative to `src/normative_conformance/`. Name test modules
`test_<source_module>.py`, such as `tests/unit/schemas/test_observation.py` and
`tests/integration/models/test_observation.py`. For migrations, test
`tests/integration/migrations/test_env.py`; do not add tests for individual files
in `migrations/versions/`.

**Why:** Matching paths make the tests for each source module easy to find.

## Separate unit tests from integration tests

Put isolated behavior tests in `tests/unit/`. Use in-memory inputs and test
doubles; do not use real databases (including in-memory SQLite), persistent
queues, filesystem I/O, network calls, application HTTP clients, or background
workers. Put tests exercising those interactions in `tests/integration/`.
Classify the entire execution, including fixture dependencies. A mock in a test
does not make it a unit test. Split mixed modules between the two trees.

Directory placement determines the suite; do not duplicate it with markers.
Do not put test modules elsewhere or import between suites. Keep integration
fixtures inside the integration tree, never in the root `tests/conftest.py`.

**Why:** Each suite must run independently with a clear dependency boundary.

## Keep test inputs visible

Spell out scenario data and behavior-relevant values in the test. A reader must
be able to connect setup to assertions without following fixture chains or
opening external data files. Prefer inline setup and a little duplication to
hidden defaults. Small helpers may handle mechanical persistence or resource
cleanup, but must receive explicit records and relevant inputs; they must not
silently create related records or choose a scenario.

Keep `conftest.py` files lean and fixtures few, primarily for infrastructure
creation and cleanup. Put shared infrastructure fixtures at their nearest common
parent within the integration suite. Invoke the operation under test directly,
not through a fixture. Do not import helpers from `conftest.py`.

**Why:** Hidden setup is a
[mystery guest](https://thoughtbot.com/blog/mystery-guest): it obscures the cause
and effect that a test should document.

## Prefer behavioral assertions over log assertions

Assert results, exceptions, state changes, and observable effects. Heavily prefer
not to test log output. Only assert it when there is no other way to test the
branch, and explain that exception beside the test. Do not use log messages as
evidence that a service or worker handled an error when its behavior is observable.

**Why:** Log wording is incidental to most behavior and makes tests brittle.

## Enforce high coverage from unit tests alone

Use `pytest-cov` and coverage.py with branch measurement enabled. Enforce the
configured 95% minimum on the unit suite independently, starting with fresh
coverage data. Integration coverage must not be used to satisfy the unit gate.
Keep unit and combined HTML reports separate. Do not lower the threshold or
exclude application code to pass a test refactor.

**Why:** Coverage identifies untested paths while behavioral assertions establish
correctness. Unit tests should cover decisions, boundary conditions, failure
handling, and orchestration with explicit inputs and test doubles. Integration
tests verify real storage, framework wiring, and concurrency independently.
