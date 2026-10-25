import assert from "node:assert/strict";
import test from "node:test";

let Processor;
globalThis.sampleRate = 16000;
globalThis.AudioWorkletProcessor = class {
  constructor() { this.messages = []; this.port = { postMessage: (m) => this.messages.push(m) }; }
};
globalThis.registerProcessor = (name, implementation) => {
  assert.equal(name, "pcm-capture");
  Processor = implementation;
};
await import("../../../src/normative_conformance/static/pcm-worklet.js");

test("emits 100 ms PCM16 packets across render quanta and flushes the exact tail", () => {
  const processor = new Processor();
  assert.equal(processor.process([]), true);
  for (let i = 0; i < 12; i++) processor.process([[new Float32Array(128).fill(0.5)]]);
  assert.equal(processor.messages.length, 0); // 1536 of 1600 samples
  processor.process([[new Float32Array(128).fill(-0.5)]]);
  const first = processor.messages[0];
  assert.equal(first.type, "audio");
  assert.equal(first.pcm.byteLength, 3200);
  const view = new DataView(first.pcm);
  assert.equal(view.getInt16(0, true), 16384);
  assert.equal(view.getInt16(3072, true), -16384);
  processor.port.onmessage({ data: "stop" });
  assert.equal(processor.messages[1].pcm.byteLength, 128); // 64 samples, no padding
  assert.equal(new DataView(processor.messages[1].pcm).getInt16(0, true), -16384);
  assert.deepEqual(processor.messages[2], { type: "stopped" });
  assert.equal(processor.process([[new Float32Array(128)]]), false);
});

test("clamps amplitudes and writes signed little-endian samples", () => {
  const processor = new Processor();
  processor.process([[new Float32Array([-2, -1, 0, 1, 2])]]);
  processor.port.onmessage({ data: "stop" });
  assert.deepEqual([...new Uint8Array(processor.messages[0].pcm)], [
    0, 128, 0, 128, 0, 0, 255, 127, 255, 127,
  ]);
});

test("empty capture stops without fabricating an audio packet", () => {
  const processor = new Processor();
  processor.port.onmessage({ data: "stop" });
  assert.deepEqual(processor.messages, [{ type: "stopped" }]);
});

test("rejects an incorrect audio context sample rate", () => {
  globalThis.sampleRate = 48000;
  assert.throws(() => new Processor(), /16 kHz/);
  globalThis.sampleRate = 16000;
});
