# ADR 004: Query-Based Normative Conformance

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

ADR 003 derives activities from stored observations during assessment. Normative models also need to evaluate relationships between observations, including timing, repetition, and repair conditions.

## Decision

Use a query-based paradigm for normative conformance checking. The versioned model defines queries that derive descriptive activities and evaluate normative conditions over a selected case prefix or range. Derived activities are not stored in a separate log.

Each successful assessment must map query results to exactly one status defined by ADR 001. An empty query result alone does not establish a status. Query execution failures are errors, not conformance outcomes.

Assessments retain the model identity and source observation references required by ADRs 001 and 003. Intervention authorization remains a separate policy decision.

No query language or execution engine is selected. Logica, for example, will not be used.

## Consequences

The observation schema, assessment boundaries, and repair deadlines require separate decisions. The selected implementation must support the required status distinctions and evidence references.

### Positive

- Normative conditions remain inspectable as queries over the retained observation log.
- One assessment can combine timing, attributes, and relationships across multiple observations.

### Negative

- Query results do not supply the four assessment statuses automatically; explicit status and temporal semantics are still required.
- Complex joins and absence checks can make normative queries difficult to inspect and debug.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Logica | Rejected after exploring the activity examples. The additional language and compiler complexity was judged too high for this project. |
| Procedural Python rules | Not selected. The chosen model expresses conditions over stored observations as queries rather than application control flow. |
