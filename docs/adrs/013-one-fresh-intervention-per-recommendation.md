# ADR 013: One Fresh Intervention per Recommendation

- **Status:** Accepted
- **Date:** 2026-10-28
- **Decision owner:** Ben Merritt

## Context

ADR 009 made `intervene` a model recommendation, but nothing turned it into an intervention. The plan grouped recommendations in a two-second window and let later batches withdraw them. Batches now end with the target's turn (ADR 012), so consecutive recommendations are a turn apart, not fragments of one. An intervention already references exactly one assessment (ADR 005).

## Decision

- An `intervene` assessment creates one intervention in the same transaction. Its message comes from a fixed table keyed by the strongest target behavior at the selection threshold, or a general message when none qualifies.
- An unsent intervention is `pending` while its target revision is current, it is newer than 60 s, and no later assessment of the target's speech has an action. Otherwise it is `expired` and is never delivered.
- Interventions are not grouped, and recommendations are not withdrawn.

## Consequences

### Positive

- No schema change, grouping window, or extra state.
- A later decision about the target replaces an undelivered one by expiring it.

### Negative

- Two `intervene` turns in a row create two interventions.
- A client that delivers more than 60 s late receives nothing.
- Speech from the other speaker alone cannot withdraw a recommendation (ADR 010).

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Grouping window | Turn batches already space recommendations; grouping needs a link table |
| Reconsideration links between decisions | Expiry gives the same delivery outcome without tracking decision chains |
