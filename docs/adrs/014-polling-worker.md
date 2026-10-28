# ADR 014: Polling Worker

- **Status:** Accepted
- **Date:** 2026-10-28
- **Decision owner:** Ben Merritt

## Context

ADR 006 scheduled assessments from ingestion. Ingestion enqueued an assessment task in a persistent queue after each stored observation. The queue was a second store that could disagree with the database, and an enqueue failure turned a stored observation into an HTTP error. Decision-model calls (ADR 009) take hundreds of milliseconds, so scheduling precision no longer matters.

## Decision

- Ingestion only stores observations.
- One worker polls the database every second for cases with a resolved target and unhandled speech.
- Each case records the last handled sequence and target revision. A target change makes its stored speech unhandled again.
- An assessment and its progress commit in one transaction. A failed call leaves progress unchanged, so the next poll retries it; a request the provider rejects is skipped.

## Consequences

### Positive

- The database is the only record of pending work, so restarts need no queue recovery.
- Ingestion cannot fail because scheduling failed.

### Negative

- Work starts up to one second late, and each poll reloads an open batch's speech.
- One synchronous worker serializes all cases.
- Failures retry on every poll without an attempt limit.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Persistent queue | A second store that can disagree with the database |
| In-memory queue | Loses pending work on restart |
