import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";

import { browser, resetBrowser } from "./browser.mjs";

const elements = new Map();
globalThis.document = {
  getElementById: (id) => {
    if (!elements.has(id)) {
      elements.set(id, { children: [], replaceChildren(...children) { this.children = children; }, addEventListener(kind, listener) { this[kind] = listener; } });
    }
    return elements.get(id);
  },
};
let pagehide;
globalThis.window = { addEventListener: (_, listener) => { pagehide = listener; } };
await import("../../../src/normative_conformance/static/capture.js");
const element = (id) => elements.get(id);

beforeEach(() => { resetBrowser(); element("target-order").value = "1"; });
afterEach(() => { pagehide(); mock.restoreAll(); });

test("start resets readouts and shows fixed status text until the server is ready", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  element("minimum").textContent = "-10.0 dBFS";
  const starting = element("start").click();
  assert.equal(element("start").disabled, true);
  assert.equal(element("minimum").textContent, "—");
  assert.equal(element("duration").textContent, "0.0 s");
  assert.equal(element("level").value, -120);
  assert.equal(element("status").textContent, "Opening microphone and connecting to transcription…");
  await starting;

  browser.socket.receive({ type: "ready", session_id: "test-session", speech_model: "test-model" });
  assert.equal(element("stop").disabled, false);
  assert.equal(element("status").textContent, "Microphone active. Transcribing live.");
});

test("renders the latest level summary", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  await element("start").click();
  browser.socket.receive({ type: "ready", session_id: "test-session", speech_model: "test-model" });
  browser.socket.receive({ type: "levels", frames: [
    { start_ms: 1480, end_ms: 1500, dbfs: -20 }, { start_ms: 1500, end_ms: 1520, dbfs: -45 },
  ] });
  assert.equal(element("minimum").textContent, "-45.0 dBFS");
  assert.equal(element("average").textContent, "-32.5 dBFS");
  assert.equal(element("maximum").textContent, "-20.0 dBFS");
  assert.equal(element("duration").textContent, "1.5 s");
  assert.equal(element("level").value, -45);
});

test("stop waits for acknowledgment, then allows a new check", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  await element("start").click();
  browser.socket.receive({ type: "ready", session_id: "test-session", speech_model: "test-model" });
  element("stop").click();
  assert.equal(element("stop").disabled, true);
  assert.equal(element("status").textContent, "Finishing transcription and speaker corrections…");
  browser.socket.receive({ type: "stopped" });
  assert.equal(element("status").textContent, "Microphone stopped. Final transcripts and speaker corrections received.");
  assert.equal(element("start").disabled, false);
});

test("a failure shows fixed text rather than the server's message and resets the controls", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  await element("start").click();
  browser.socket.receive({ type: "ready", session_id: "test-session", speech_model: "test-model" });
  browser.socket.receive({ type: "error", message: "Expected PCM audio or stop" });
  assert.equal(
    element("status").textContent,
    "The server rejected the audio stream. Start a new microphone check.",
  );
  assert.equal(element("start").disabled, false);
  assert.equal(element("stop").disabled, true);
  assert.equal(browser.track.stopped, true);
});

test("leaving the page releases an active check", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  await element("start").click();
  browser.socket.receive({ type: "ready", session_id: "test-session", speech_model: "test-model" });
  pagehide();
  assert.equal(browser.track.stopped, true);
  assert.equal(element("start").disabled, false);
});

test("uses the selected speaker order, shows the case, and locks selection during capture", async () => {
  let selectedOrder;
  mock.method(globalThis, "fetch", async (_, options) => {
    selectedOrder = JSON.parse(options.body).target_speaker_order;
    return { ok: true, json: async () => ({ case_id: "selected-case" }) };
  });
  element("target-order").value = "2";
  await element("start").click();
  assert.equal(selectedOrder, 2);
  assert.equal(element("capture-case").textContent, "Case selected-case");
  assert.equal(element("target-order").disabled, true);
  browser.socket.receive({ type: "stopped" });
  assert.equal(element("target-order").disabled, false);
});

test("case setup failure restores controls and shows fixed text", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: false }));
  await element("start").click();
  assert.equal(element("status").textContent, "Could not create the capture case. Try starting again.");
  assert.equal(element("capture-case").textContent, "No case created.");
  assert.equal(element("start").disabled, false);
  assert.equal(element("target-order").disabled, false);
  assert.equal(element("stop").disabled, true);
  assert.equal(browser.socket, undefined);
});
