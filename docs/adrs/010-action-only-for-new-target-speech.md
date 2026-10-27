# ADR 010: Action Only for New Target Speech

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decision owner:** Ben Merritt

## Context

In a 620 s cordial interview capture, 31 of 85 batches had no new target speech. 29 of them returned `await_context`. Those answers concern no new target behavior and would hold recommendations open.

## Decision

Ask the action question only when a batch contains new target speech. Other batches store topic classifications with no action, no action confidence, and no action probabilities. The database requires action and confidence to be both present or both absent.

## Consequences

### Positive

- Speech from other speakers alone produces no action recommendation.
- Calls for those batches ask one fewer question.

### Negative

- Jev is still called for topic classification, so the number of calls is unchanged.
- Readers must handle an assessment without an action.
- Another speaker's apology or clarification cannot change a recommendation until the target speaks again.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Remove `await_context` | The problem observed was batches without target speech |
