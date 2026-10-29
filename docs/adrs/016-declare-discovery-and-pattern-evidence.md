# ADR 016: Declare Discovery and Pattern Evidence

- **Status:** Accepted
- **Date:** 2026-10-29
- **Decision owner:** Ben Merritt

## Context

Each decision judges one batch with up to 30 s of context. Earlier conversations can show that certain topics come before conflict even when each is harmless alone, such as a partner's mother and then money from shared savings.

Eight written control conversations were replayed through Jev. Primary topics named the specific subject (`repairs`, `credit_card_debt`) and varied for the same pattern; topics at the 0.7 threshold did not. Inductive Miner models with alignment fitness fit calm conversations at 0.86–1.00, as well as conflict ones. Declare precedence rules gave evidence in 5 of 6 held-out conflict conversations and 0 of 2 calm ones, never before every planted topic had come up.

## Decision

- **Trace.** A case's trace uses the assessments of its current target revision. Each topic at the selection threshold is an event the first time it appears. The first assessment with criticism, contempt, cruelty, defensiveness, stonewalling, or interruption at the threshold ends the trace with `undesired_behavior`, without its own topics. Swearing alone does not count.
- **Discovery.** `uv run discover-model` runs pm4py Declare discovery on the traces that end in `undesired_behavior`. It keeps `precedence(topic, undesired_behavior)` rules with support and confidence ratios of 1.0: the topics that came before undesired behavior in every such conversation. Fewer than 3 such traces store no model. Otherwise a new, append-only model records its topics and the assessments it used.
- **Conformance.** Once a batch closes, the worker builds the case's trace from earlier assessments, adds `undesired_behavior`, and checks it with Declare conformance against the newest model. Evidence requires at least one rule, every rule satisfied, and a trace that has not ended.
- **Evidence.** Only the action question receives evidence: its instructions name the topics and say evidence is not a probability of conflict and never justifies intervention by itself, and its `intervene` option also covers emerging tension. Evidence stays out of the shared state, so the classifications that feed discovery do not see it. The stored request records it under `evidence`.
- **Ownership.** `services/model/` stores and reads models; `services/discovery/` computes them.
- The prompt version is `conversation-3`, which also asks whether a turn expresses "a wish or threat to hurt, intimidate, or humiliate the listener".

## Consequences

### Positive

- A combination of individually harmless topics can inform an action; one topic alone does not.
- Each request records whether evidence was supplied and from which model.
- Runs without a model are unchanged apart from the cruelty wording, so they separate the decision model's effect from discovery's.

### Negative

- With few conversations, a topic that happens to precede every conflict becomes required, and a conversation without it never matches.
- Evidence uses only earlier batches. When the last required topic and the attack share a batch, no evidence is given; when the attack follows in the next batch, evidence arrives with it.
- The newest model applies to every case. The app cannot establish that conversations share participants.
- A calm conversation that covers every required topic receives evidence; the action question must still choose silence.
- pm4py is licensed under AGPL v3, adds about 20 dependencies, and adds about 0.9 s to import time.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Primary-topic events | Varied for the same pattern |
| Inductive Miner with alignment fitness | Did not separate calm from conflict conversations |
| Dropping topics that also appear in calm conversations | Removes the pattern's topics, which are each harmless alone |
| Partial matches | Gave evidence after one topic of the pattern |
| A second request for the evidence | Doubles requests, and the action question already weighs context |
| Evidence in the snapshot state | Every question would see it, including the classifications that feed discovery |
| Discovery inside the worker | Puts model construction in the API process |
