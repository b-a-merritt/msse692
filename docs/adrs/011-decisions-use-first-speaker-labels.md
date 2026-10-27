# ADR 011: Decisions Use First Speaker Labels

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decision owner:** Ben Merritt
- **Supersedes:** ADR 008's rule that later decision context uses the latest revision

## Context

In a 620 s interview capture, 15 speaker revisions arrived in two bursts, 40–460 s after the speech they corrected. Every affected batch had already been assessed, so none of the 23 corrected observations reached a decision. Nine revisions moved one-word acknowledgements to a third speaker who was not present.

## Decision

Decisions use speech with the speaker labels it was ingested with. Revisions are stored and linked to the observations they replace, but batch boundaries, snapshots, and classifications ignore them. Revisions never trigger reassessment.

## Consequences

### Positive

- An assessment shows the speech exactly as the system judged it.
- Snapshots no longer merge revised turns with handled speech.

### Negative

- Attribution errors that a later revision fixes remain in decisions (ADR 008).
- Finding where revisions and decisions disagree requires comparing stored revisions with assessments.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Reassess when a revision arrives | Revisions arrived minutes late; a recommendation about a long-past moment cannot help |
| Delay batches until revisions settle | Revisions can arrive at the end of capture |
