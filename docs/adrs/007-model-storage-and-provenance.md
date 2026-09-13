# ADR-007: Model Storage and Provenance

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

Assessments must identify the model version and observations evaluated. Interventions can reference several assessments.

## Decision

Use these six tables (not-exclusive as there might be join tables):

| Table | Responsibility |
|---|---|
| `observation` | Store all supported incoming observation types in one table. |
| `normative_model_version` | Store immutable model versions and their SQL definitions. |
| `assessment` | Store the result, evaluation time, assessed extent, and reference to exactly one model version. |
| `assessment_observation` | Link assessments to their exact evaluated observation sets, not only observations that matched an activity. |
| `intervention` | Store the policy decision and delivery status defined by ADR 005. |
| `intervention_assessment` | Link each intervention to one or more source assessments. |

Each normative model version stores a stable model identifier, name, version, `undesirable_pattern` orientation, definitions with rule identifiers, model parameters, and content hash. The hash covers the definitions and behavior-affecting parameters. The model identifier and version pair is unique. Changed content requires a new version and existing versions are not overwritten.

Initialization seeds the project-supplied versions without duplicating or replacing existing records. Startup loads the explicitly supplied versions and validates their metadata, hashes, rule references, and SQL against the database schema. Validation failure stops startup. Models remain fixed while the server runs. There is no runtime model-editing API provided.

Association tables use foreign keys and unique reference pairs. Commit each assessment or intervention with its associations in one transaction. Later assessments and delivery updates do not change existing source associations.

## Consequences

### Positive

- Historical assessments retain their original model definitions and observation references.
- Explicit associations support shared observations and multi-assessment interventions without identifier lists embedded in records.

### Negative

- Association tables add rows, joins, and transactional integrity requirements.
- Retaining model versions and evaluated observation links increases storage and migration work.

## Alternatives Considered

- **Model definitions only in repository files:** not selected as the sole stored source; assessments must resolve their exact model definitions from SQLite.
- **Identifier lists inside assessments and interventions:** not selected; association tables provide explicit foreign keys and unique membership.
- **A separate parent `normative_model` table:** deferred; the fixed-model prototype can retain model identity in each version record.
- **Overwrite the current model definition:** rejected because it would change the definition associated with historical assessments.
