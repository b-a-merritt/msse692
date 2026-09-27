# AI Assistance

| Work | How AI helped | Example Prompt |
|---|---|---|
| Code review | AI assisted all code reviews before committing. | Review these changes for bugs, edge cases, and consistency with project conventions. Read all of the documentation in ./docs before making a decision. Let's go back and forth on anything you are not clear about. It is better to create a plan that is approved than to create changes. In all things speak directly and do not use highfalutin language. |
| Observation examples | Silero VAD detected speech, faster-whisper transcribed dialogue, and pyannote identified speaker turns. These outputs were combined with timestamps and measured signal levels to produce observation examples. | Create a tool that converts conversation audio into JSONL observations with speaker IDs, timestamps, transcripts, and signal levels. |
| Test generation | AI assisted in creating tests for functionality before starting to code and while changing implementation. It saved a lot of time creating those tests. I will go back through during weeks 7 and 8 to refine them, but for now, they are helpful to ensure I don't break anything as I implement them | Create tests for the functionality as I implement them |
