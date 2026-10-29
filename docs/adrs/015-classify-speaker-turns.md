# ADR 015: Classify Speaker Turns

- **Status:** Accepted
- **Date:** 2026-10-29
- **Decision owner:** Ben Merritt
- **Supersedes:** ADR 009's rule that every new observation is classified

## Context

AssemblyAI splits one speaker's turn into several observations, often fragments such as "I". ADR 012 batches a whole target turn, but each new observation still got its own 8 topic questions, plus 8 behavior and hostility questions for target speech. The model judged fragments, and requests grew with the number of observations.

## Decision

- A turn is consecutive new observations from one speaker, ordered by start time, end time, and observation ID. Context speech does not split a turn.
- Each turn gets the topic questions, and each target turn the behavior and hostility questions, once. The questions name the turn's rows in the snapshot.
- A classification references the turn's first observation. Readers rebuild the turn from the assessment's sequence range, so the schema is unchanged.
- The assessments API lists each classification's `observation_ids`. `observation_id` remains the first of them.
- The prompt version is `conversation-2`.

## Consequences

### Positive

- The model judges whole turns rather than fragments.
- Questions per batch scale with turns, not observations.
- Process discovery can treat each classification as one turn.

### Negative

- A turn split by a batch boundary, including the 60 s limit, becomes two classifications.
- One score covers the whole turn, so a behavior cannot be traced to one of its observations.
- Assessments made under `conversation-1` classified observations. The listing rebuilds turns for them too, so an observation that started a turn reports the whole turn.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Store turns in the schema | The sequence range and ordering already determine them |
| Merge each turn into one transcript before sending | Hides the times and signal levels of each observation from the model |
