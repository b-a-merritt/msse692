import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { browser, resetBrowser } from "../browser.mjs";
import { CaptureSession } from "../../../../src/normative_conformance/static/capture/session.js";
import { STATUS } from "../../../../src/normative_conformance/static/capture/status.js";

function record() {
  const events = { statuses: [], ready: 0, levels: [], transcripts: [], ended: 0 };
  const session = new CaptureSession({
    onStatus: (key) => {
      assert.ok(Object.hasOwn(STATUS, key), `missing status text for ${key}`);
      events.statuses.push(key);
    },
    onReady: () => { events.ready += 1; },
    onLevels: (frames) => events.levels.push(frames),
    onTranscript: (message) => events.transcripts.push(message),
    onEnd: () => { events.ended += 1; },
  });
  return { session, events };
}

function assertReleased() {
  assert.equal(browser.track.stopped, true);
  assert.equal(browser.context.state, "closed");
}

beforeEach(resetBrowser);

test("opens unprocessed 16 kHz audio and connects the graph only when the server is ready", async () => {
  const { session, events } = record();
  await session.start();
  assert.deepEqual(browser.context.options, { sampleRate: 16000 });
  assert.deepEqual(browser.constraints.audio, { channelCount: 1, sampleRate: 16000,
    autoGainControl: false, noiseSuppression: false, echoCancellation: false });
  assert.deepEqual(browser.context.modules, ["/capture/pcm-worklet.js"]);
  assert.equal(browser.socket.url, "ws://localhost:8000/api/v1/capture/audio");
  assert.equal(browser.source.target, null);
  assert.deepEqual(events.statuses, ["opening"]);

  browser.socket.receive({ type: "ready" });
  assert.equal(browser.source.target, browser.node);
  assert.equal(browser.node.target, browser.context.destination);
  assert.deepEqual(events.statuses, ["opening", "active"]);
  assert.equal(events.ready, 1);
});

test("forwards nonempty level messages", async () => {
  const { session, events } = record();
  await session.start();
  browser.socket.receive({ type: "ready" });
  browser.socket.receive({ type: "levels", frames: [] });
  browser.socket.receive({ type: "levels", frames: [{ start_ms: 0, end_ms: 20, dbfs: -30 }] });
  assert.deepEqual(events.levels, [[{ start_ms: 0, end_ms: 20, dbfs: -30 }]]);
});

test("stop flushes the final packet and releases only after the server acknowledges", async () => {
  const { session, events } = record();
  await session.start();
  browser.socket.receive({ type: "ready" });
  session.stop();
  assert.deepEqual(browser.node.port.sent, ["stop"]);
  const pcm = new ArrayBuffer(160);
  browser.node.port.onmessage({ data: { type: "audio", pcm } });
  browser.node.port.onmessage({ data: { type: "stopped" } });
  assert.deepEqual(browser.socket.sent, [pcm, "stop"]);
  assert.equal(browser.track.stopped, false);

  browser.socket.receive({ type: "stopped" });
  assertReleased();
  browser.socket.onclose();
  assert.deepEqual(events.statuses, ["opening", "active", "finishing", "stopped"]);
  assert.equal(events.ended, 1);
});

test("an unacknowledged stop times out and releases the microphone", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { session, events } = record();
  await session.start();
  browser.socket.receive({ type: "ready" });
  session.stop();
  t.mock.timers.tick(24999);
  assert.equal(browser.track.stopped, false);
  t.mock.timers.tick(1);
  assertReleased();
  assert.equal(events.statuses.at(-1), "unacknowledged");
});

test("a send backlog above one second stops capture with a gap", async () => {
  const { session, events } = record();
  await session.start();
  browser.socket.receive({ type: "ready" });
  browser.socket.bufferedAmount = 32001;
  browser.node.port.onmessage({ data: { type: "audio", pcm: new ArrayBuffer(3200) } });
  assert.deepEqual(browser.socket.sent, []);
  assertReleased();
  assert.equal(events.statuses.at(-1), "backlog");
});

for (const [name, fault, expected] of [
  ["a server error", () => browser.socket.receive({ type: "error", message: "Expected PCM audio or stop" }), "rejected"],
  ["a connection error", () => browser.socket.onerror(), "connectionFailed"],
  ["an early connection close", () => browser.socket.onclose(), "closed"],
  ["a disconnected microphone", () => browser.track.onended(), "ended"],
]) {
  test(`${name} releases the session once`, async () => {
    const { session, events } = record();
    await session.start();
    browser.socket.receive({ type: "ready" });
    fault();
    browser.socket.onclose();
    assertReleased();
    assert.deepEqual(events.statuses, ["opening", "active", expected]);
    assert.equal(events.ended, 1);
  });
}

for (const [name, error, expected] of [
  ["denied permission", new DOMException("Permission denied by system", "NotAllowedError"), "denied"],
  ["another start error", new DOMException("Device busy", "NotReadableError"), "startFailed"],
]) {
  test(`${name} reports ${expected} and closes the audio context`, async () => {
    browser.permission = async () => { throw error; };
    const { session, events } = record();
    await session.start();
    assert.equal(browser.context.state, "closed");
    assert.deepEqual(events.statuses, ["opening", expected]);
    assert.equal(events.ended, 1);
  });
}

test("enabled audio processing rejects capture before connecting", async () => {
  browser.track.getSettings = () => ({ autoGainControl: true });
  const { session, events } = record();
  await session.start();
  assert.equal(browser.socket, undefined);
  assertReleased();
  assert.equal(events.statuses.at(-1), "processing");
});

test("a browser without microphone capture is unsupported", async () => {
  const mediaDevices = navigator.mediaDevices;
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
  try {
    const { session, events } = record();
    await session.start();
    assert.equal(browser.context, undefined);
    assert.deepEqual(events.statuses, ["unsupported"]);
    assert.equal(events.ended, 1);
  } finally {
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: mediaDevices });
  }
});

test("releasing during the permission prompt stops the late stream without more status", async () => {
  let grant;
  browser.permission = () => new Promise((resolve) => { grant = resolve; });
  const { session, events } = record();
  const starting = session.start();
  await Promise.resolve();
  session.release();
  grant(browser.stream);
  await starting;
  assertReleased();
  assert.equal(browser.socket, undefined);
  assert.deepEqual(events.statuses, ["opening"]);
  assert.equal(events.ended, 1);
});

test("stop after release does nothing", async () => {
  const { session, events } = record();
  await session.start();
  session.release();
  session.stop();
  assert.deepEqual(browser.node.port.sent, []);
  assert.deepEqual(events.statuses, ["opening"]);
});

test("forwards final speaker revisions before reporting a completed stop", async () => {
  const { session, events } = record();
  await session.start();
  browser.socket.receive({ type: "ready" });
  session.stop();
  const correction = { type: "transcript", turn_order: 0, final: true, revised: true,
    transcript: "Hello", speaker_id: "B", words: [] };
  browser.socket.receive(correction);
  assert.deepEqual(events.transcripts, [correction]);
  assert.equal(events.ended, 0);
  browser.socket.receive({ type: "stopped" });
  assert.equal(events.ended, 1);
});

test("maps a provider error to fixed status text and releases the microphone", async () => {
  const { session, events } = record();
  await session.start();
  browser.socket.receive({ type: "error", code: "providerAuth", message: "private details" });
  assert.equal(events.statuses.at(-1), "providerAuth");
  assertReleased();
});
