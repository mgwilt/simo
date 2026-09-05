import assert from "node:assert/strict";
import test from "node:test";
import { MAX_PREVIEW_FRAMES, PreviewPlayer } from "../src/preview-player.ts";

const tick = () => new Promise(resolve => setImmediate(resolve));
const never = () => new Promise(() => {});

function setup({ resume = false, module = false, acknowledge = true } = {}) {
  let node;
  let signal;
  let closed = 0;
  const samples = [];
  const messages = [];
  globalThis.AudioContext = class {
    sampleRate = 24000;
    destination = {};
    audioWorklet = { addModule: () => module ? never() : Promise.resolve() };
    resume() { return resume ? never() : Promise.resolve(); }
    close() { closed++; return Promise.resolve(); }
  };
  globalThis.AudioWorkletNode = class {
    received = 0;
    port = {
      onmessage: null,
      postMessage: message => {
        messages.push(message.type);
        if (message.type === "pcm") {
          samples.push(...message.samples);
          this.received += message.samples.length;
        }
        if (message.type === "end" && acknowledge) queueMicrotask(() => {
          this.port.onmessage?.({ data: { type: "started", contextTime: 0 } });
          this.port.onmessage?.({ data: { type: "drained", frames: this.received } });
        });
      },
    };
    constructor(_context, _name, options) { node = this; this.options = options; }
    connect() {}
    disconnect() {}
  };
  function response(chunks, headers = { "X-Sample-Rate": "24000", "X-Sample-Format": "s16le" }) {
    globalThis.fetch = async (_url, options) => {
      signal = options.signal;
      return new Response(new ReadableStream({ start(controller) {
        for (const chunk of chunks) controller.enqueue(new Uint8Array(chunk));
        controller.close();
      } }), { headers });
    };
  }
  response([[0, 0]]);
  function streaming() {
    let controller;
    globalThis.fetch = async (_url, options) => {
      signal = options.signal;
      return new Response(new ReadableStream({ start(value) { controller = value; } }), {
        headers: { "X-Sample-Rate": "24000", "X-Sample-Format": "s16le", "X-Simo-Cache": "MISS" },
      });
    };
    return { get controller() { return controller; } };
  }
  return { response, streaming, samples, messages, get signal() { return signal; }, get closed() { return closed; }, get node() { return node; } };
}

for (const stage of ["resume", "module"]) {
  test(`Stop settles during stalled ${stage}`, { timeout: 1000 }, async () => {
    const env = setup({ [stage]: true });
    const player = new PreviewPlayer();
    const playing = player.play("/preview", () => {});
    await tick(); player.stop();
    await assert.rejects(playing, { name: "AbortError" });
    assert.ok(env.closed > 0);
  });
}

test("invalid metadata aborts upstream even before reader creation", async () => {
  const env = setup(); env.response([[0, 0]], { "X-Sample-Rate": "48000" });
  const player = new PreviewPlayer();
  await assert.rejects(player.play("/preview", () => {}), /Invalid preview PCM/);
  assert.equal(env.signal.aborted, true); assert.ok(env.closed > 0);
});

test("odd network boundaries preserve little-endian PCM and complete after drain", async () => {
  const env = setup(); env.response([[0], [128, 255], [127, 0, 0]]);
  const player = new PreviewPlayer();
  const metrics = await player.play("/preview", () => {});
  assert.deepEqual(env.samples, [-1, 32767 / 32768, 0]);
  assert.equal(metrics.completed, true); assert.equal(metrics.playedFrames, 3);
  assert.equal(metrics.receivedFrames, 3);
  assert.deepEqual(env.node.options.processorOptions, { bufferUntilEnd: true });
});

test("truncated sample fails instead of claiming completion", async () => {
  const env = setup(); env.response([[0, 0, 1]]);
  const player = new PreviewPlayer();
  await assert.rejects(player.play("/preview", () => {}), /Incomplete/);
  assert.equal(player.metrics.completed, false); assert.equal(env.signal.aborted, true);
  assert.equal(env.messages.includes("end"), false);
});

