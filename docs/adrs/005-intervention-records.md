# ADR 005: Intervention Records

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

A notification-only record cannot represent abstention. The earlier requirements also separate intervention decisions from notifications and restrict each decision to one assessment.

## Decision

Use one incoming `observation` schema. Store observations, assessments, and interventions in their respective tables. Allow additional tables for normative model versions and associations between records. Do not create separate observation-type, intervention-decision, or notification tables.

An intervention records a policy decision and references one or more source assessments. Those assessments identify the normative model versions and exact observations evaluated.

The intervention's `status` has these meanings:

| Status | Meaning |
|---|---|
| `pending` | Intervention was authorized and awaits delivery. |
| `sent` | Delivery completed successfully. |
| `failed` | Intervention was authorized, but delivery failed. |
| `abstained` | The policy decided not to intervene. No delivery occurs. |

Intervention `pending` is distinct from assessment `pending`, which means conformance is unresolved.

Retain the policy identity, decision reason, and decision time. Persist an authorized intervention as `pending` before attempting delivery. Delivery status updates must preserve the decision evidence and source assessment references.

## Consequences

Abstention and delivery failure remain distinguishable without a notification table.

The local outbox must define what constitutes successful delivery before using `sent`; it must not imply external delivery in the course prototype.

### Positive

- Abstention, awaiting delivery, and delivery outcomes remain distinguishable in one record.
- One intervention can retain references to several supporting assessments without duplicating its policy decision on each assessment.

### Negative

- One status field combines policy outcome and delivery progress; transition rules must preserve the original decision evidence.
- Multiple assessment references require explicit link storage and referential integrity constraints.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Separate decision and notification tables | Not selected. One intervention record retains both the policy decision and delivery state. |
| Notifications only for authorized interventions | Rejected. Missing notification records would not distinguish abstention from an unevaluated policy or notification creation failure. |
| Policy decision fields on each assessment | Not selected. One intervention may combine several assessments; storing its decision on each would duplicate it. |
| Separate tables for observation types | Rejected. A shared observation table keeps the case history in one relation. |
