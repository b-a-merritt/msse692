import { summarize } from "./capture/levels.js";
import { CaptureSession } from "./capture/session.js";
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
  startButton.disabled = true;
  session = new CaptureSession({
    onStatus: (key) => { statusLine.textContent = STATUS[key]; },
    onReady: () => { stopButton.disabled = false; },
    onLevels: (frames) => showLevels(summarize(frames)),
    onEnd: () => {
      session = null;
      startButton.disabled = false;
      stopButton.disabled = true;
    },
  });
  await session.start();
});

stopButton.addEventListener("click", () => {
  stopButton.disabled = true;
  session?.stop();
});

window.addEventListener("pagehide", () => session?.release());
