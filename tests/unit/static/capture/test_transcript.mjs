import assert from "node:assert/strict";
import { test } from "node:test";
import { Transcript, segments } from "../../../../src/normative_conformance/static/capture/transcript.js";

function element() {
  return { children: [], textContent: "", className: "",
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); } };
}
globalThis.document = { createElement: () => element() };

test("groups adjacent attributed words without assigning missing words to the dominant speaker", () => {
  assert.deepEqual(segments({ final: true, speaker_id: "A", transcript: "Hi yes sure hmm okay",
    words: [
      { text: "Hi", speaker_id: "A" }, { text: "yes", speaker_id: "A" },
      { text: "sure", speaker_id: "B" }, { text: "hmm", speaker_id: null },
      { text: "okay", speaker_id: "PENDING" },
    ] }), [
    { speaker: "A", text: "Hi yes" }, { speaker: "B", text: "sure" },
    { speaker: null, text: "hmm okay" },
  ]);
});

test("partials use the current transcript and preserve unresolved attribution", () => {
  assert.deepEqual(segments({ final: false, transcript: "Hello", speaker_id: "UNKNOWN", words: [] }),
    [{ speaker: null, text: "Hello" }]);
});

test("finals, duplicates and revisions update a single row; late partials cannot replace it", () => {
  const container = element();
  const transcript = new Transcript(container);
  const turn = { turn_order: 0, final: false, revised: false,
    transcript: "Hello", speaker_id: null, words: [] };
  transcript.update(turn);
  const row = container.children[0];
  transcript.update({ ...turn, final: true, speaker_id: "A" });
  transcript.update({ ...turn, final: true, speaker_id: "A" });
  assert.equal(container.children.length, 1);
  assert.equal(row.children[1].children[0].textContent, "Speaker A");
  transcript.update({ ...turn, final: true, revised: true, speaker_id: "B",
    words: [{ text: "Hello", speaker_id: "B" }] });
  transcript.update(turn);
  assert.equal(container.children[0], row);
  assert.equal(row.children[0].textContent, "Speaker labels revised");
  assert.equal(row.children[1].children[0].textContent, "Speaker B");
  transcript.clear();
  assert.deepEqual(container.children, []);
});

test("orders turns and inserts transcript content as text", () => {
  const container = element();
  const transcript = new Transcript(container);
  transcript.update({ turn_order: 2, final: true, revised: false, transcript: "Second", speaker_id: "B", words: [] });
  transcript.update({ turn_order: 1, final: true, revised: false, transcript: "<img src=x onerror=alert(1)>", speaker_id: "A", words: [] });
  assert.equal(container.children.length, 2);
  assert.equal(container.children[0].children[1].children[1].textContent, "<img src=x onerror=alert(1)>");
  assert.equal(container.children[1].children[1].children[1].textContent, "Second");
});
