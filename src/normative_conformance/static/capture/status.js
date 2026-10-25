// Fixed page text keyed by the status keys a capture session reports.
export const STATUS = Object.freeze({
  opening: "Opening microphone…",
  active: "Microphone active.",
  finishing: "Finishing audio measurement…",
  stopped: "Microphone stopped. All captured audio was measured.",
  unsupported: "Use a browser with AudioWorklet support on HTTPS or localhost.",
  denied: "Microphone access was denied.",
  processing: "The microphone is applying audio processing. Choose a device that allows it to be disabled.",
  startFailed: "The microphone could not be started.",
  ended: "The microphone disconnected. Capture is incomplete.",
  backlog: "The connection cannot keep up with audio. Capture stopped with a gap.",
  rejected: "The server rejected the audio stream. Start a new microphone check.",
  connectionFailed: "The audio connection failed.",
  closed: "The audio connection closed before capture finished.",
  unacknowledged: "Capture stopped before the final audio was acknowledged.",
});
