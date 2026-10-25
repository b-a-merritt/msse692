// Summarize one nonempty `levels` message using the arithmetic mean of frame dBFS values.
export function summarize(frames) {
  const levels = frames.map((frame) => frame.dbfs);
  return {
    minimum: Math.min(...levels),
    average: levels.reduce((total, level) => total + level, 0) / levels.length,
    maximum: Math.max(...levels),
    latest: levels.at(-1),
    seconds: frames.at(-1).end_ms / 1000,
  };
}
