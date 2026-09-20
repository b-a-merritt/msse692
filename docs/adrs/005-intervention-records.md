# ADR 005: Intervention Records

- **Status:** Accepted; prototype scope clarified during design review on 2026-09-20
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

A notification-only record cannot represent abstention. The earlier requirements also separate intervention decisions from notifications and restrict each decision to one assessment.

## Decision

Use one incoming `observation` schema. Store observations, assessments, and interventions in their respective tables. Store immutable normative model versions separately. Do not create separate observation-type, intervention-decision, or notification tables.

An intervention records a policy decision and references exactly one conformant assessment through a unique `assessment_id`. That assessment identifies its model version and exact evaluated case prefix. Grouping interventions is outside scope.

The response's `status` vocabulary has these meanings; this prototype produces only `pending` and `sent`:

| Status | Meaning |
|---|---|
| `pending` | Intervention was authorized and awaits delivery. |
| `sent` | Delivery completed successfully. |
| `failed` | Intervention was authorized, but delivery failed. |
| `abstained` | The policy decided not to intervene. No delivery occurs. |

Intervention `pending` is distinct from assessment `pending`, which means conformance is unresolved.

Retain the policy identity, decision reason, message, and decision time. A stored intervention is always authorized. Derive response status from `sent_at_us`: null means pending, otherwise sent. Case and subject are read through the source assessment. Delivery sets the timestamp once while preserving all decision fields.

## Consequences

The intervention remains a separate decision record, with its own identity and
creation time. A unique source assessment prevents duplicate authorization.
Case, authorization status, and delivery status need no duplicate stored fields.

`sent` means the consume-on-retrieval transaction committed before the HTTP
response. It does not guarantee receipt by the client. A pre-commit failure
leaves the record pending; response loss after commit leaves it sent.

Failed delivery and abstention remain reserved response vocabulary. Supporting
those states later requires extending the current storage model.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Separate decision and notification tables | Unnecessary for one local delivery per decision. |
| Multi-assessment link table | Removed; grouping is outside scope. |
| Policy fields on the assessment | Rejected; policy decisions have a separate commit boundary and meaning. |
| Separate observation-type tables | Rejected; raw chunks share one observation schema. |
