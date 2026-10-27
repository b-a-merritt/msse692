# ADR 009: Decision-Model Assessment

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decision owner:** Ben Merritt
- **Supersedes:** ADRs 001, 003, 004, 006, and 007

## Context

SQL rules over phrase lists and signal thresholds matched predictions in 5 of 10 scored film cases. They missed paraphrases, such as the threat in case 8, and loud speech produced false positives. A phrase list cannot judge whether an apology or clarification already addressed a behavior.

## Decision

- Each batch of new observations, with up to 30 s (configurable) of earlier speech as context, goes to Jev as typed questions.
- Every new observation gets a score for each topic in a fixed list and one primary topic.
- New target speech also gets scores for seven behaviors (interruption, swearing, criticism, cruelty, contempt, defensiveness, stonewalling) and a hostility intensity.
- One action question chooses `remain_silent`, `await_context`, `reflect_later`, or `intervene`. It considers rectification already in the conversation. There is no repair timer. ADR 010 limits it to batches with new target speech.
- Application code builds the questions, binds each one to an observation, and assembles the stored result. The model has no tools or database access and writes no message text or evidence lists.
- Assessments store raw scores, the selection threshold, model and prompt versions, and the full request. Thresholds are applied when results are read.

## Consequences

### Positive

- Paraphrases and surrounding context inform each finding.
- Every input and answer is retained for inspection.

### Negative

- Answers can vary between runs, so re-running a request does not reproduce a stored result.
- Each batch is a paid external call. A failing call is retried on every poll.
- Findings are only as accurate as speaker attribution (ADR 008).
- Conformance statuses no longer exist. An intervention's source is an assessment with the `intervene` action.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Keep SQL rules | The film case results above |
| Free-text model output | It must be parsed and can cite evidence the system never supplied |
