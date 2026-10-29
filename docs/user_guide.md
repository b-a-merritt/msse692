# User guide

Start the app using the [setup instructions](../README.md#run). A decision-model credential is required for both capture and replay. Results appear in the [API docs](http://127.0.0.1:8000/docs).

## Microphone capture

Configure the [transcription credential](deployment_guide.md#configuration), open [capture](http://127.0.0.1:8000/capture), choose whether the target speaks first or second, and select **Start microphone**. Allow microphone access and speak in that order. Each Start creates a fresh case; save the displayed case ID.

The page shows transcripts, session-local speaker labels, and signal levels. **Unassigned** speech is stored with speaker `PENDING`. Assessment waits until the selected speaking order resolves. Speaker corrections update the transcript only; assessments use the labels speech arrived with, and the target does not change.

Select **Stop** and wait for completion. An error or early close means capture is incomplete, but committed speech remains saved. Reloading clears the display. Microphone capture requires localhost or HTTPS, AudioWorklet support, and a 16 kHz audio context.

## HTTP input and replay

In `/docs`, create a case with **PUT /api/v1/cases/{case_id}/target**, using `docs-demo` and `{"target_speaker_id":"speaker-2"}`. Then submit this body to **POST /api/v1/observations**:

```json
{
  "case_id": "docs-demo", "observation_id": "chunk-1",
  "speaker_id": "speaker-2",
  "start_at": "2026-10-10T12:00:00Z", "end_at": "2026-10-10T12:00:04Z",
  "transcript": "Please help with the dishes.",
  "signal_level_min": -50, "signal_level_avg": -30, "signal_level_max": -10
}
```

**201** confirms storage. Duplicate case/observation IDs return **409**. To replay supplied observations:

```bash
uv run python scripts/send_observations.py scripts/cases/case-3.jsonl --target-speaker-id speaker-2
```

The script preserves recorded gaps unless `--delay` is supplied. Use fresh storage or new case IDs for independent runs. The [manifest](../scripts/manifest.md) identifies the source material.

## Results

Read **GET /api/v1/cases/{case_id}/assessments**. Results contain topics, target behavior scores, intensity, and an action: `remain_silent`, `await_context`, `reflect_later`, or `intervene`. An assessment covers a target turn and the other speech before it. It starts once the target stops speaking, after 60 s of speech, or after 20 s without speech. A batch without new target speech has no action. Results depend on the conversation and model; no phrase guarantees an action. An `intervene` action creates an intervention with a fixed message. Read pending ones with **GET /api/v1/interventions?case_id={case_id}&status=pending**, or deliver them with **POST /api/v1/cases/{case_id}/interventions/deliver**. One that waits over 60 s, or is followed by a newer assessment of the target, expires instead.

An empty list can mean the target's turn is still open, inference is pending, the target is unresolved, or processing failed. Check **GET /api/v1/cases/{case_id}**, readiness, and server logs. Change the target through PUT using either `target_speaker_order` (1 or 2) or `target_speaker_id`; selecting a label clears the order.

For validation and storage errors, see the [API reference](api.md#errors).

## Pattern evidence

After replaying conversations, discover the topics that preceded undesired behavior in all of them:

```bash
uv run discover-model
```

It prints the stored model's topics, or reports that fewer than 3 conversations ended in undesired behavior. Use the same `APP_DB_PATH` as the server. Later decisions check each conversation against the newest model; when every listed topic has come up, the action question is told so. Evidence never triggers an intervention by itself, and a run without a model is unaffected. The stored request in `assessment.request_json` records any evidence; the assessments API does not show it.
