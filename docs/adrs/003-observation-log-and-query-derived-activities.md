# ADR 003: Observation Log and Query-Derived Activities

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

Activity labels alone may discard properties needed by a normative model. Conditions like speech overlap require comparing observations. The system needs those observations available when assessing a case, especially when extending functionalities.

## Decision

The case log stores mocked validated observations. Each record includes an observation identifier, case identifier, speaker identifier, observation type, source, and timestamps appropriate to that type. The observation schema defines the additional attributes retained, such as volume measurements or configured-term matches. An upstream activity label is not persisted, but rather derived.

Invalid or unsupported observations are rejected before persistence. A valid, supported observation is retained even if it currently matches no activity definition. Case logs are append-only.

Assessment queries derive activity labels from the selected observations. A derivation may combine several records. For example, a query can compare two speakers' intervals to derive a speech-overlap activity.

Derived activity labels are computed at assessment time without a separate persisted activity log. Their definitions are explicit parts of the versioned model. Assessments retain references to the source observations and definitions used so that derivations can be reproduced.

Conformance status applies to the assessed prefix or range, not to each observation. Failure to match an activity definition does not discard the observation or assign it a conformance status.

For now, the system continues to mock sensing and upstream interpretation. This decision does not add real audio ingestion or processing.

## Consequences

This ADR supersedes the following statements without modifying the earlier files:

| Earlier decision | Replacement |
|---|---|
| [ADR 001](001-conformance-status.md): only constructed events enter the case log. | Accepted observations enter the case log before activity derivation. |
| [ADR 002](002-observation-to-event-construction-boundaries.md): event construction emits an event or filters the input before conformance checking. | Assessment queries derive activities from stored observations. An observation that produces no activity remains available to later assessments. |

The earlier filtering consequences apply to inputs rejected at ingestion, not to retained observations that match no activity definition.

ADR 001's status definitions, model orientation, and intervention eligibility gate still apply. ADR 002's restrictions on descriptive event names, unsupported social judgments, and source-quality interpretation still apply.

### Positive

- Retained observations remain available when later observations or different definitions make them relevant.
- Versioned definitions and source references allow activity derivations to be reproduced.

### Negative

- Keeping observations that match no current activity increases storage compared with retaining only matching activities.
- Assessment repeats derivation work; cross-observation queries may cost more than reading stored activity labels.

## Alternatives Considered

- **Persist only upstream activity labels:** rejected because labels alone may omit attributes and relationships needed by the normative model.
- **Maintain a separate derived activity log:** not selected because it duplicates information reproducible from observations and versioned definitions.
- **Discard valid observations that match no activity:** rejected because later observations or different definitions may make those records relevant.
