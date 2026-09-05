import assert from "node:assert/strict";
import test from "node:test";
import { playbackPolicy, STREAM_CAPACITY_FRAMES } from "../src/preview-player.ts";
import { playbackHarness, pcmPattern, exactRenderedPCM, STREAM_HEADERS, TEST_RUNTIME } from "./helpers/playback-harness.mjs";

test("actual player/worklet stream before EOF with bounded sample-exact credits", async () => {
  const h = await playbackHarness();
  try {
    const run = h.start(), pcm = pcmPattern(24000 * 5);
    run.enqueue(pcm);
    for (let n = 0; n < 10; n++) await h.step();
    assert.notEqual(run.player.metrics.firstPlaybackMs, null);
    assert.equal(run.settled, false);
    assert.ok(run.node().maxOutstanding <= STREAM_CAPACITY_FRAMES);
    run.end(); await h.finish(run);
    assert.equal(run.error, null);
    assert.equal(run.result.completed, true);
    assert.equal(run.result.underruns, 0);
    assert.ok(run.node().maxRing <= STREAM_CAPACITY_FRAMES);
    assert.ok(exactRenderedPCM(run.node(), pcm));
  } finally { h.restore(); }
});

test("640ms threshold, short EOF and odd byte boundaries use the real processor", async () => {
  const h = await playbackHarness();
  try {
    const run = h.start(), pcm = pcmPattern(15360);
    run.enqueue(pcm.subarray(0, 1)); run.enqueue(pcm.subarray(1, pcm.length - 2));
    await h.step(); assert.equal(run.node().firstRenderMs, null);
    run.enqueue(pcm.subarray(pcm.length - 2)); await h.step();
    assert.notEqual(run.node().firstRenderMs, null);
    run.end(); await h.finish(run); assert.ok(exactRenderedPCM(run.node(), pcm));
    const short = h.start(), bytes = pcmPattern(3);
    short.enqueue(bytes); await h.step(); assert.equal(short.node().firstRenderMs, null);
    short.end(); await h.finish(short); assert.ok(exactRenderedPCM(short.node(), bytes));
  } finally { h.restore(); }
});

test("delayed credits preserve two-second outstanding bound and exact output", async () => {
  const h = await playbackHarness({ creditDelayMs: 200 });
  try {
    const run = h.start(), pcm = pcmPattern(24000 * 8);
    run.enqueue(pcm); run.end(); await h.finish(run);
    assert.equal(run.error, null); assert.equal(run.result.underruns, 0);
    assert.ok(run.node().maxOutstanding <= STREAM_CAPACITY_FRAMES);
    assert.ok(exactRenderedPCM(run.node(), pcm));
  } finally { h.restore(); }
});

test("lost credits and stalled stream cancellation cannot hold Stop", async () => {
  const h = await playbackHarness({ holdCredits: true });
  try {
    const run = h.start({ cancelNever: true });
    run.enqueue(pcmPattern(24000 * 8));
    for (let n = 0; n < 10; n++) await h.step();
    assert.equal(run.player.metrics.receivedFrames, STREAM_CAPACITY_FRAMES);
    run.player.stop(); await h.finish(run, 100);
    assert.equal(run.error.name, "AbortError"); assert.equal(run.result, null);
    assert.equal(run.node().connected, false); assert.equal(run.player.metrics.completed, false);
  } finally { h.restore(); }
});

test("late transport failure clears queued audio, keeps the error, and retries", async () => {
  const h = await playbackHarness();
  try {
    const run = h.start(); run.enqueue(pcmPattern(24000)); await h.step();
    assert.notEqual(run.node().firstRenderMs, null);
    run.fail(new Error("Late HTTP failure")); await h.finish(run, 100);
    assert.equal(run.error.message, "Late HTTP failure"); assert.equal(run.player.metrics.completed, false);
    assert.equal(run.node().connected, false); await h.flush(); assert.equal(run.node().processor.queue.size, 0);
    const retry = h.start(); const pcm = pcmPattern(1000);
    retry.enqueue(pcm); retry.end(); await h.finish(retry);
    assert.equal(retry.error, null); assert.ok(exactRenderedPCM(retry.node(), pcm));
  } finally { h.restore(); }
});

