import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";

import { browser, resetBrowser } from "../browser.mjs";
import { CaptureSession } from "../../../../src/normative_conformance/static/capture/session.js";
import { STATUS } from "../../../../src/normative_conformance/static/capture/status.js";

function record() {
  const events = { statuses: [], ready: 0, levels: [], transcripts: [], cases: [], ended: 0 };
  const session = new CaptureSession({
    onStatus: (key) => {
      assert.ok(Object.hasOwn(STATUS, key), `missing status text for ${key}`);
      events.statuses.push(key);
    },
    onCase: (record) => events.cases.push(record),
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
afterEach(() => mock.restoreAll());

test("opens unprocessed 16 kHz audio and connects the graph only when the server is ready", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
  assert.deepEqual(browser.context.options, { sampleRate: 16000 });
  assert.deepEqual(browser.constraints.audio, { channelCount: 1, sampleRate: 16000,
    autoGainControl: false, noiseSuppression: false, echoCancellation: false });
  assert.deepEqual(browser.context.modules, ["/capture/pcm-worklet.js"]);
  assert.equal(browser.socket.url, "ws://localhost:8000/api/v1/capture/audio?case_id=capture-test");
  assert.equal(browser.source.target, null);
  assert.deepEqual(events.statuses, ["opening"]);

  browser.socket.receive({ type: "ready" });
  assert.equal(browser.source.target, browser.node);
  assert.equal(browser.node.target, browser.context.destination);
  assert.deepEqual(events.statuses, ["opening", "active"]);
  assert.equal(events.ready, 1);
});

test("forwards nonempty level messages", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
  browser.socket.receive({ type: "ready" });
  browser.socket.receive({ type: "levels", frames: [] });
  browser.socket.receive({ type: "levels", frames: [{ start_ms: 0, end_ms: 20, dbfs: -30 }] });
  assert.deepEqual(events.levels, [[{ start_ms: 0, end_ms: 20, dbfs: -30 }]]);
});

test("stop flushes the final packet and releases only after the server acknowledges", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
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
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { session, events } = record();
  await session.start(1);
  browser.socket.receive({ type: "ready" });
  session.stop();
  t.mock.timers.tick(24999);
  assert.equal(browser.track.stopped, false);
  t.mock.timers.tick(1);
  assertReleased();
  assert.equal(events.statuses.at(-1), "unacknowledged");
});

test("a send backlog above one second stops capture with a gap", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
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
    mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
    const { session, events } = record();
    await session.start(1);
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
    await session.start(1);
    assert.equal(browser.context.state, "closed");
    assert.deepEqual(events.statuses, ["opening", expected]);
    assert.equal(events.ended, 1);
  });
}

test("enabled audio processing rejects capture before connecting", async () => {
  browser.track.getSettings = () => ({ autoGainControl: true });
  const { session, events } = record();
  await session.start(1);
  assert.equal(browser.socket, undefined);
  assertReleased();
  assert.equal(events.statuses.at(-1), "processing");
});

test("a browser without microphone capture is unsupported", async () => {
  const mediaDevices = navigator.mediaDevices;
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
  try {
    const { session, events } = record();
    await session.start(1);
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
  const starting = session.start(1);
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
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
  session.release();
  session.stop();
  assert.deepEqual(browser.node.port.sent, []);
  assert.deepEqual(events.statuses, ["opening"]);
});

test("forwards final speaker revisions before reporting a completed stop", async () => {
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
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
  mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ case_id: "capture-test" }) }));
  const { session, events } = record();
  await session.start(1);
  browser.socket.receive({ type: "error", code: "providerAuth", message: "private details" });
  assert.equal(events.statuses.at(-1), "providerAuth");
  assertReleased();
});

test("creates a fresh case with the selected order before each capture", async () => {
  const ids = ["first-case", "second-case"];
  mock.method(crypto, "randomUUID", () => ids.shift());
  const requests = [];
  mock.method(globalThis, "fetch", async (url, options) => {
    requests.push({ url, options });
    assert.equal(browser.socket, undefined);
    return { ok: true, json: async () => ({ case_id: url.split("/").at(-2) }) };
  });
  const first = record();
  await first.session.start(2);
  assert.deepEqual(first.events.cases, [{ case_id: "first-case" }]);
  assert.equal(browser.socket.url, "ws://localhost:8000/api/v1/capture/audio?case_id=first-case");
  first.session.release();
  resetBrowser();
  const second = record();
  await second.session.start(1);
  assert.equal(browser.socket.url, "ws://localhost:8000/api/v1/capture/audio?case_id=second-case");
  assert.deepEqual(requests, [
    { url: "/api/v1/cases/first-case/target", options: { method: "PUT",
      headers: { "Content-Type": "application/json" }, body: '{"target_speaker_order":2}' } },
    { url: "/api/v1/cases/second-case/target", options: { method: "PUT",
      headers: { "Content-Type": "application/json" }, body: '{"target_speaker_order":1}' } },
  ]);
  second.session.release();
});

for (const [name, response] of [
  ["HTTP failure", async () => ({ ok: false })],
  ["network failure", async () => { throw new Error("private details"); }],
]) {
  test(`case setup ${name} releases the microphone without opening a socket`, async () => {
    mock.method(globalThis, "fetch", response);
    const { session, events } = record();
    await session.start(2);
    assertReleased();
    assert.equal(browser.socket, undefined);
    assert.deepEqual(events.cases, []);
    assert.deepEqual(events.statuses, ["opening", "caseSetupFailed"]);
    assert.equal(events.ended, 1);
  });
}

test("leaving during case creation prevents a late connection", async () => {
  let finishRequest;
  let startedRequest;
  const requested = new Promise((resolve) => { startedRequest = resolve; });
  mock.method(globalThis, "fetch", () => {
    startedRequest();
    return new Promise((resolve) => { finishRequest = resolve; });
  });
  const { session, events } = record();
  const starting = session.start(1);
  await requested;
  session.release();
  finishRequest({ ok: true, json: async () => ({ case_id: "abandoned-case" }) });
  await starting;
  assertReleased();
  assert.equal(browser.socket, undefined);
  assert.deepEqual(events.cases, []);
  assert.equal(events.ended, 1);
});
