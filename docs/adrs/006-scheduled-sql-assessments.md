# ADR 006: Scheduled SQL Assessments

- **Status:** Accepted
- **Date:** 2026-09-12
- **Decision owner:** Ben Merritt

## Context

ADR 004 selected query-based assessment without choosing a language or engine. Assessment results can change when observations arrive, repair deadlines expire, or observations leave a sliding window.

## Decision

Implement activity definitions and normative conditions as SQL queries executed against SQLite.

After an observation is validated and committed, schedule assessment of the affected case. A background worker runs each supplied model's full assessment query set for that case.

Also schedule assessments at repair deadlines and relevant window expirations. These checks must run without requiring another observation to arrive. Assessments are not limited to fixed one-minute intervals.

Use a sliding time window within each case to detect new qualifying patterns. For checks awaiting repair, retain the exact supporting observation references until resolution. Observations leaving the detection window do not cancel an unresolved repair check or remove its evidence from the log.

Each assessment records its evaluation time and exact evaluated observations. Later evaluations create new assessments rather than rewriting earlier results.

## Consequences

The scheduler controls when assessment runs; the SQL model defines the conditions evaluated. Query selection based on dependencies is deferred until performance testing demonstrates a need.

Window length, repair allowance, timestamp boundary conventions, model storage, and scheduler recovery behavior remain undecided.

### Positive

- Observations and time boundaries can trigger assessment without waiting for a fixed polling interval or another observation.
- Sliding windows limit new-pattern detection to recent behavior while pending checks retain their supporting evidence.

### Negative

- Deadline and window-expiration scheduling requires duplicate prevention and restart recovery.
- Running full query sets can repeatedly evaluate overlapping histories; unresolved repair checks can require evidence outside the current detection window.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Fixed one-minute assessment schedule only | Not selected. Observation responses and deadline resolution would wait for the next periodic check. |
| Assessment only when observations arrive | Rejected. Deadlines and window expirations can change results without new observations. |
| Unbounded case-prefix pattern detection | Not selected for new patterns. Older behavior would continue contributing instead of aging out of the detection window. |
| Independent one-minute segments | Rejected. Related observations and repairs can fall on opposite sides of a segment boundary. |
| Restrict every assessment to the current sliding window | Rejected. Supporting evidence could leave the window before a pending repair check reaches its deadline. |
| Dependency-based query selection from the start | Deferred. Run the full query set for the affected case until performance testing justifies the added selection logic. |
