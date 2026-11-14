class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    if (sampleRate !== 16000) throw new Error("Capture requires a 16 kHz audio context");
    this.buffer = new ArrayBuffer(3200);
    this.view = new DataView(this.buffer);
    this.count = 0;
    this.stopped = false;
    this.port.onmessage = ({ data }) => {
      if (data === "stop") {
        this.stopped = true;
        this.flush();
        this.port.postMessage({ type: "stopped" });
      }
    };
  }

  flush() {
    if (!this.count) return;
    const pcm = this.buffer.slice(0, this.count * 2);
    this.port.postMessage({ type: "audio", pcm }, [pcm]);
    this.count = 0;
  }

  process(inputs) {
    if (this.stopped) return false;
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (const value of channel) {
      const sample = Math.max(-32768, Math.min(32767, Math.round(value * 32768)));
      this.view.setInt16(this.count * 2, sample, true);
      this.count += 1;
      if (this.count === 1600) this.flush();
    }
    // Outputs remain silent: the microphone is never played through the speakers.
    return true;
  }
}
registerProcessor("pcm-capture", PCMProcessor);
