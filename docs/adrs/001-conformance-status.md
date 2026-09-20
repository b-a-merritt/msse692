# ADR 001: Conformance Status and Intervention Eligibility

- **Status:** Accepted
- **Date:** 2026-09-05
- **Decision owner:** Ben Merritt

## Context

Not every upstream observation becomes an event. For example, an input that triggers on profanity would not emit speech events for non-profane conversations. Those non-profane conversations are thereby left out of the event log. E

Conformance and intervention answer different questions. A model match may be relevant to an intervention decision, but it cannot authorize an intervention by itself. For example, there might be contexts in which notifactions are not sent.

## Decision

Event construction emits only constructed events to the case log. An input that does not produce an event is filtered before conformance checking and receives no assessment. The system does not use `inapplicable` or `indeterminate` as statuses for filtered inputs.

The fixed model has the orientation `undesirable_pattern`. Every assessment identifies the model name, version, and orientation.

The conformance monitor returns exactly one of these statuses for the assessed event prefix or range:

- `conformant` — the assessed history matches the applicable undesirable-behavior pattern.
- `non-conformant` — the assessed history definitely does not match that pattern.
- `pending` — the result depends on a future event or an unexpired deadline.
- `conflicted` — applicable checks give incompatible results that have not been resolved.

Only a `conformant` assessment is eligible for the separate intervention policy. Eligibility does not authorize intervention. The policy may abstain.

`Non-conformant`, `pending`, and `conflicted` assessments are not intervention-eligible, but could be used when conformance checks again for a different model. They remain available for inspection.

## Consequences

- Filtered inputs create neither an event nor an assessment.
- Expected-result traces must cover all four statuses.
- The intervention policy must accept only eligible `conformant` assessments and must support abstention.

This decision does not choose the conformance algorithm, assessment window, rule formalism, or intervention strategy.

### Positive

- Distinguishes an unresolved assessment from a definite model match or mismatch.
- Keeps intervention authorization separate from conformance and permits abstention.

### Negative

- The negative model orientation can be misread unless every result identifies the model and explains the status.
- Four statuses require explicit temporal and conflict rules, with tests for each outcome.

## Alternatives rejected

### Treat `non-conformant` as the undesirable result

Rejected because it conflicts with the model's negative orientation. A match with the undesirable-pattern model is `conformant` by definition. This is to have common terminology with other normative conformance checking projects.

### Give filtered inputs a conformance status

Rejected because the monitor has no constructed event history to assess. Filtering is an event-construction outcome, not a conformance result.
