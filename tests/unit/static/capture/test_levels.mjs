import assert from "node:assert/strict";
import { test } from "node:test";

import { summarize } from "../../../../src/normative_conformance/static/capture/levels.js";

test("summarizes frame levels with the arithmetic mean of dBFS values", () => {
  assert.deepEqual(
    summarize([
      { start_ms: 100, end_ms: 120, dbfs: -20 },
      { start_ms: 120, end_ms: 140, dbfs: -60 },
      { start_ms: 140, end_ms: 145, dbfs: -40 },
    ]),
    { minimum: -60, average: -40, maximum: -20, latest: -40, seconds: 0.145 },
  );
});

test("a single frame is its own minimum, average, and maximum", () => {
  assert.deepEqual(
    summarize([{ start_ms: 0, end_ms: 20, dbfs: -120 }]),
    { minimum: -120, average: -120, maximum: -120, latest: -120, seconds: 0.02 },
  );
});
