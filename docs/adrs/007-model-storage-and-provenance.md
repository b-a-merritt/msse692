# ADR-007: Model Storage and Provenance

- **Status:** Accepted; simplified during design review on 2026-09-20
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

Assessments must retain their model version and exact evaluated observations.
Every evaluation uses a full immutable case prefix. Each intervention has one
source assessment; grouping is outside the prototype scope.

## Decision

Use six application tables:

| Table | Responsibility |
|---|---|
| `experiment_config` | Retain the singleton experiment subject and initialization time. |
| `case_log` | Identify cases and their creation times. |
| `observation` | Store raw speech chunks, identified by `(case_id, observation_id)`. |
| `normative_model_version` | Store immutable definitions, keyed by `(model_id, version)`. |
| `assessment` | Store the result, evaluation time, model reference, case, and history cutoff. |
| `intervention` | Store a policy decision with one unique source assessment reference and delivery time. |

Model versions retain their name, orientation, rules, and parameters. Startup
compares supplied definitions directly with stored content and validates SQL and
rule references. Conflicting or invalid definitions stop startup. Models are fixed
while the server runs, and historical definitions cannot be overwritten.

An assessment's `case_id` and `through_sequence` identify every evaluated
observation, including context and nonmatching evidence. Observations cannot be
updated or deleted; ingestion allocates increasing sequences under the writer
lock. Later arrivals therefore leave historical extents unchanged. Derive extent
IDs and counts on retrieval instead of storing duplicate memberships or counts.

An intervention stores a unique `assessment_id` foreign key. Its source must be
conformant. Retrieve case and subject through that reference. Delivery changes
only `sent_at_us`; source and decision evidence remain immutable.

## Consequences

- Historical results resolve their exact definitions and full evaluated prefixes.
- Composite keys avoid parallel internal and external identifiers.
- Foreign keys and uniqueness guards preserve source integrity without join tables.
- Prefix provenance depends on append-only observations and increasing case sequences.
  Supporting arbitrary subsets would require a new evidence representation.
- Multiple source assessments per intervention would require a schema change;
  the current prototype deliberately has one source.

## Alternatives Considered

- **Explicit evidence membership rows:** unnecessary while every evaluation uses a full immutable prefix.
- **Intervention/assessment association table:** unnecessary for one source per decision.
- **Model definitions only in repository files:** insufficient for resolving stored historical definitions.
- **Separate parent model table:** unnecessary for the fixed catalog.
- **Overwrite definitions:** rejected because it changes historical assessment meaning.
