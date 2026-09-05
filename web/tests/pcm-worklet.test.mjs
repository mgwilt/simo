import assert from "node:assert/strict";
import test from "node:test";

let Processor;
globalThis.currentTime = 12;
globalThis.AudioWorkletProcessor = class {
  messages = [];
  port = { postMessage: message => this.messages.push(message) };
};
globalThis.registerProcessor = (name, ctor) => { assert.equal(name, "simo-pcm"); Processor = ctor; };
await import("../public/pcm-worklet.js");

test("worklet emits one start, exact consumption and terminal drain", () => {
  const processor = new Processor();
  processor.port.onmessage({ data: { type: "pcm", samples: new Float32Array([1, 2, 3]) } });
  processor.port.onmessage({ data: { type: "end" } });
  const output = new Float32Array(2);
  assert.equal(processor.process([], [[output]]), true);
  assert.deepEqual([...output], [1, 2]);
  assert.equal(processor.process([], [[output]]), false);
  assert.deepEqual([...output], [3, 0]);
  assert.deepEqual(processor.messages, [
    { type: "started", contextTime: 12 }, { type: "consumed", frames: 2 },
    { type: "consumed", frames: 3 }, { type: "drained", frames: 3 },
  ]);
});

test("invalid protocol and Stop terminate worklet", () => {
  const processor = new Processor();
  processor.port.onmessage({ data: { type: "unknown" } });
  assert.equal(processor.messages[0].type, "error");
  assert.equal(processor.process([], [[new Float32Array(128)]]), false);
  const stopped = new Processor(); stopped.port.onmessage({ data: { type: "stop" } });
  assert.equal(stopped.process([], [[new Float32Array(128)]]), false);
});

test("buffered preview worklet holds exact maximum until end then needs no refills", () => {
  const processor = new Processor({ processorOptions: { bufferUntilEnd: true } });
  const limit = 120 * 24000, samples = new Float32Array(limit).fill(0.25);
  processor.port.onmessage({ data: { type: "pcm", samples } });
  const output = new Float32Array(128);
  for (let i = 0; i < 10; i++) processor.process([], [[output]]);
  assert.equal(processor.messages.length, 0);
  assert.equal(processor.queue.size, limit);
  processor.port.onmessage({ data: { type: "end" } });
  let rendered = 0;
  while (true) {
    const active = processor.process([], [[output]]);
    assert.ok(output.every(value => value === 0.25));
    rendered += output.length;
    if (!active) break;
  }
  assert.equal(rendered, limit);
  assert.equal(processor.messages.filter(message => message.type === "started").length, 1);
  assert.equal(processor.messages.filter(message => message.type === "underrun").length, 0);
  assert.deepEqual(processor.messages.at(-1), { type: "drained", frames: limit });
});

test("buffered worklet overflow stops without emitting a start", () => {
  const processor = new Processor({ processorOptions: { bufferUntilEnd: true } });
  processor.port.onmessage({ data: { type: "pcm", samples: new Float32Array(120 * 24000 + 1) } });
  assert.equal(processor.messages[0].type, "error");
  assert.equal(processor.process([], [[new Float32Array(128)]]), false);
  assert.equal(processor.messages.some(message => message.type === "started"), false);
});
