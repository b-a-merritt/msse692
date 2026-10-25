// Browser API doubles for the capture tests. They record what the code under test
// did; each test supplies its own scenario through `browser` and fake events.
export const browser = {};

export function resetBrowser() {
  const track = { stopped: false, stop() { this.stopped = true; }, getSettings: () => ({}) };
  browser.track = track;
  browser.stream = { getTracks: () => [track], getAudioTracks: () => [track] };
  browser.permission = async () => browser.stream;
  browser.constraints = undefined;
  browser.context = undefined;
  browser.source = undefined;
  browser.node = undefined;
  browser.socket = undefined;
}

globalThis.location = { protocol: "http:", host: "localhost:8000" };

globalThis.AudioContext = class {
  constructor(options) {
    browser.context = this;
    this.options = options;
    this.state = "running";
    this.destination = {};
    this.modules = [];
    this.audioWorklet = { addModule: async (url) => { this.modules.push(url); } };
  }
  async resume() {}
  async close() { this.state = "closed"; }
  createMediaStreamSource(stream) {
    browser.source = { stream, target: null, connect(target) { this.target = target; }, disconnect() { this.target = null; } };
    return browser.source;
  }
};

globalThis.AudioWorkletNode = class {
  constructor(context, name) {
    browser.node = this;
    this.name = name;
    this.target = null;
    this.port = { sent: [], postMessage(message) { this.sent.push(message); } };
  }
  connect(target) { this.target = target; }
  disconnect() { this.target = null; }
};

globalThis.WebSocket = class {
  static OPEN = 1;
  constructor(url) {
    browser.socket = this;
    this.url = url;
    this.readyState = 1;
    this.bufferedAmount = 0;
    this.sent = [];
  }
  send(data) { this.sent.push(data); }
  close() { this.readyState = 3; }
  receive(message) { this.onmessage({ data: JSON.stringify(message) }); }
};

Object.defineProperty(globalThis.navigator, "mediaDevices", {
  configurable: true,
  value: {
    getUserMedia: async (constraints) => {
      browser.constraints = constraints;
      return browser.permission();
    },
  },
});
