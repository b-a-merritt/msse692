import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import { browser, resetBrowser } from "./browser.mjs";

const elements = new Map();
globalThis.document = {
  getElementById: (id) => {
    if (!elements.has(id)) {
      elements.set(id, { addEventListener(kind, listener) { this[kind] = listener; } });
    }
    return elements.get(id);
  },
};
let pagehide;
globalThis.window = { addEventListener: (_, listener) => { pagehide = listener; } };
await import("../../../src/normative_conformance/static/capture.js");
const element = (id) => elements.get(id);

beforeEach(resetBrowser);
afterEach(() => pagehide());

test("start resets readouts and shows fixed status text until the server is ready", async () => {
  element("minimum").textContent = "-10.0 dBFS";
  const starting = element("start").click();
  assert.equal(element("start").disabled, true);
  assert.equal(element("minimum").textContent, "—");
  assert.equal(element("duration").textContent, "0.0 s");
  assert.equal(element("level").value, -120);
  assert.equal(element("status").textContent, "Opening microphone…");
  await starting;

  browser.socket.receive({ type: "ready" });
  assert.equal(element("stop").disabled, false);
  assert.equal(element("status").textContent, "Microphone active.");
});

test("renders the latest level summary", async () => {
  await element("start").click();
  browser.socket.receive({ type: "ready" });
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
  await element("start").click();
  browser.socket.receive({ type: "ready" });
  element("stop").click();
  assert.equal(element("stop").disabled, true);
  assert.equal(element("status").textContent, "Finishing audio measurement…");
  browser.socket.receive({ type: "stopped" });
  assert.equal(element("status").textContent, "Microphone stopped. All captured audio was measured.");
  assert.equal(element("start").disabled, false);
});

test("a failure shows fixed text rather than the server's message and resets the controls", async () => {
  await element("start").click();
  browser.socket.receive({ type: "ready" });
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
  await element("start").click();
  browser.socket.receive({ type: "ready" });
  pagehide();
  assert.equal(browser.track.stopped, true);
  assert.equal(element("start").disabled, false);
});
