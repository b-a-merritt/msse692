# User guide

Start the app using the [setup instructions](../README.md#run). A decision-model credential is required for both capture and replay. Results appear in the [API docs](http://127.0.0.1:8000/docs).

## Microphone capture

Configure the [transcription credential](deployment_guide.md#configuration), open [capture](http://127.0.0.1:8000/capture), choose whether the target speaks first or second, and select **Start microphone**. Allow microphone access and speak in that order. Each Start creates a fresh case; save the displayed case ID.

The page shows transcripts, session-local speaker labels, and signal levels. **Unassigned** speech is stored with speaker `PENDING`. Assessment waits until the selected speaking order resolves. Speaker corrections update the transcript and later assessment context; they do not change the target or existing decisions.

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

Read **GET /api/v1/cases/{case_id}/assessments**. Results contain topics, target behavior scores, intensity, and an action: `remain_silent`, `await_context`, `reflect_later`, or `intervene`. A batch without new target speech has no action. Results depend on the conversation and model; no phrase guarantees an action. Recommendations do not create interventions automatically.

An empty list can mean inference is pending, the target is unresolved, or processing failed. Check **GET /api/v1/cases/{case_id}**, readiness, and server logs. Change the target through PUT using either `target_speaker_order` (1 or 2) or `target_speaker_id`; selecting a label clears the order.

For validation and storage errors, see the [API reference](api.md#errors).
