import assert from "node:assert/strict";
import test from "node:test";
import { PcmQueue } from "../public/pcm-queue.js";

test("startup buffering is not an underrun; a short EOF plays", () => {
  const q = new PcmQueue(16, 8);
  q.push(new Float32Array([1, 2, 3]));
  const output = new Float32Array(5);
  q.render(output);
  assert.deepEqual([...output], [0, 0, 0, 0, 0]);
  assert.equal(q.underruns, 0);
  q.end(); q.render(output);
  assert.deepEqual([...output], [1, 2, 3, 0, 0]);
  assert.equal(q.consumed, 3);
  assert.equal(q.drained, true);
});

test("wraparound and arbitrary render lengths preserve every sample", () => {
  const q = new PcmQueue(8, 1), out = new Float32Array(3);
  q.push(new Float32Array([1, 2, 3, 4, 5]));
  q.render(out); assert.deepEqual([...out], [1, 2, 3]);
  q.push(new Float32Array([6, 7, 8, 9, 10]));
  q.end();
  const played = [];
  while (!q.drained) { const n = q.render(out); played.push(...out.slice(0, n)); }
  assert.deepEqual(played, [4, 5, 6, 7, 8, 9, 10]);
  assert.equal(q.consumed, 10); assert.equal(q.underruns, 0);
});

test("starvation counts episodes, rebuffering does not repeatedly increment", () => {
  const q = new PcmQueue(16, 4), out = new Float32Array(5);
  q.push(new Float32Array([1, 2, 3, 4])); q.render(out);
  assert.equal(q.underruns, 0);
  q.render(out); q.render(out); assert.equal(q.underruns, 0);
  q.push(new Float32Array([5, 6, 7, 8])); q.render(out);
  assert.equal(q.underruns, 1);
});

test("delayed EOF after final samples is not an interior underrun", () => {
  const q = new PcmQueue(8, 4), out = new Float32Array(4);
  q.push(new Float32Array(4)); q.render(out); q.render(out); q.end();
  assert.equal(q.drained, true); assert.equal(q.underruns, 0);
});

test("overflow fails; stop and end are terminal", () => {
  const q = new PcmQueue(4, 1);
  assert.throws(() => q.push(new Float32Array(5)), /overflow/);
  q.push(new Float32Array([1])); q.stop();
  const out = new Float32Array([9, 9]); q.render(out);
  assert.deepEqual([...out], [0, 0]);
  assert.throws(() => q.push(new Float32Array([2])), /closed/);
  const other = new PcmQueue(4, 1); other.end();
  assert.throws(() => other.push(new Float32Array([2])), /closed/);
});

test("complete-clip mode stays silent even at exact capacity until EOF", () => {
  const q = new PcmQueue(16, 4, true), out = new Float32Array(4);
  q.push(Float32Array.from({ length: 16 }, (_, i) => i + 1));
  for (let i = 0; i < 10; i++) assert.equal(q.render(out), 0);
  assert.equal(q.started, false); assert.equal(q.size, 16);
  q.end(); const played = [];
  while (!q.drained) { const n = q.render(out); played.push(...out.subarray(0, n)); }
  assert.deepEqual(played, Array.from({ length: 16 }, (_, i) => i + 1));
  assert.equal(q.underruns, 0);
});

test("complete-clip Stop discards buffered samples without starting", () => {
  const q = new PcmQueue(16, 4, true), out = new Float32Array(4);
  q.push(new Float32Array(16)); q.stop();
  assert.equal(q.render(out), 0); assert.equal(q.started, false); assert.equal(q.size, 0);
});