test("connection failure interrupts a pending credit wait immediately", async () => {
  const h = await playbackHarness({ holdCredits: true });
  try {
    const run = h.start(); run.enqueue(pcmPattern(24000 * 8)); await h.step();
    assert.equal(run.player.metrics.receivedFrames, 48000);
    run.fail(new Error("Connection failed during backpressure"));
    await h.finish(run, 100);
    assert.equal(run.error.message, "Connection failed during backpressure");
    assert.equal(run.player.metrics.completed, false); assert.equal(run.node().connected, false);
  } finally { h.restore(); }
});

test("stale or missing streaming policy/identity cannot post any PCM", async () => {
  for (const changed of [{ "X-Simo-Runtime-Fingerprint": "b".repeat(64) }, { "X-Simo-Playback-Policy": "complete-clip" }]) {
    const h = await playbackHarness();
    try {
      const run = h.start({ headers: { ...STREAM_HEADERS, ...changed } });
      run.enqueue(pcmPattern(24000)); run.end(); await h.finish(run, 100);
      assert.match(run.error.message, /changed/); assert.equal(run.node().posted, 0);
      assert.equal(run.node().firstRenderMs, null);
    } finally { h.restore(); }
  }
});

test("unknown policy retains complete-clip silence and malformed opt-in rejects", async () => {
  assert.throws(() => playbackPolicy("mlx-stream-v1", "invalid"), /fingerprint/);
  const h = await playbackHarness();
  try {
    const run = h.start({ policy: playbackPolicy("future-unknown", TEST_RUNTIME) });
    run.enqueue(pcmPattern(24000)); await h.step();
    assert.equal(run.node().firstRenderMs, null);
    run.end(); await h.finish(run); assert.equal(run.result.completed, true);
  } finally { h.restore(); }
});

test("rebuffer state and interior gap are emitted without counting delayed EOF", async () => {
  const h = await playbackHarness();
  try {
    const run = h.start(); run.enqueue(pcmPattern(15360));
    for (let n = 0; n < 130; n++) await h.step();
    assert.equal(run.player.metrics.state, "rebuffering");
    assert.equal(run.player.metrics.underruns, 0);
    run.enqueue(pcmPattern(15360)); await h.step();
    assert.equal(run.player.metrics.state, "playing"); assert.equal(run.player.metrics.underruns, 1);
    run.end(); await h.finish(run); assert.equal(run.result.underruns, 1);
  } finally { h.restore(); }
});

test("streaming exact120s cap remains bounded and one extra sample aborts", async () => {
  const h = await playbackHarness();
  try {
    const run = h.start(), pcm = pcmPattern(120 * 24000);
    run.enqueue(pcm); run.end(); await h.finish(run);
    assert.equal(run.error, null); assert.ok(exactRenderedPCM(run.node(), pcm));
    assert.ok(run.node().maxOutstanding <= 48000);
    const oversized = h.start(); oversized.enqueue(pcmPattern(120 * 24000 + 1)); oversized.end();
    await h.finish(oversized, 100);
    assert.match(oversized.error.message, /120-second/); assert.equal(oversized.node().posted, 0);
  } finally { h.restore(); }
});

test("late odd EOF and invalid consumption credit abort instead of completing", async () => {
  for (const invalidCredit of [false, true]) {
    const h = await playbackHarness();
    try {
      const run = h.start(); run.enqueue(pcmPattern(24000)); await h.step();
      if (invalidCredit) run.node().port.onmessage({ data: { type: "consumed", frames: 24001 } });
      else { run.enqueue(new Uint8Array([1])); run.end(); }
      await h.finish(run, 100);
      assert.match(run.error.message, invalidCredit ? /consumption credit/ : /Incomplete/);
      assert.equal(run.player.metrics.completed, false); assert.equal(run.node().connected, false);
    } finally { h.restore(); }
  }
});
