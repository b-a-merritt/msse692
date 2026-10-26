import { summarize } from "./capture/levels.js";
import { CaptureSession } from "./capture/session.js";
import { Transcript } from "./capture/transcript.js";
import { STATUS } from "./capture/status.js";

const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const statusLine = document.getElementById("status");
const readouts = {
  minimum: document.getElementById("minimum"),
  average: document.getElementById("average"),
  maximum: document.getElementById("maximum"),
  duration: document.getElementById("duration"),
};
const meter = document.getElementById("level");
const transcript = new Transcript(document.getElementById("transcript"));
const providerSession = document.getElementById("provider-session");
const targetOrder = document.getElementById("target-order");
const caseLabel = document.getElementById("capture-case");
let session = null;

function resetLevels() {
  readouts.minimum.textContent = "—";
  readouts.average.textContent = "—";
  readouts.maximum.textContent = "—";
  readouts.duration.textContent = "0.0 s";
  meter.value = -120;
}

function showLevels(summary) {
  readouts.minimum.textContent = `${summary.minimum.toFixed(1)} dBFS`;
  readouts.average.textContent = `${summary.average.toFixed(1)} dBFS`;
  readouts.maximum.textContent = `${summary.maximum.toFixed(1)} dBFS`;
  readouts.duration.textContent = `${summary.seconds.toFixed(1)} s`;
  meter.value = summary.latest;
}

startButton.addEventListener("click", async () => {
  if (session) return;
  resetLevels();
  transcript.clear();
  providerSession.textContent = "Connecting…";
  caseLabel.textContent = "No case created.";
  startButton.disabled = true;
  targetOrder.disabled = true;
  session = new CaptureSession({
    onStatus: (key) => { statusLine.textContent = STATUS[key] ?? STATUS.rejected; },
    onCase: (record) => { caseLabel.textContent = `Case ${record.case_id}`; },
    onReady: (message) => {
      stopButton.disabled = false;
      providerSession.textContent = `Session ${message.session_id} · ${message.speech_model}`;
    },
    onLevels: (frames) => showLevels(summarize(frames)),
    onTranscript: (message) => transcript.update(message),
    onEnd: () => {
      session = null;
      startButton.disabled = false;
      targetOrder.disabled = false;
      stopButton.disabled = true;
    },
  });
  await session.start(Number(targetOrder.value));
});

stopButton.addEventListener("click", () => {
  stopButton.disabled = true;
  session?.stop();
});

window.addEventListener("pagehide", () => session?.release());
