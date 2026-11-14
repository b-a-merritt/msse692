const SAMPLE_RATE = 16000;
const MAX_BUFFERED_BYTES = 32000; // One second of PCM16 at 16 kHz.
const STOP_TIMEOUT_MS = 25000;

// Own one live transcription session: audio graph, WebSocket, and their release.
// Reports status keys; the page maps them to text.
export class CaptureSession {
  #callbacks;
  #closed = false;
  #context;
  #stream;
  #source;
  #node;
  #socket;
  #timer;

  constructor({ onStatus, onCase, onReady, onLevels, onTranscript, onEnd }) {
    this.#callbacks = { onStatus, onCase, onReady, onLevels, onTranscript, onEnd };
  }

  async start(targetSpeakerOrder) {
    if (!navigator.mediaDevices?.getUserMedia || !globalThis.AudioWorkletNode) {
      return this.#fail("unsupported");
    }
    this.#callbacks.onStatus("opening");
    try {
      this.#context = new AudioContext({ sampleRate: SAMPLE_RATE });
      await this.#context.resume();
      this.#stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: SAMPLE_RATE, autoGainControl: false,
          noiseSuppression: false, echoCancellation: false },
      });
      // The page may have been left while the permission prompt was open.
      if (this.#closed) return this.release();
      const track = this.#stream.getAudioTracks()[0];
      const settings = track.getSettings();
      if ([settings.autoGainControl, settings.noiseSuppression, settings.echoCancellation].includes(true)) {
        return this.#fail("processing");
      }
      await this.#context.audioWorklet.addModule("/capture/pcm-worklet.js");
      this.#node = new AudioWorkletNode(this.#context, "pcm-capture", {
        channelCount: 1, channelCountMode: "explicit", outputChannelCount: [1],
      });
      this.#source = this.#context.createMediaStreamSource(this.#stream);
      track.onended = () => this.#fail("ended");
      this.#node.port.onmessage = ({ data }) => this.#onAudio(data);
      let captureCase;
      try {
        const response = await fetch(`/api/v1/cases/${crypto.randomUUID()}/target`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_speaker_order: targetSpeakerOrder }),
        });
        if (!response.ok) return this.#fail("caseSetupFailed");
        captureCase = await response.json();
      } catch {
        return this.#fail("caseSetupFailed");
      }
      if (this.#closed) return this.release();
      this.#callbacks.onCase(captureCase);
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      this.#socket = new WebSocket(`${protocol}//${location.host}/api/v1/capture/audio?case_id=${encodeURIComponent(captureCase.case_id)}`);
      this.#socket.onmessage = ({ data }) => this.#onServerMessage(JSON.parse(data));
      this.#socket.onerror = () => this.#fail("connectionFailed");
      this.#socket.onclose = () => this.#fail("closed");
    } catch (error) {
      this.#fail(error.name === "NotAllowedError" ? "denied" : "startFailed");
    }
  }

  // Ask the worklet to flush its final packet; the server acknowledges with `stopped`.
  stop() {
    if (this.#closed) return;
    this.#callbacks.onStatus("finishing");
    this.#timer = setTimeout(() => this.#fail("unacknowledged"), STOP_TIMEOUT_MS);
    this.#node.port.postMessage("stop");
  }

  // Safe to repeat: always releases resources, including ones acquired late.
  release() {
    clearTimeout(this.#timer);
    this.#source?.disconnect();
    this.#node?.disconnect();
    this.#stream?.getTracks().forEach((track) => track.stop());
    this.#context?.close().catch(() => {});
    this.#socket?.close();
    if (!this.#closed) {
      this.#closed = true;
      this.#callbacks.onEnd();
    }
  }

  #fail(key) {
    if (this.#closed) return;
    this.#callbacks.onStatus(key);
    this.release();
  }

  #onAudio(data) {
    if (this.#socket.readyState !== WebSocket.OPEN || this.#socket.bufferedAmount > MAX_BUFFERED_BYTES) {
      this.#fail("backlog");
    } else if (data.type === "audio") {
      this.#socket.send(data.pcm);
    } else if (data.type === "stopped") {
      this.#socket.send("stop");
    }
  }

  #onServerMessage(message) {
    if (this.#closed) return;
    if (message.type === "ready") {
      this.#source.connect(this.#node);
      this.#node.connect(this.#context.destination);
      this.#callbacks.onStatus("active");
      this.#callbacks.onReady(message);
    } else if (message.type === "levels" && message.frames.length) {
      this.#callbacks.onLevels(message.frames);
    } else if (message.type === "transcript") {
      this.#callbacks.onTranscript(message);
    } else if (message.type === "stopped") {
      this.#callbacks.onStatus("stopped");
      this.release();
    } else if (message.type === "error") {
      this.#fail(message.code ?? "rejected");
    }
  }
}
