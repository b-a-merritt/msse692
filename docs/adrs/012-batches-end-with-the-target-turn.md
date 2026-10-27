# ADR 012: Batches End With the Target's Turn

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decision owner:** Ben Merritt

## Context

Batches held up to four new observations, but the worker ran as soon as one was pending. In a 620 s interview capture, 74 of 85 batches held one observation, often a fragment such as "I". One 130 s target answer was assessed 18 times. Requests averaged 78 KB.

## Decision

- A batch ends with the target's turn: at the last target observation, once an observation from another speaker arrives. Other speakers' speech joins the target turn that follows it.
- A batch also ends once its speech spans 60 s, or when no speech has arrived for 20 s, so long answers and the end of a conversation are still assessed. Both durations are configurable.
- Up to 30 s (configurable) of earlier speech is still sent as context.
- The batch-size setting is removed.

## Consequences

### Positive

- The model judges whole target turns together with the speech that prompted them.
- There is one call per target turn rather than one per observation.

### Negative

- Decisions wait for the target's turn to end, for 60 s of speech, or for 20 s without speech.
- A short acknowledgement from another speaker ends the target's turn.
- While a batch is open, each poll reloads the case's speech.
- Requests grow with the batch, because each new observation still gets its own topic questions.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Larger batch size | The size is a maximum; the worker runs as soon as one observation is pending |
| Fixed delay before each batch | Splits turns at arbitrary points |
