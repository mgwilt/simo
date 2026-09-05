/** CPU-only integration: actual player + processor, simulated ports/render clock, no device. */
import { setImmediate as nextTurn } from "node:timers/promises";
import { PreviewPlayer, playbackPolicy } from "../../src/preview-player.ts";

let Processor;
let constructingPort;
export const TEST_RUNTIME = "a".repeat(64);
export const STREAM_HEADERS = {
  "X-Sample-Rate": "24000", "X-Sample-Format": "s16le", "X-Simo-Cache": "MISS",
  "X-Simo-Runtime-Fingerprint": TEST_RUNTIME, "X-Simo-Playback-Policy": "mlx-stream-v1",
};

export async function playbackHarness({ creditDelayMs = 0, holdCredits = false } = {}) {
  const names = ["performance", "setTimeout", "clearTimeout", "AudioContext", "AudioWorkletNode",
    "AudioWorkletProcessor", "registerProcessor", "currentTime", "fetch"];
  const saved = new Map(names.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  let now = 0, sequence = 0;
  const messages = [], timers = new Map(), nodes = [];
  globalThis.performance = { now: () => now };
  globalThis.setTimeout = (callback, ms = 0) => { const id = ++sequence; timers.set(id, { at: now + ms, callback }); return id; };
  globalThis.clearTimeout = id => timers.delete(id);
  globalThis.currentTime = 0;
  if (!Processor) {
    globalThis.AudioWorkletProcessor = class { constructor() { this.port = constructingPort; } };
    globalThis.registerProcessor = (_name, constructor) => { Processor = constructor; };
    await import("../../public/pcm-worklet.js");
  }
  globalThis.AudioContext = class {
    sampleRate = 24000;
    outputLatency = 0;
    destination = {};
    closed = false;
    audioWorklet = { addModule: async () => undefined };
    resume() { return Promise.resolve(); }
    close() { this.closed = true; return Promise.resolve(); }
    getOutputTimestamp() { return { contextTime: now / 1000, performanceTime: now }; }
  };
  globalThis.AudioWorkletNode = class {
    connected = false;
    alive = true;
    posted = 0;
    acknowledged = 0;
    maxOutstanding = 0;
    maxRing = 0;
    firstRenderMs = null;
    renderedFrames = 0;
    rendered = [];
    constructor(context, _name, options) {
      this.context = context;
      this.options = options;
      this.port = { onmessage: null, postMessage: (data, transfer = []) => {
        if (data.type === "pcm") {
          this.posted += data.samples.length;
          this.maxOutstanding = Math.max(this.maxOutstanding, this.posted - this.acknowledged);
        }
        const copy = structuredClone(data, { transfer });
        messages.push({ at: now, deliver: () => {
          this.processor.port.onmessage({ data: copy });
          this.maxRing = Math.max(this.maxRing, this.processor.queue.size);
        } });
      } };
      constructingPort = { onmessage: null, postMessage: data => {
        const credit = data.type === "consumed" || data.type === "drained";
        if (credit && holdCredits) return;
        const copy = structuredClone(data);
        messages.push({ at: now + (credit ? creditDelayMs : 0), deliver: () => {
          if (credit) this.acknowledged = copy.frames;
          this.port.onmessage?.({ data: copy });
        } });
      } };
      this.processor = new Processor(options);
      nodes.push(this);
    }
    connect() { this.connected = true; }
    disconnect() { this.connected = false; }
  };

  async function flush() {
    // setImmediate uses the real Node event loop, independent of our virtual timers.
    for (let iteration = 0; iteration < 3; iteration++) {
      for (let index = 0; index < messages.length;) {
        if (messages[index].at <= now) messages.splice(index, 1)[0].deliver();
        else index++;
      }
      for (const [id, timer] of timers) if (timer.at <= now) { timers.delete(id); timer.callback(); }
      await nextTurn();
    }
  }
  async function step() {
    await flush();
    globalThis.currentTime = now / 1000;
    for (const node of nodes) {
      if (!node.alive || !node.connected || node.context.closed) continue;
      const output = new Float32Array(128), before = node.processor.queue.consumed;
      node.alive = node.processor.process([], [[output]]);
      const count = node.processor.queue.consumed - before;
      if (count) {
        node.firstRenderMs ??= now;
        node.rendered.push(output.slice(0, count));
        node.renderedFrames += count;
      }
    }
    await flush();
    now += 128 / 24000 * 1000;
  }
  function start({ headers = STREAM_HEADERS, policy = playbackPolicy("mlx-stream-v1", TEST_RUNTIME), cancelNever = false } = {}) {
    let controller, terminal = false;
    const run = { settled: false, result: null, error: null, aborted: false, cancelled: false, updates: [] };
    const stream = new ReadableStream({
      start(value) { controller = value; },
      cancel() { run.cancelled = true; terminal = true; return cancelNever ? new Promise(() => {}) : undefined; },
    });
    globalThis.fetch = async (_url, { signal }) => {
      signal.addEventListener("abort", () => {
        run.aborted = true;
        if (!terminal) { terminal = true; controller.error(signal.reason); }
      }, { once: true });
      return new Response(stream, { headers });
    };
    run.player = new PreviewPlayer();
    run.promise = run.player.play("/preview", metrics => run.updates.push(metrics), policy);
    run.promise.then(result => { run.result = result; run.settled = true; }, error => { run.error = error; run.settled = true; });
    run.enqueue = bytes => controller.enqueue(bytes);
    run.end = () => { terminal = true; controller.close(); };
    run.fail = error => { terminal = true; controller.error(error); };
    run.node = () => nodes.at(-1);
    return run;
  }
  async function finish(run, timeoutMs = 125000) {
    const deadline = now + timeoutMs;
    while (!run.settled && now <= deadline) await step();
    if (!run.settled) throw new Error("Scripted player did not settle");
    return run;
  }
  function restore() {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
  return { start, step, flush, finish, restore, get nowMs() { return now; } };
}

export function pcmPattern(frames) {
  const bytes = new Uint8Array(frames * 2), view = new DataView(bytes.buffer);
  for (let index = 0; index < frames; index++) view.setInt16(index * 2, (index % 65536) - 32768, true);
  return bytes;
}

export function exactRenderedPCM(node, bytes) {
  if (node.renderedFrames * 2 !== bytes.length) return false;
  const source = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let index = 0;
  for (const block of node.rendered) for (const sample of block) {
    if (sample !== source.getInt16(index++ * 2, true) / 32768) return false;
  }
  return true;
}
