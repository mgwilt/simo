// node web/scripts/replay-preview.mjs <completed-report.json> [...]
// Uses actual PreviewPlayer + processor through simulated ports/clock, not a browser/device.
import fs from "node:fs";
import crypto from "node:crypto";
import assert from "node:assert/strict";
import { playbackPolicy } from "../src/preview-player.ts";
import { playbackHarness, exactRenderedPCM, STREAM_HEADERS, TEST_RUNTIME } from "../tests/helpers/playback-harness.mjs";

const sha = value => crypto.createHash("sha256").update(value).digest("hex");
function wavPCM(path) {
  const data = fs.readFileSync(path);
  assert.equal(data.toString("ascii", 0, 4), "RIFF");
  assert.equal(data.toString("ascii", 8, 12), "WAVE");
  let format, pcm;
  for (let offset = 12; offset + 8 <= data.length;) {
    const type = data.toString("ascii", offset, offset + 4), length = data.readUInt32LE(offset + 4);
    const end = offset + 8 + length;
    assert.ok(end <= data.length, "truncated WAV");
    if (type === "fmt ") format = data.subarray(offset + 8, end);
    if (type === "data") { assert.equal(pcm, undefined, "multiple PCM chunks"); pcm = data.subarray(offset + 8, end); }
    offset = end + (length % 2);
  }
  assert.ok(format && pcm);
  assert.deepEqual([format.readUInt16LE(0), format.readUInt16LE(2), format.readUInt32LE(4), format.readUInt16LE(14)], [1, 1, 24000, 16]);
  return pcm;
}
if (process.argv.length < 3) throw new Error("Provide completed benchmark reports");
const reports = [];
for (const path of process.argv.slice(2)) {
  const reportBytes = fs.readFileSync(path), report = JSON.parse(reportBytes);
  const samples = [];
  if (report.schema_version === 3) {
    assert.equal(report.completed, true, "cannot replay a failed cohort as accepted evidence");
    assert.equal(report.failure, undefined);
    assert.match(report.runtime?.runtime_fingerprint ?? "", /^[0-9a-f]{64}$/);
    assert.equal(report.manifest.runtime_fingerprint, report.runtime.runtime_fingerprint);
    assert.equal(report.manifest.playback_policy, "mlx-stream-v1");
    const prompts = report.manifest.suites[report.suite].slice(0, report.limit);
    const expected = prompts.flatMap((prompt, index) => report.seeds.map(seed => ({ prompt, index, seed })));
    assert.equal(report.timed_case_count, expected.length);
    assert.equal(report.samples.length, expected.length);
    assert.equal(report.warmup_samples.length, report.warmups);
    const ids = new Set();
    for (const [index, sample] of [...report.warmup_samples, ...report.samples].entries()) {
      assert.match(sample.request_id, /^api-[0-9a-f]{32}$/);
      assert.ok(!ids.has(sample.request_id)); ids.add(sample.request_id);
      assert.equal(sample.instruction_id, report.instruction_id);
      assert.equal(sample.cache, "BYPASS");
      assert.equal(sample.metrics.request_id, sample.request_id);
      assert.equal(sample.metrics.completed, true);
      assert.equal(sample.metrics.eos_reached, true);
      assert.equal(sample.metrics.cancelled, false);
      const row = index < report.warmups
        ? { prompt: prompts[0], index: 0, seed: report.seeds[0] }
        : expected[index - report.warmups];
      for (const key of ["prompt", "index", "seed"]) assert.equal(sample[key], row[key]);
    }
  }
  assert.equal(report.samples.length, report.audio_artifacts.length);
  for (let index = 0; index < report.samples.length; index++) {
    const sample = report.samples[index], audio = report.audio_artifacts[index];
    const pcm = wavPCM(audio.path);
    assert.equal(sha(pcm), audio.pcm_sha256);
    const arrivals = sample.arrivals
      ? sample.arrivals.map(item => ({ at_s: item.seconds, frames: item.samples }))
      : report.chunk_arrivals[index].map((item, i, all) => ({ at_s: item.at_s, frames: Math.round((item.audio_s - (all[i - 1]?.audio_s ?? 0)) * 24000) }));
    assert.equal(arrivals.reduce((sum, item) => sum + item.frames, 0) * 2, pcm.length);
    const eof = sample.total_s ?? sample.wall_s;
    assert.ok(Number.isFinite(eof) && eof >= arrivals.at(-1).at_s);
    const runtime = report.runtime?.runtime_fingerprint ?? TEST_RUNTIME;
    const h = await playbackHarness();
    try {
      const run = h.start({ headers: { ...STREAM_HEADERS, "X-Simo-Runtime-Fingerprint": runtime }, policy: playbackPolicy("mlx-stream-v1", runtime) });
      let position = 0, offset = 0, ended = false;
      while (!run.settled && h.nowMs < (eof + sample.audio_s + 5) * 1000) {
        while (position < arrivals.length && arrivals[position].at_s * 1000 <= h.nowMs) {
          const end = offset + arrivals[position].frames * 2;
          run.enqueue(new Uint8Array(pcm.subarray(offset, end)));
          offset = end; position++;
        }
        if (!ended && position === arrivals.length && h.nowMs >= eof * 1000) { run.end(); ended = true; }
        await h.step();
      }
      assert.ok(run.settled, "player did not settle"); assert.equal(run.error, null);
      assert.ok(exactRenderedPCM(run.node(), pcm), "rendered samples differ");
      assert.ok(run.node().maxOutstanding <= 48000 && run.node().maxRing <= 48000);
      assert.equal(run.result.underruns, 0, "recorded arrival gap");
      samples.push({ prompt: sample.prompt, seed: sample.seed, pcm_sha256: sha(pcm), frames: pcm.length / 2,
        first_render_s: run.node().firstRenderMs / 1000, scheduled_estimate_s: run.result.firstPlaybackMs / 1000,
        max_outstanding_frames: run.node().maxOutstanding, max_ring_frames: run.node().maxRing,
        underruns: run.result.underruns, exact_pcm: true, completed: run.result.completed });
    } finally { h.restore(); }
  }
  const values = samples.map(item => item.first_render_s).sort((a, b) => a - b);
  reports.push({ path, sha256: sha(reportBytes), source: report.source ?? report.runtime,
    synthetic_wire_identity: !report.runtime?.runtime_fingerprint, samples,
    first_render_p95_s: values[Math.ceil(values.length * .95) - 1] });
}
console.log(JSON.stringify({ schema_version: 1, policy: "mlx-stream-v1", capacity_frames: 48000, reserve_frames: 15360,
  sample_rate: 24000, render_quantum: 128, reports,
  proof: "Actual player and worklet logic; simulated ports, context setup, output timestamps and render clock. Retained PCM and arrival/EOF times. Not real browser scheduling, network backpressure, physical sound, LAN jitter acceptance or Fast release." }, null, 2));
