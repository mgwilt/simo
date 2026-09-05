import { PcmQueue } from "./pcm-queue.js?preview-v2";

class SimoPCMProcessor extends AudioWorkletProcessor {
  constructor(options = {}) {
    super();
    // Preview clips favor continuous speech over early partial playback. The
    // explicit EOF gate also covers a clip that exactly fills the 120s bound.
    const buffered = options.processorOptions?.bufferUntilEnd === true;
    this.streaming = options.processorOptions?.streamingPolicy === "mlx-stream-v1";
    this.queue = buffered ? new PcmQueue(120 * 24000, 5760, true)
      : this.streaming ? new PcmQueue(48000, 15360) : new PcmQueue();
    this.announcedState = "buffering";
    this.announcedStart = false;
    this.announcedUnderruns = 0;
    this.port.onmessage = ({ data }) => {
      try {
        if (data.type === "pcm") this.queue.push(data.samples);
        else if (data.type === "end") this.queue.end();
        else if (data.type === "stop") this.queue.stop();
        else throw new Error("Unknown PCM message");
      } catch (error) {
        this.port.postMessage({ type: "error", message: String(error) });
        this.queue.stop();
      }
    };
  }

  process(_inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output || this.queue.stopped) return false;
    const count = this.queue.render(output);
    if (count && !this.announcedStart) {
      this.announcedStart = true;
      this.port.postMessage({ type: "started", contextTime: currentTime });
    }
    if (count) this.port.postMessage({ type: "consumed", frames: this.queue.consumed });
    if (this.queue.underruns !== this.announcedUnderruns) {
      this.announcedUnderruns = this.queue.underruns;
      this.port.postMessage({ type: "underrun", count: this.queue.underruns });
    }
    if (this.streaming && this.queue.started && !this.queue.drained) {
      const state = this.queue.playing ? "playing" : "rebuffering";
      if (state !== this.announcedState) {
        this.announcedState = state;
        this.port.postMessage({ type: "state", state });
      }
    }
    if (this.queue.drained) {
      this.port.postMessage({ type: "drained", frames: this.queue.consumed });
      return false;
    }
    return true;
  }
}

registerProcessor("simo-pcm", SimoPCMProcessor);
