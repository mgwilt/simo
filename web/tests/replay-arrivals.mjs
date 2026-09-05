// CLI-only replay: node web/tests/replay-arrivals.mjs <benchmark.json> [...]
import fs from "node:fs";
import assert from "node:assert/strict";
import { PcmQueue } from "../public/pcm-queue.js";

function replay(arrivals, eof, complete) {
  const rate = 24000, block = 128;
  const queue = new PcmQueue(complete ? 120 * rate : 48000, 5760, complete);
  const output = new Float32Array(block);
  let index = 0, frames = 0, ended = false, first = null;
  for (let n = 0; n < Math.ceil((eof + 130) * rate / block); n++) {
    const now = n * block / rate;
    while (index < arrivals.length && arrivals[index].at_s <= now) {
      const next = Math.round(arrivals[index].audio_s * rate);
      queue.push(new Float32Array(next - frames));
      frames = next; index++;
    }
    if (!ended && now >= eof) { queue.end(); ended = true; }
    const count = queue.render(output);
    if (count && first === null) first = now;
    if (queue.drained) return { gaps: queue.underruns, frames: queue.consumed, first_s: first };
  }
  throw new Error("Queue did not drain");
}

if (process.argv.length < 3) throw new Error("Provide benchmark JSON paths");
for (const path of process.argv.slice(2)) {
  const artifact = JSON.parse(fs.readFileSync(path, "utf8"));
  const data = artifact.resident_screen?.long ?? artifact;
  const rows = data.samples.map((sample, index) => ({
    reference: replay(data.chunk_arrivals[index], sample.wall_s, false),
    buffered: replay(data.chunk_arrivals[index], sample.wall_s, true),
  }));
  for (const row of rows) {
    assert.equal(row.buffered.gaps, 0);
    assert.equal(row.buffered.frames, row.reference.frames);
  }
  console.log(JSON.stringify({ path, clips: rows.length,
    referenceGaps: rows.reduce((sum, row) => sum + row.reference.gaps, 0),
    bufferedGaps: 0, identicalFrames: true,
    firstBufferedRange: [Math.min(...rows.map(row => row.buffered.first_s)), Math.max(...rows.map(row => row.buffered.first_s))],
    proof: "render-queue simulation, not physical playback or Fast acceptance",
  }));
}
