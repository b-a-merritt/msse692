# Quality Attribute Evaluation

## Result

The median time from the end of speech to a stored decision is 3.37 s on film replays and 8.35 s on live capture. The model call takes about 0.5 s of that. Most of the rest is waiting for the batch to close and, on live capture, transcription.

One worker handles about 2.1 assessments per second. It kept up with 10 simultaneous conversations but not 20, where the median decision time rose to 23.27 s. Every observation and batch was still stored and handled once. This evaluation reports measurements and sets no targets.

## Method

All runs used one machine: WSL2 Linux with 12 cores, Python 3.13.15, SQLite 3.53.1, `jev-1.14.0`, prompt `conversation-3`, one worker, and no discovered model.

| Run | Input | Setup |
|---|---|---|
| Film replays | 24 replays: each of the 12 film cases twice, at recorded pacing | One server and fresh database per case, six servers at a time |
| Live capture | 17 decisions across 5 captures | Speech through the capture page and the transcription provider |
| Stress | Phases 1–3 of `scripts/cases/stress.jsonl`: 1,812 observations in 60 conversations | One server and fresh database |

The film and live runs used code from before the request limits and dependency changes. Those changes do not touch the decision, worker, discovery, assessment, or model-client code.

| Measure | Definition |
|---|---|
| Decision | An assessment with an action. Batches without new target speech have no action |
| End of speech | Live capture: `end_at` of the batch's last observation. Replays: `received_at`, because replays post each observation at its recorded end, so replay times exclude transcription |
| Transcription | `received_at` minus `end_at`, live capture only |
| Wait to close | From the arrival of the batch's last observation until the next observation arrives, up to 20 s |
| Poll wait | From the batch closing until the worker picks it up (`evaluated_at`) |
| Model call and store | `evaluated_at` to `completed_at` |
| Total | End of speech to `completed_at` |

Each percentile is calculated separately, so the parts do not add up to the total.

## Response time

A conversation's last batch has no speech after it, so it closes after the 20 s idle limit. Those decisions are listed separately.

| Seconds | n | p50 | p95 | Max |
|---|---|---|---|---|
| Film replays, mid-conversation | 348 | 3.37 | 11.82 | 21.52 |
| Film replays, conversation end | 8 | 21.01 | 21.55 | 21.55 |
| Live capture, mid-conversation | 15 | 8.35 | 15.01 | 15.01 |
| Live capture, conversation end | 2 | 22.20 | 22.71 | 22.71 |

Mid-conversation parts:

| Seconds | Film replays p50 / p95 / max | Live capture p50 / p95 / max |
|---|---|---|
| Transcription | Not applicable | 1.57 / 12.21 / 12.21 |
| Wait to close | 2.36 / 11.12 / 20.00 | 1.35 / 13.02 / 13.02 |
| Poll wait | 0.59 / 1.00 / 2.40 | 0.71 / 2.33 / 2.33 |
| Model call and store | 0.50 / 0.69 / 1.08 | 0.40 / 0.59 / 0.59 |
| Total | 3.37 / 11.82 / 21.52 | 8.35 / 15.01 / 15.01 |

## Capacity

Each phase adds more simultaneous conversations. Phase 3 started before phase 2 finished: phase 2's last assessment was stored 284 s into the run, and phase 3's first observation arrived at 251 s.

| Phase | Conversations | Observations offered | Observations received | Assessments | Mid-conversation decision p50 / p95 / max (s) | Conversation-end decision p50 / p95 / max (s) |
|---|---|---|---|---|---|---|
| 1 | 10 | 3.7/s | 3.5/s | 134 | 5.30 / 7.43 / 8.44 | 21.26 / 23.52 / 23.52 |
| 2 | 20 | 7.2/s | 6.5/s | 268 | 23.27 / 50.04 / 62.44 | 45.65 / 60.62 / 74.01 |
| 3 | 30 | 10.6/s | 9.4/s | 402 | 51.02 / 99.65 / 107.70 | 99.15 / 107.48 / 108.79 |

From 180 s to 420 s, while batches were waiting, the worker handled 2.05–2.15 assessments per second. From the first assessment to the last, it averaged 1.80 per second. The model call and store took 0.41 s at p50, 0.54 s at p95, and 0.81 s at most.

In phase 1, 10 conversations produced about 1.6 batches per second, or about 0.16 per conversation. At that rate, 2.1 assessments per second serves about 13 conversations. This is an estimate. No run had 13 conversations.

## Resource use

| Measure | Result |
|---|---|
| Server CPU, share of one core | p50 7%, p95 14%, max 17% |
| Server memory (RSS) | 227 MB at start, 237 MB at peak |
| Database size after the run | 129 MB, about 160 KB per assessment |
| Share of the run the worker spent on model calls and storage | 77% |

The server process was sampled every 2 s. CPU use is low because the worker mostly waits for the provider.

## Bottlenecks

1. **Batch closing.** A target's turn closes when the next speaker's observation arrives, so decision time includes the next speaker's speech. This is the largest part of replay decision time at p50 and p95. A conversation's last batch waits the full 20 s.
2. **One sequential worker.** The worker makes one model call at a time, which limits capacity to about 2.1 assessments per second. Above that, decision time grows as batches wait. Receiving observations is not affected.

On live capture, transcription is the largest part at p50 and reaches 12.21 s. This comes from only 15 decisions, so it is not listed as a third bottleneck.

## Reliability

All 1,812 stress observations were stored and all 804 batches were handled. No batch was assessed twice and no observation was stored twice. All 1,812 observation requests returned 201 and took 9.4 ms at p50, 16.9 ms at p95, and 108.5 ms at most. The stress and film logs show no rejected batches or processing failures.

## Limitations

- Live capture has only 17 decisions, so its p95 and maximum rest on few rows.
- Results come from one machine, and the provider's response time is outside the system's control.
- Stress speech is short synthetic dialogue with alternating speakers.
- Phases 4–6 were not run. They offer more load than phase 3, which the worker already could not keep up with.
- No run used a discovered model, so these times do not include checking evidence.
- No run forced a crash or a provider outage.

Decision agreement is reported in [`scripts/cases/predictions.md`](../scripts/cases/predictions.md).
