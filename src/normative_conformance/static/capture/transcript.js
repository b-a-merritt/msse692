function speaker(label) {
  return !label || ["PENDING", "UNKNOWN"].includes(label) ? null : label;
}

// Word labels take precedence; missing attribution stays unresolved.
export function segments(turn) {
  if (!turn.final || !turn.words.length) {
    return [{ speaker: speaker(turn.speaker_id), text: turn.transcript }];
  }
  const groups = [];
  for (const word of turn.words) {
    const label = speaker(word.speaker_id);
    const last = groups.at(-1);
    if (last && last.speaker === label) last.text += ` ${word.text}`;
    else groups.push({ speaker: label, text: word.text });
  }
  return groups;
}

export class Transcript {
  #container;
  #turns = new Map();

  constructor(container) { this.#container = container; }

  clear() {
    this.#turns.clear();
    this.#container.replaceChildren();
  }

  update(turn) {
    const existing = this.#turns.get(turn.turn_order);
    // A late partial cannot overwrite finalized or corrected speech.
    if (existing?.turn.final && !turn.final) return;
    const row = existing?.row ?? document.createElement("li");
    const follow = this.#container.scrollHeight - this.#container.scrollTop - this.#container.clientHeight < 32;
    const status = document.createElement("span");
    status.className = "turn-status";
    status.textContent = turn.revised ? "Speaker labels revised" : turn.final ? "Final" : "Listening…";
    row.className = turn.final ? "turn" : "turn partial";
    row.replaceChildren(status);
    for (const group of segments(turn)) {
      const line = document.createElement("p");
      const label = document.createElement("strong");
      label.textContent = group.speaker === null ? "Unassigned" : `Speaker ${group.speaker}`;
      const text = document.createElement("span");
      text.textContent = group.text;
      line.append(label, text);
      row.append(line);
    }
    this.#turns.set(turn.turn_order, { turn, row });
    const rows = [...this.#turns.entries()].sort(([a], [b]) => a - b).map(([, value]) => value.row);
    this.#container.replaceChildren(...rows);
    if (follow) this.#container.scrollTop = this.#container.scrollHeight;
  }
}
