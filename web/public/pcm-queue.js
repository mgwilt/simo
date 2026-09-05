/** Bounded mono PCM queue shared by the real worklet and deterministic tests. */
export class PcmQueue {
  constructor(capacity = 48000, threshold = 5760, waitForEnd = false) {
    if (!Number.isInteger(capacity) || !Number.isInteger(threshold) || capacity < 1 || threshold < 1 || threshold > capacity) throw new Error("Invalid PCM bounds");
    this.data = new Float32Array(capacity);
    this.threshold = threshold;
    this.waitForEnd = waitForEnd;
    this.head = 0;
    this.size = 0;
    this.consumed = 0;
    this.started = false;
    this.playing = false;
    this.ended = false;
    this.stopped = false;
    this.underruns = 0;
    this.starved = false;
  }

  push(samples) {
    if (this.stopped || this.ended) throw new Error("PCM stream is closed");
    if (!(samples instanceof Float32Array) || this.size + samples.length > this.data.length) {
      throw new Error("PCM buffer overflow");
    }
    const tail = (this.head + this.size) % this.data.length;
    const first = Math.min(samples.length, this.data.length - tail);
    this.data.set(samples.subarray(0, first), tail);
    this.data.set(samples.subarray(first), 0);
    this.size += samples.length;
  }

  end() { this.ended = true; }
  stop() { this.stopped = true; this.size = 0; this.playing = false; }

  render(output) {
    output.fill(0);
    if (this.stopped) return 0;
    if (!this.playing && ((!this.waitForEnd && this.size >= this.threshold) || (this.ended && this.size > 0))) {
      // Only later audio proves this was an interior gap, not delayed EOF.
      if (this.starved) this.underruns += 1;
      this.starved = false;
      this.playing = true;
      this.started = true;
    }
    if (!this.playing) return 0;
    const count = Math.min(output.length, this.size);
    const first = Math.min(count, this.data.length - this.head);
    output.set(this.data.subarray(this.head, this.head + first));
    output.set(this.data.subarray(0, count - first), first);
    this.head = (this.head + count) % this.data.length;
    this.size -= count;
    this.consumed += count;
    if (count < output.length && !this.ended) {
      this.starved = true;
      this.playing = false;
    }
    return count;
  }

  get drained() { return this.ended && this.size === 0; }
}