test("exact 120-second clip buffers without the old two-second credit deadlock", { timeout: 2000 }, async () => {
  const env = setup(); env.response([new Uint8Array(MAX_PREVIEW_FRAMES * 2)]);
  const player = new PreviewPlayer();
  const metrics = await player.play("/preview", () => {});
  assert.equal(env.samples.length, MAX_PREVIEW_FRAMES);
  assert.equal(metrics.maxBufferedFrames, MAX_PREVIEW_FRAMES);
  assert.equal(metrics.completed, true);
});

test("one frame over the limit is rejected before copying or posting PCM", async () => {
  const env = setup(); env.response([new Uint8Array((MAX_PREVIEW_FRAMES + 1) * 2)]);
  const player = new PreviewPlayer();
  await assert.rejects(player.play("/preview", () => {}), /120-second/);
  assert.equal(env.samples.length, 0);
  assert.equal(env.messages.includes("end"), false);
  assert.equal(env.signal.aborted, true);
});

test("delayed arrivals buffer silently and report progress until validated EOF", async () => {
  const env = setup(); const stream = env.streaming();
  const player = new PreviewPlayer(); const updates = [];
  const playing = player.play("/preview", metrics => updates.push(metrics));
  await tick();
  stream.controller.enqueue(new Uint8Array(24000 * 2)); await tick();
  stream.controller.enqueue(new Uint8Array(24000 * 4)); await tick();
  assert.equal(player.metrics.receivedFrames, 72000);
  assert.equal(player.metrics.firstPlaybackMs, null);
  assert.equal(env.messages.includes("end"), false);
  assert.ok(updates.length >= 2);
  assert.ok(updates.every(metrics => metrics.firstPlaybackMs === null));
  stream.controller.close();
  const metrics = await playing;
  assert.equal(metrics.playedFrames, 72000);
  assert.equal(metrics.cache, "MISS");
  assert.equal(metrics.underruns, 0);
});

test("failed partial response never starts playback", async () => {
  const env = setup(); const stream = env.streaming();
  const player = new PreviewPlayer(); const playing = player.play("/preview", () => {});
  await tick(); stream.controller.enqueue(new Uint8Array(12000)); await tick();
  stream.controller.error(new Error("Connection lost"));
  await assert.rejects(playing, /Connection lost/);
  assert.equal(env.messages.includes("end"), false);
  assert.equal(player.metrics.firstPlaybackMs, null);
});

test("Stop after partial buffering settles and an immediate cached retry completes", async () => {
  const env = setup(); const stream = env.streaming();
  const player = new PreviewPlayer(); const playing = player.play("/preview", () => {});
  await tick(); stream.controller.enqueue(new Uint8Array(12000)); await tick();
  player.stop(); await assert.rejects(playing, { name: "AbortError" });
  assert.equal(env.messages.includes("end"), false);
  assert.equal(env.signal.aborted, true);
  env.response([[1, 0]], { "X-Sample-Rate": "24000", "X-Sample-Format": "s16le", "X-Simo-Cache": "HIT" });
  const retry = await new PreviewPlayer().play("/preview", () => {});
  assert.equal(retry.completed, true); assert.equal(retry.cache, "HIT");
  assert.equal(retry.receivedFrames, 1);
});

test("empty EOF remains silent and fails", async () => {
  const env = setup(); env.response([]);
  const player = new PreviewPlayer();
  await assert.rejects(player.play("/preview", () => {}), /empty/);
  assert.equal(env.messages.includes("end"), false);
});

test("Stop settles while waiting for drain", { timeout: 1000 }, async () => {
  setup({ acknowledge: false });
  const player = new PreviewPlayer();
  const playing = player.play("/preview", () => {});
  await tick(); player.stop();
  await assert.rejects(playing, { name: "AbortError" });
});

test("Stop aborts a stalled response reader", { timeout: 1000 }, async () => {
  setup();
  globalThis.fetch = async (_url, { signal }) => new Response(new ReadableStream({
    start(controller) { signal.addEventListener("abort", () => controller.error(signal.reason), { once: true }); },
  }), { headers: { "X-Sample-Rate": "24000", "X-Sample-Format": "s16le" } });
  const player = new PreviewPlayer();
  const playing = player.play("/preview", () => {});
  await tick(); player.stop();
  await assert.rejects(playing, { name: "AbortError" });
});

