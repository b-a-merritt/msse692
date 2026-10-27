# ADR 008: Live Audio Ingestion

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decision owner:** Ben Merritt

## Context

Mocked observation files cannot show how the system behaves on real speech. Loudness must come from the audio itself.

## Decision

- The browser captures 16 kHz mono PCM16 through an AudioWorklet and sends 100 ms packets over a WebSocket. Gain control, noise suppression, and echo cancellation are off because they flatten loudness.
- The server forwards audio unchanged to AssemblyAI streaming with speaker labels on and profanity filtering off. Audio is not stored.
- The server measures 20 ms frames in dBFS. Each observation stores the min, mean, and max of the frames under its words.
- Each finalized turn becomes one observation per run of consecutive words from one speaker. Its ID derives from the provider session, turn, word span, and speaker label.
- Speaker revisions are appended as replacements linked to the original observation IDs. They never change observations, targets, or stored assessments. Later decision context uses the latest revision.
- Each case selects its target by speaking order or by an explicit speaker label.

## Consequences

### Positive

- Assessments use real speech, timing, and loudness.
- No audio is retained.

### Negative

- Speaker attribution errors become behavior findings about the wrong person. In a 620 s interview capture, revisions replaced 27 of 100 turns and introduced a third speaker. The highest target behavior scores were on turns that read as the other speaker's.
- Capture depends on a paid external provider and a network connection.
- Speaking order identifies a target within one case only.

## Alternatives Rejected

| Alternative | Reason |
|---|---|
| Browser audio processing left on | Gain control flattens the loudness the observations record. |
| Mocked observation files only | They cannot show behavior on real speech. They remain available for replays. |
