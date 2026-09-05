import assert from "node:assert/strict";
import test from "node:test";
import { ListeningSession, ListeningAutosave, recordedRequest, validateProducer, validateDeck, mountListening } from "../src/listening-review.ts";

function deck() {
  return { schema: "simo.breeze.listening.v1", deck_sha256: "a".repeat(64), cases: Array.from({ length: 18 }, (_, index) => ({
    id: (index + 100).toString(16).padStart(32, "0"), text: "Complete test text", instruction: "Warm voice", seed: 17,
    clips: [..."ABCD"].map((label, arm) => ({ id: (index * 4 + arm).toString(16).padStart(32, "0"), label, samples: 1920, pcm_sha256: "b".repeat(64), wav_sha256: "c".repeat(64) })),
  })) };
}
const manifest = { schema: "simo.breeze.https-benchmark.v1", manifest_sha256: "d".repeat(64), runtime_fingerprint: "e".repeat(64), playback_policy: "mlx-stream-v1" };
const requestId = "api-" + "a".repeat(32);
const metrics = { requestId, receivedFrames: 1920 };
const producer = { request_id: requestId, completed: true, eos_reached: true, cancelled: false, audio_samples: 1920, codec_frames: 1, audio_s: .08 };
const envelope = () => ({ manifest_sha256: manifest.manifest_sha256, runtime: { runtime_fingerprint: manifest.runtime_fingerprint, busy: false, last_request: { ...producer } } });

test("deck validates exact full schedule and rejects duplicate/malformed IDs", () => {
  const data = deck(); validateDeck(data);
  data.cases[1].clips[0].id = data.cases[0].clips[0].id;
  assert.throws(() => validateDeck(data), /Invalid/);
  assert.throws(() => validateDeck({ ...deck(), cases: [] }), /Invalid/);
});
test("recorded contract is full-PCM and never borrows live identities", () => {
  const data = deck(); const clip = data.cases[0].clips[0]; const contract = recordedRequest(data, clip);
  assert.equal(contract.expectedHeaders["X-Simo-Cache"], "RECORDED");
  assert.deepEqual(contract.recordedPCM, { samples: 1920, sha256: clip.pcm_sha256 });
  assert.throws(() => contract.onResponse(new Response(null, { headers: { "X-Breeze-Request-ID": requestId } })), /mislabeled/);
});
test("all attempts survive failures/stops/replays and incomplete export never accepts Fast", () => {
  const session = new ListeningSession(deck());
  const attempt = session.begin("recorded", { clip_id: session.deck.cases[0].clips[0].id });
  assert.throws(() => session.begin("recorded", {}), /already running/);
  assert.throws(() => session.export("", null, "fixture"), /Stop or finish/);
  attempt.status = "failed"; attempt.error = "AudioContext unsupported";
  session.begin("recorded", { clip_id: attempt.clip_id }).status = "stopped";
  session.begin("recorded", { clip_id: attempt.clip_id }).status = "complete";
  const exported = session.export("Synthetic device", null, "fixture");
  assert.deepEqual(exported.attempts.map(item => item.status), ["failed", "stopped", "complete"]);
  assert.equal(exported.ratings.length, 0);
  assert.equal(exported.quality_accepted, false); assert.equal(exported.acoustic_onset, "unmeasured");
  assert.ok(exported.attempts.every(item => item.listener.heard === "uncertain"));
});
test("fresh requests are fixed JSON with exact identities and unique IDs across retries", () => {
  const session = new ListeningSession(deck()); const attempt = session.begin("fresh", { trial: { suite: "short", index: 0, seed: 17, instruction_id: "default" } });
  const contract = session.freshRequest(manifest, attempt);
  assert.deepEqual(contract.body, { seed: 17, instruction_id: "default" });
  assert.equal(contract.expectedHeaders["X-Simo-Cache"], "BYPASS");
  assert.throws(() => contract.onResponse(new Response()), /Missing/);
  const response = new Response(null, { headers: { "X-Breeze-Request-ID": requestId } });
  contract.onResponse(response); attempt.status = "stopped";
  const retry = session.begin("fresh", { trial: attempt.trial });
  assert.throws(() => session.freshRequest(manifest, retry).onResponse(response), /reused/);
});
test("producer joins fail closed on overwritten request, runtime, EOF totals or cancellation", () => {
  assert.deepEqual(validateProducer(envelope(), manifest, metrics), producer);
  for (const [field, value] of Object.entries({ request_id: "api-" + "f".repeat(32), completed: false, eos_reached: false, cancelled: true, audio_samples: 1919, codec_frames: 0, audio_s: 1 })) {
    const changed = envelope(); changed.runtime.last_request[field] = value;
    assert.throws(() => validateProducer(changed, manifest, metrics), /unavailable/);
  }
  const changed = envelope(); changed.runtime.busy = true;
  assert.throws(() => validateProducer(changed, manifest, metrics), /unavailable/);
});
test("fresh EOF fetch binds completed evidence and propagates unavailable metrics", async () => {
  const session = new ListeningSession(deck()); const attempt = session.begin("fresh", { trial: { suite: "short", index: 0, seed: 17, instruction_id: "default" } });
  const contract = session.freshRequest(manifest, attempt);
  const controller = new AbortController();
  globalThis.fetch = async (url, options) => { assert.equal(url, `/api/benchmarks/metrics/${requestId}`); assert.equal(options.signal.aborted, false); return Response.json(envelope()); };
  await contract.onEOF(metrics, controller.signal); assert.deepEqual(attempt.producer, producer);
  globalThis.fetch = async () => new Response("unavailable", { status: 503 });
  await assert.rejects(contract.onEOF(metrics, controller.signal), /not accepted/);
});
test("an unconfigured deck never constructs a player or uploads anything", async () => {
  const calls = []; globalThis.fetch = async (...args) => { calls.push(args); return new Response(null, { status: 404 }); };
  assert.equal(await mountListening({}, () => { throw new Error("Playback on load"); }), false);
  assert.equal(calls.length, 1); assert.equal(calls[0][0], "/api/listening");
});