test("processor failure during a pending read keeps its error reason", async () => {
  const env = setup(); env.streaming();
  const player = new PreviewPlayer(); const playing = player.play("/preview", () => {});
  await tick();
  env.node.port.onmessage({ data: { type: "error", message: "PCM buffer overflow" } });
  await assert.rejects(playing, { name: "Error", message: "PCM buffer overflow" });
  assert.equal(env.messages.includes("end"), false);
});

test("recorded body hash and full count validate before EOF across odd chunks", async () => {
  const env = setup(); env.response([[1], [0, 2], [0]]);
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", new Uint8Array([1, 0, 2, 0])))].map(value => value.toString(16).padStart(2, "0")).join("");
  const result = await new PreviewPlayer().play("/recorded", () => {}, { name: "complete-clip" }, { expectedHeaders: {}, recordedPCM: { samples: 2, sha256: digest } });
  assert.equal(result.completed, true); assert.equal(env.messages.includes("end"), true);
});
test("same-length corruption and sample-count changes never release recorded EOF", async () => {
  for (const expected of [{ samples: 1, sha256: "a".repeat(64) }, { samples: 2, sha256: "b".repeat(64) }]) {
    const env = setup(); env.response([[0, 0]]);
    await assert.rejects(new PreviewPlayer().play("/recorded", () => {}, { name: "complete-clip" }, { expectedHeaders: {}, recordedPCM: expected }), /Recorded PCM/);
    assert.equal(env.messages.includes("end"), false);
  }
});
test("Stop during recorded digest cannot subsequently release EOF", async () => {
  const env = setup(); let resolve; const original = crypto.subtle.digest;
  crypto.subtle.digest = () => new Promise(value => { resolve = value; });
  try {
    const player = new PreviewPlayer(); const playing = player.play("/recorded", () => {}, { name: "complete-clip" }, { expectedHeaders: {}, recordedPCM: { samples: 1, sha256: "0".repeat(64) } });
    await tick(); player.stop(); await assert.rejects(playing, { name: "AbortError" });
    resolve(new Uint8Array(32).buffer); await tick(); assert.equal(env.messages.includes("end"), false);
  } finally { crypto.subtle.digest = original; }
});
test("wrong required metadata fails before PCM and no recorded early-play policy is allowed", async () => {
  const env = setup();
  await assert.rejects(new PreviewPlayer().play("/recorded", () => {}, { name: "complete-clip" }, { expectedHeaders: { "X-Simo-Cache": "RECORDED" } }), /identity mismatch/);
  assert.equal(env.samples.length, 0);
  await assert.rejects(new PreviewPlayer().play("/recorded", () => {}, { name: "mlx-stream-v1", runtimeFingerprint: "a".repeat(64) }, { expectedHeaders: {}, recordedPCM: { samples: 1, sha256: "a".repeat(64) } }), /complete-clip/);
});
test("failed EOF evidence remains failed rather than claiming completion", async () => {
  const env = setup();
  const player = new PreviewPlayer();
  await assert.rejects(player.play("/trial", () => {}, { name: "complete-clip" }, { expectedHeaders: {}, onEOF: async () => { throw new Error("Request overwritten"); } }), /overwritten/);
  assert.equal(player.metrics.completed, false); assert.equal(env.signal.aborted, true);
});
test("unavailable output clock stays labeled callback fallback, not acoustic time", async () => {
  setup(); const result = await new PreviewPlayer().play("/clip", () => {});
  assert.equal(result.playbackClock, "callback-fallback"); assert.ok(result.firstPlaybackMs > 0);
});

test("transport EOF seals the worklet before delayed producer evidence, but completion waits", async () => {
  const env = setup(); let finish;
  const player = new PreviewPlayer();
  const playing = player.play("/trial", () => {}, { name: "complete-clip" }, { expectedHeaders: {}, onEOF: () => {
    assert.equal(env.messages.includes("end"), true);
    return new Promise(resolve => { finish = resolve; });
  } });
  await tick(); assert.equal(player.metrics.completed, false);
  finish(); const result = await playing; assert.equal(result.completed, true);
});
