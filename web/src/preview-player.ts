/** Matches the server's 120-second PCM limit; worklet storage is <=11.52 MB. */
export const MAX_PREVIEW_FRAMES = 120 * 24000;
export const STREAM_CAPACITY_FRAMES = 2 * 24000;
export const STREAM_POLICY = "mlx-stream-v1";

export type PlaybackPolicy =
  | { name: "complete-clip" }
  | { name: typeof STREAM_POLICY; runtimeFingerprint: string };

/** Unknown policies never opt into early playback. Runtime drift fails at the response. */
export function playbackPolicy(name: unknown, runtime: unknown): PlaybackPolicy {
  if (name !== STREAM_POLICY) return { name: "complete-clip" };
  if (typeof runtime !== "string" || !/^[0-9a-f]{64}$/.test(runtime)) {
    throw new Error("Streaming previews require an exact runtime fingerprint");
  }
  return { name: STREAM_POLICY, runtimeFingerprint: runtime };
}

export interface PlaybackMetrics {
  firstPlaybackMs: number | null;
  firstPCMms: number | null;
  underruns: number;
  playedFrames: number;
  receivedFrames: number;
  maxBufferedFrames: number;
  cache: string;
  runtime: string;
  completed: boolean;
  state: "buffering" | "playing" | "rebuffering" | "draining" | "complete" | "stopped" | "failed";
  bufferedFrames: number;
  playbackClock: "unavailable" | "output-estimate" | "callback-fallback";
  requestId: string;
}

/** Optional acceptance contract; ordinary preview requests keep their existing defaults. */
export interface PlaybackRequest {
  headers?: Record<string, string>;
  body?: { seed: number; instruction_id: string };
  expectedHeaders: Record<string, string>;
  recordedPCM?: { samples: number; sha256: string };
  onResponse?: (response: Response) => void;
  onEOF?: (metrics: PlaybackMetrics, signal: AbortSignal) => Promise<void>;
}

type WorkletMessage =
  | { type: "consumed" | "drained"; frames: number }
  | { type: "started"; contextTime: number }
  | { type: "underrun"; count: number }
  | { type: "state"; state: "playing" | "rebuffering" }
  | { type: "error"; message: string };