test("fresh EOF retries cleanup 409 with the same ID and Stop aborts the retry wait", async () => {
  const session = new ListeningSession(deck());
  const attempt = session.begin("fresh", { trial: { suite: "short", index: 0, seed: 17, instruction_id: "default" } });
  let calls = 0;
  globalThis.fetch = async url => { assert.equal(url, `/api/benchmarks/metrics/${requestId}`); return ++calls === 1 ? new Response(null, { status: 409 }) : Response.json(envelope()); };
  await session.freshRequest(manifest, attempt).onEOF(metrics, new AbortController().signal);
  assert.equal(calls, 2);
  globalThis.fetch = async () => new Response(null, { status: 409 });
  const controller = new AbortController();
  const pending = session.freshRequest(manifest, attempt).onEOF(metrics, controller.signal);
  await new Promise(resolve => setImmediate(resolve)); controller.abort();
  await assert.rejects(pending, { name: "AbortError" });
});

test("configured CPU DOM: load/advance/export are silent; setup failure, Stop and retry survive export", async () => {
  class Element {
    children = []; listeners = new Map(); disabled = false; value = ""; textContent = "";
    constructor(tag) { this.tag = tag; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute() {}
    addEventListener(type, callback) { this.listeners.set(type, callback); }
    querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
    querySelector(tag) { return this.querySelectorAll(tag)[0] ?? null; }
    click() { if (!this.disabled) this.listeners.get("click")?.(); }
  }
  const previousDocument = globalThis.document; const previousWindow = globalThis.window;
  const previousCreate = URL.createObjectURL; const previousRevoke = URL.revokeObjectURL;
  let blob; let constructed = 0; let rejectPlay;
  globalThis.document = { createElement: tag => new Element(tag) };
  globalThis.window = { addEventListener() {} };
  URL.createObjectURL = value => { blob = value; return "blob:fixture"; }; URL.revokeObjectURL = () => {};
  const root = new Element("section");
  const fullManifest = { ...manifest, suites: { short: ["A full line"], long: ["A long line"] }, instructions: { default: "Warm voice" } };
  const calls = [];
  globalThis.fetch = async url => { calls.push(url); return Response.json(url === "/api/listening" ? deck() : fullManifest); };
  try {
    const metrics = { completed: false, state: "buffering", underruns: 0, receivedFrames: 0 };
    await mountListening(root, () => {
      constructed++;
      if (constructed === 1) throw new Error("AudioContext unavailable");
      return { metrics, stop() { rejectPlay(new DOMException("Stopped", "AbortError")); }, play() {
        if (constructed === 2) return new Promise((_resolve, reject) => { rejectPlay = reject; });
        return Promise.resolve({ ...metrics, completed: true, state: "complete" });
      } };
    });
    const button = text => root.querySelectorAll("button").find(item => item.textContent === text);
    const tick = () => new Promise(resolve => setImmediate(resolve));
    assert.equal(constructed, 0); assert.deepEqual(calls, ["/api/listening", "/api/benchmarks"]);
    assert.equal(root.querySelectorAll("select").length, 0);
    const ratingInputs = () => root.querySelectorAll("input").filter(input => input.name.startsWith("clip-"));
    assert.equal(ratingInputs().length, 18);
    assert.equal(ratingInputs().filter(input => input.checked).length, 0);
    assert.equal(new Set(ratingInputs().map(input => input.name)).size, 6);
    button("Next comparison").click(); button("Previous").click();
    button("Download backup").click(); assert.equal(constructed, 0);
    assert.equal(JSON.parse(await blob.text()).attempts.length, 0);
    button("Hear A").click(); await tick();
    button("Download backup").click();
    assert.match(JSON.parse(await blob.text()).attempts[0].error, /AudioContext unavailable/);
    button("Hear A").click(); assert.equal(button("Download backup").disabled, true); assert.equal(button("Stop").disabled, false);
    button("Stop").click(); await tick();
    button("Hear A").click(); await tick(); button("Download backup").click();
    const exported = JSON.parse(await blob.text());
    assert.deepEqual(exported.attempts.map(item => item.status), ["failed", "stopped", "complete"]);
    assert.equal(exported.ratings.length, 0); assert.equal(exported.acoustic_onset, "unmeasured");
    assert.equal(constructed, 3); assert.equal(calls.length, 2);
    const unsure = ratingInputs().find(input => input.value === "uncertain");
    unsure.checked = true; unsure.listeners.get("change")();
    button("Next comparison").click(); button("Previous").click();
    assert.equal(ratingInputs().filter(input => input.checked).length, 1);
    button("Download backup").click();
    const rated = JSON.parse(await blob.text()).ratings;
    assert.equal(rated.length, 1); assert.equal(rated[0].heard_fully, "uncertain"); assert.deepEqual(rated[0].answered, ["heard_fully"]);
  } finally { globalThis.document = previousDocument; globalThis.window = previousWindow; URL.createObjectURL = previousCreate; URL.revokeObjectURL = previousRevoke; }
});

function memoryStorage() { const values = new Map(); return { getItem(key) { return values.get(key) ?? null; }, setItem(key, value) { values.set(key, value); } }; }
function ack(url, body) { return Response.json({ schema: "simo.breeze.listening.saved.v1", session_id: url.split("/").at(-1), revision: JSON.parse(body).revision, deck_sha256: deck().deck_sha256 }); }
const snapshot = () => new ListeningSession(deck()).snapshot("synthetic", null, "CPU fixture");

test("autosave serializes edits, reports Saved only for latest ack, and retains exact uncertain-response retry", async () => {
  const storage = memoryStorage(); const messages = []; const calls = []; let release;
  const first = snapshot(); const second = { ...first, conditions: "edited during request" };
  globalThis.fetch = async (url, options) => { calls.push(options.body); if (calls.length === 1) await new Promise(resolve => { release = resolve; }); return ack(url, options.body); };
  const saving = new ListeningAutosave(first.deck_sha256, storage, text => messages.push(text));
  saving.save(first); const pending = saving.flush(); saving.save(second);
  assert.ok(messages.every(text => !text.startsWith("Saved")));
  release(); await pending;
  assert.equal(calls.length, 2); assert.equal(JSON.parse(calls[1]).snapshot.conditions, second.conditions);
  assert.equal(messages.at(-1), "Saved on this server");
  const third = { ...second, conditions: "lost ack" }; saving.save(third);
  globalThis.fetch = async (_url, options) => { calls.push(options.body); throw new Error("connection lost after commit"); };
  await saving.flush(); const lost = calls.at(-1);
  assert.match(messages.at(-1), /Not saved/);
  globalThis.fetch = async (url, options) => {
    if (options.method === "PUT") { calls.push(options.body); return ack(url, options.body); }
    return Response.json({ schema: "simo.breeze.listening.saved.v1", session_id: url.split("/").at(-1), revision: 3, snapshot: third });
  };
  const resumed = new ListeningAutosave(first.deck_sha256, storage, text => messages.push(text));
  assert.deepEqual(await resumed.restore(), third); assert.equal(calls.at(-1), lost);
});

test("offline refresh retains newest draft; conflicts require explicit separate session", async () => {
  const storage = memoryStorage(); const messages = []; const first = snapshot();
  globalThis.fetch = async () => { throw new Error("offline"); };
  const saving = new ListeningAutosave(first.deck_sha256, storage, text => messages.push(text));
  saving.save(first); await saving.flush();
  const newest = { ...first, conditions: "offline edit" }; saving.save(newest); await saving.flush();
  const resumed = new ListeningAutosave(first.deck_sha256, storage, text => messages.push(text));
  assert.deepEqual(await resumed.restore(), newest);
  const ids = [];
  globalThis.fetch = async url => { ids.push(url); return new Response(null, { status: 409 }); };
  await resumed.flush(); assert.equal(resumed.conflict, true); assert.match(messages.at(-1), /conflict/);
  await resumed.flush(); assert.equal(ids.length, 1);
  globalThis.fetch = async (url, options) => { ids.push(url); return ack(url, options.body); };
  await resumed.separateSession(); assert.notEqual(ids[0], ids[1]);
  assert.equal(resumed.conflict, false); assert.equal(messages.at(-1), "Saved on this server");
});

test("storage failure is visible and server save remains available; mismatched acknowledgments never claim Saved", async () => {
  const messages = []; const data = snapshot();
  const saving = new ListeningAutosave(data.deck_sha256, { getItem() { throw new Error("denied"); }, setItem() { throw new Error("quota"); } }, text => messages.push(text));
  globalThis.fetch = async () => Response.json({ schema: "wrong" });
  saving.save(data); await saving.flush(); assert.match(messages.at(-1), /Not saved.*recovery unavailable/);
  globalThis.fetch = async (url, options) => ack(url, options.body);
  await saving.flush(); assert.match(messages.at(-1), /^Saved on this server.*recovery unavailable/);
});

test("resume preserves clip view, conditions, notes and attempt evidence; running becomes stopped without playback", () => {
  const original = new ListeningSession(deck()); const clip = original.deck.cases[3].clips[2];
  original.ratings.set(clip.id, { clip_id: clip.id, pcm_sha256: clip.pcm_sha256, heard_fully: "no", intelligible: "uncertain", complete_words: "uncertain", instruction: "uncertain", natural: "uncertain", gap_free: "uncertain", answered: ["heard_fully"], notes: "missing ending" });
  original.preferences.set(original.deck.cases[3].id, "C");
  original.begin("fresh", { trial: { suite: "short", index: 0, seed: 17, instruction_id: "default" }, benchmark_manifest: manifest });
  const data = structuredClone(original.snapshot("Bluetooth", manifest, "CPU", { position: 3, clip: "C" }));
  const resumed = new ListeningSession(deck()); assert.equal(resumed.restore(data), true);
  assert.equal(resumed.started, original.started); assert.equal(resumed.attempts[0].status, "stopped");
  assert.deepEqual(resumed.attempts[0].benchmark_manifest, manifest); assert.match(resumed.attempts[0].error, /not resumed/);
  assert.deepEqual([...resumed.ratings.values()], [...original.ratings.values()]); assert.deepEqual([...resumed.preferences], [...original.preferences]);
  assert.equal(data.view.clip, "C"); assert.equal(data.conditions, "Bluetooth");
  assert.throws(() => new ListeningSession(deck()).restore({ ...data, deck_sha256: "f".repeat(64) }), /match/);
});

test("server deadline covers stalled acknowledgment and restore bodies, and Retry recovers", async () => {
  const previousTimer = globalThis.setTimeout; const storage = memoryStorage(); const messages = []; const data = snapshot();
  globalThis.setTimeout = (callback, delay, ...args) => previousTimer(callback, delay === 10000 ? 10 : delay, ...args);
  let aborted = 0;
  const stalled = async (_url, options) => {
    options.signal.addEventListener("abort", () => { aborted++; });
    return { ok: true, status: 200, text: () => new Promise(() => {}) };
  };
  try {
    const saving = new ListeningAutosave(data.deck_sha256, storage, message => messages.push(message));
    globalThis.fetch = stalled; saving.save(data); await saving.flush();
    assert.match(messages.at(-1), /Not saved.*timed out/); assert.equal(aborted, 1);
    globalThis.fetch = async (url, options) => ack(url, options.body); await saving.flush();
    assert.equal(messages.at(-1), "Saved on this server");
    globalThis.fetch = stalled;
    const resumed = new ListeningAutosave(data.deck_sha256, storage, message => messages.push(message));
    assert.deepEqual(await resumed.restore(), data); assert.match(messages.at(-1), /timed out/); assert.equal(aborted, 2);
  } finally { globalThis.setTimeout = previousTimer; }
});

test("server-enabled mount restores mobile view and partial radios, records interruption, and never autoplays", async () => {
  class Element {
    children = []; listeners = new Map(); disabled = false; value = ""; textContent = "";
    constructor(tag) { this.tag = tag; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute() {}
    addEventListener(type, callback) { this.listeners.set(type, callback); }
    querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tag === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
    click() { if (!this.disabled) this.listeners.get("click")?.(); }
  }
  const previousDocument = globalThis.document; const previousWindow = globalThis.window;
  const storage = memoryStorage(); const data = deck(); data.server_results = true;
  const original = new ListeningSession(data); const item = data.cases[3]; const clip = item.clips[2];
  original.ratings.set(clip.id, { clip_id: clip.id, pcm_sha256: clip.pcm_sha256, heard_fully: "uncertain", intelligible: "uncertain", complete_words: "uncertain", instruction: "uncertain", natural: "uncertain", gap_free: "uncertain", notes: "Retain this note", answered: ["natural"] });
  original.preferences.set(item.id, "C"); original.begin("recorded", { clip_id: clip.id, case_id: item.id });
  const restored = original.snapshot("Phone speakers", null, "fixture", { position: 3, clip: "C" });
  const session_id = "a".repeat(32);
  storage.setItem(`simo-listening-v1:${data.deck_sha256}`, JSON.stringify({ session_id, revision: 1, pending: null, latest: restored }));
  const fullManifest = { ...manifest, suites: { short: ["Short"], long: ["Long"] }, instructions: { default: "Warm" } };
  const writes = []; let plays = 0;
  globalThis.document = { createElement: tag => new Element(tag) }; globalThis.window = { localStorage: storage, addEventListener() {} };
  globalThis.fetch = async (url, options) => {
    if (url === "/api/listening") return Response.json(data);
    if (url === "/api/benchmarks") return Response.json(fullManifest);
    if (options.method === "PUT") { writes.push(JSON.parse(options.body)); return ack(url, options.body); }
    return Response.json({ schema: "simo.breeze.listening.saved.v1", session_id, revision: 1, snapshot: restored });
  };
  try {
    const root = new Element("section"); await mountListening(root, () => { plays++; throw new Error("Must remain silent"); });
    assert.equal(plays, 0); assert.ok(root.querySelectorAll("h3").some(value => value.textContent === "Comparison 4 of 18"));
    assert.ok(root.querySelectorAll("button").some(value => value.textContent === "Hear C"));
    assert.equal(root.querySelectorAll("input").filter(value => value.name.startsWith("clip-") && value.checked).length, 1);
    assert.ok(root.querySelectorAll("textarea").some(value => value.value === "Retain this note"));
    assert.ok(root.querySelectorAll("textarea").some(value => value.value === "Phone speakers"));
    assert.ok(root.querySelectorAll("input").some(value => value.name === `preference-${item.id}` && value.value === "C" && value.checked));
    await new Promise(resolve => setTimeout(resolve, 350));
    assert.equal(writes.length, 1); assert.equal(writes[0].revision, 2); assert.equal(writes[0].snapshot.attempts[0].status, "stopped");
    assert.equal(plays, 0); assert.equal(writes[0].snapshot.ratings.length, 1);
  } finally { globalThis.document = previousDocument; globalThis.window = previousWindow; }
});
