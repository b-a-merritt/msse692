# ADR 017: Batches End After Three Turns

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Ben Merritt
- **Supersedes:** ADR 012's rule that only the target's turn, the speech duration, or idle time ends a batch

## Context

Each turn of new speech gets about 160 questions, mostly topics (ADR 015). A batch could hold any number of turns before the target spoke. In a film replay, six short turns among four speakers made a 963-question request, which the provider rejected as `max_tokens_exceeded`; the worker skips rejected batches, so that speech was never assessed. Across 747 accepted requests, the largest had 486 questions, and the average batch held 1.96 turns.

## Decision

- A batch also ends at the end of its third turn, when another speaker's observation arrives. The limit is configurable (`DECISION_MAX_BATCH_TURNS`).
- Turns are never split; a capped batch without target speech gets no action question.

## Consequences

### Positive

- A batch asks at most 486 questions (three turns of 159 topic questions, one target turn's 8 behavior and intensity questions, and the action), the size of the largest accepted request.
- Typical batches, another speaker's turn followed by the target's, are unchanged.

### Negative

- Rapid exchanges among several speakers become several requests.
- The provider's token limit is not published, so three turns is a bound from observed requests, not a guarantee. A long monologue or context can still exceed it.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Ask topics once per batch | Changes per-turn topics in the API and classification records |
| Remove topics never selected in the evaluation | Fits the list to 80 film and scripted conversations |
| Split a rejected batch and retry | Adds a recovery path for a request size that can be prevented |