/** Setup operations are not abortable themselves; Stop must still settle play. */
function abortable<T>(pending: Promise<T>, signal: AbortSignal): Promise<T> {
  signal.throwIfAborted();
  return new Promise<T>((resolve, reject) => {
    const abort = (): void => reject(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    pending.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

/** Construct in the tap handler: resume happens before any network/module await. */
export class PreviewPlayer {
  private readonly started = performance.now();
  readonly controller = new AbortController();
  readonly context = new AudioContext({ sampleRate: 24000, latencyHint: "interactive" });
  readonly metrics: PlaybackMetrics = {
    firstPlaybackMs: null, firstPCMms: null, underruns: 0, playedFrames: 0,
    receivedFrames: 0, maxBufferedFrames: 0, cache: "", runtime: "", completed: false,
    state: "buffering", bufferedFrames: 0,
    playbackClock: "unavailable", requestId: "",
  };
  private readonly resumed = this.context.resume();
  private node: AudioWorkletNode | null = null;

  stop(): void {
    this.controller.abort();
    this.node?.port.postMessage({ type: "stop" });
    this.node?.disconnect();
    void this.context.close().catch(() => undefined);
  }

  async play(url: string, update: (metrics: PlaybackMetrics) => void, policy: PlaybackPolicy = { name: "complete-clip" }, request?: PlaybackRequest): Promise<PlaybackMetrics> {
    const streaming = policy.name === STREAM_POLICY;
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
    let posted = 0;
    let inputEnded = false;
    let failure: Error | null = null;
    let wakeCredit: (() => void) | null = null;
    let resolveDrain: () => void = () => undefined;
    let rejectDrain: (error: Error) => void = () => undefined;
    const drained = new Promise<void>((resolve, reject) => { resolveDrain = resolve; rejectDrain = reject; });
    void drained.catch(() => undefined);
    const fail = (error: Error): void => {
      failure = error;
      this.metrics.state = "failed";
      this.node?.port.postMessage({ type: "stop" });
      this.node?.disconnect();
      this.controller.abort(error);
      rejectDrain(error);
    };
    const aborted = (): void => {
      failure ??= new DOMException("Preview stopped", "AbortError");
      if (this.metrics.state !== "failed") this.metrics.state = "stopped";
      rejectDrain(failure);
    };
    this.controller.signal.addEventListener("abort", aborted);
    const check = (): void => {
      if (failure) throw failure;
      this.controller.signal.throwIfAborted();
    };
    try {
      if (request?.recordedPCM && streaming) throw new Error("Recorded acceptance requires complete-clip playback");
      await abortable(this.resumed, this.controller.signal);
      check();
      if (this.context.sampleRate !== 24000) throw new Error("This browser cannot create a 24 kHz audio context");
      await abortable(this.context.audioWorklet.addModule("/pcm-worklet.js?preview-v2"), this.controller.signal);
      check();
      const node = new AudioWorkletNode(this.context, "simo-pcm", {
        numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [1],
        processorOptions: streaming ? { bufferUntilEnd: false, streamingPolicy: STREAM_POLICY } : { bufferUntilEnd: true },
      });
      this.node = node;
      node.onprocessorerror = () => fail(new Error("Audio playback processor failed"));
      node.port.onmessage = (event: MessageEvent<WorkletMessage>) => {
        if (this.controller.signal.aborted) return;
        const message = event.data;
        if (message.type === "error") { fail(new Error(message.message)); return; }
        if (message.type === "consumed" || message.type === "drained") {
          if (!Number.isInteger(message.frames) || message.frames < this.metrics.playedFrames || message.frames > posted) {
            fail(new Error("Invalid PCM consumption credit")); return;
          }
          if (message.type === "drained" && (!inputEnded || message.frames !== posted)) {
            fail(new Error("Premature PCM drain")); return;
          }
          this.metrics.playedFrames = message.frames;
          this.metrics.bufferedFrames = posted - message.frames;
          wakeCredit?.();
          if (message.type === "drained") { this.metrics.state = "draining"; resolveDrain(); }
        } else if (message.type === "started") {
          this.metrics.state = "playing";
          const stamp = this.context.getOutputTimestamp?.();
          const estimate = stamp && typeof stamp.performanceTime === "number" && typeof stamp.contextTime === "number" && Number.isFinite(stamp.performanceTime) && Number.isFinite(stamp.contextTime) && stamp.performanceTime > 0 && Number.isFinite(message.contextTime)
            ? stamp.performanceTime + (message.contextTime - stamp.contextTime) * 1000 - this.started : null;
          this.metrics.playbackClock = estimate !== null ? "output-estimate" : "callback-fallback";
          this.metrics.firstPlaybackMs = estimate !== null ? (estimate >= 0 ? estimate : null) : performance.now() - this.started;
        } else if (message.type === "underrun") {
          this.metrics.underruns = message.count;
        } else if (message.type === "state") {
          this.metrics.state = message.state;
        }
        update({ ...this.metrics });
      };
      node.connect(this.context.destination);
      const response = await fetch(url, { method: "POST", cache: "no-store", signal: this.controller.signal,
        headers: request?.headers, body: request?.body ? JSON.stringify(request.body) : undefined });
      if (!response.ok) throw new Error(await response.text());
      if (response.headers.get("X-Sample-Rate") !== "24000" || response.headers.get("X-Sample-Format") !== "s16le" || !response.body) {
        throw new Error("Invalid preview PCM response");
      }
      this.metrics.cache = response.headers.get("X-Simo-Cache") ?? "";
      this.metrics.runtime = response.headers.get("X-Simo-Runtime-Fingerprint") ?? "";
      this.metrics.requestId = response.headers.get("X-Breeze-Request-ID") ?? "";
      for (const [name, value] of Object.entries(request?.expectedHeaders ?? {})) {
        if (response.headers.get(name) !== value) throw new Error(`Playback identity mismatch: ${name}`);
      }
      request?.onResponse?.(response);
      if (streaming && (this.metrics.runtime !== policy.runtimeFingerprint || response.headers.get("X-Simo-Playback-Policy") !== STREAM_POLICY)) {
        throw new Error("Preview runtime or streaming policy changed; refresh the page");
      }
      reader = response.body.getReader();
      // A stream can fail while a large read chunk is waiting for worklet credits.
      // Observe errors independently of the next read; releaseLock/Stop must not
      // replace the original failure during deliberate final cleanup.
      void reader.closed.catch((error: unknown) => {
        if (!this.controller.signal.aborted) fail(error instanceof Error ? error : new Error(String(error)));
      });
      let carry: number | null = null;
      const recordedChunks: Uint8Array[] = [];
      let recordedBytes = 0;
      while (true) {
        check();
        const { value, done } = await abortable(reader.read(), this.controller.signal);
        check();
        if (done) break;
        if (!value.length) continue;
        // Check before allocating/converting an untrusted network chunk. No
        // The total response cap is separate from the streaming credit window.
        if (posted * 2 + value.length + (carry === null ? 0 : 1) > MAX_PREVIEW_FRAMES * 2) {
          throw new Error("Preview exceeds the 120-second buffer limit");
        }
        if (request?.recordedPCM) { recordedChunks.push(value.slice()); recordedBytes += value.length; }
        this.metrics.firstPCMms ??= performance.now() - this.started;
        const bytes: Uint8Array = new Uint8Array(value.length + (carry === null ? 0 : 1));
        if (carry !== null) bytes[0] = carry;
        bytes.set(value, carry === null ? 0 : 1);
        carry = bytes.length % 2 ? bytes[bytes.length - 1] : null;
        const view = new DataView(bytes.buffer);
        const frames = Math.floor(bytes.length / 2);
        for (let offset = 0; offset < frames; offset += 4800) {
          const count = Math.min(4800, frames - offset);
          check();
          while (streaming && posted - this.metrics.playedFrames + count > STREAM_CAPACITY_FRAMES) {
            try {
              await abortable(new Promise<void>(resolve => { wakeCredit = resolve; }), this.controller.signal);
            } finally { wakeCredit = null; }
            check();
          }
          const samples = new Float32Array(count);
          for (let i = 0; i < count; i++) samples[i] = view.getInt16((offset + i) * 2, true) / 32768;
          posted += count;
          this.metrics.receivedFrames = posted;
          this.metrics.bufferedFrames = posted - this.metrics.playedFrames;
          this.metrics.maxBufferedFrames = Math.max(this.metrics.maxBufferedFrames, this.metrics.bufferedFrames);
          node.port.postMessage({ type: "pcm", samples }, [samples.buffer]);
        }
        update({ ...this.metrics });
      }
      if (carry !== null || posted === 0) throw new Error("Incomplete or empty preview PCM");
      if (request?.recordedPCM) {
        if (posted !== request.recordedPCM.samples) throw new Error("Recorded PCM sample count changed");
        const all = new Uint8Array(recordedBytes);
        let offset = 0;
        for (const chunk of recordedChunks) { all.set(chunk, offset); offset += chunk.length; }
        const digest = await abortable(crypto.subtle.digest("SHA-256", all), this.controller.signal);
        const hex = [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
        if (hex !== request.recordedPCM.sha256) throw new Error("Recorded PCM hash changed");
        check();
      }
      // Complete mode stays silent until EOF; streaming may already have played.
      inputEnded = true;
      node.port.postMessage({ type: "end" });
      if (request?.onEOF) await abortable(request.onEOF({ ...this.metrics }, this.controller.signal), this.controller.signal);
      check();
      await drained;
      // Let the last rendered block reach the output device before closing.
      const outputLatency = Number.isFinite(this.context.outputLatency) ? this.context.outputLatency : 0;
      await abortable(new Promise<void>((resolve) => setTimeout(resolve, Math.max(50, outputLatency * 1000 + 20))), this.controller.signal);
      check();
      this.metrics.completed = true;
      this.metrics.state = "complete";
      update({ ...this.metrics });
      return { ...this.metrics };
    } catch (error) {
      if (this.metrics.state !== "stopped") this.metrics.state = "failed";
      throw error;
    } finally {
      this.controller.signal.removeEventListener("abort", aborted);
      // Covers errors before getReader(), including invalid response headers.
      this.controller.abort();
      this.node?.port.postMessage({ type: "stop" });
      this.node?.disconnect();
      // Abort already closes fetch. A stalled underlying cancel must not hold Stop.
      void reader?.cancel().catch(() => undefined);
      reader?.releaseLock();
      if (this.node) this.node.port.onmessage = null;
      await this.context.close().catch(() => undefined);
    }
  }
}
