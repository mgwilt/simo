import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { requestSettings, settingsPayload } from "../src/live-controls.ts";

const settings = { prompt: "Explain fully", voice_instruction: "A warm lower-register voice", max_tokens: 1024,
  revision: 3, voice_editable: true, seed: 42, cfg_scale: 4, scope: "Session only" };

test("GET loads active settings and PUT sends only the revisioned editable fields", async () => {
  const prior = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => { calls.push([url, options]); return Response.json(settings); };
  try {
    assert.deepEqual(await requestSettings(), settings);
    await requestSettings(settings);
    assert.equal(calls[0][0], "/api/controls");
    assert.equal(calls[0][1].method, "GET");
    assert.equal(calls[0][1].cache, "no-store");
    assert.equal(calls[1][1].method, "PUT");
    assert.deepEqual(JSON.parse(calls[1][1].body), settingsPayload(settings));
    assert.deepEqual(Object.keys(settingsPayload(settings)).sort(), ["max_tokens", "prompt", "revision", "voice_instruction"]);
    assert.equal(calls[1][1].signal.aborted, false);
  } finally { globalThis.fetch = prior; }
});

test("stale, network, and malformed responses are never reported as applied", async () => {
  const prior = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(null, { status: 409 });
    await assert.rejects(requestSettings(settings), /Another tab/);
    globalThis.fetch = async () => { throw new Error("Offline"); };
    await assert.rejects(requestSettings(settings), /Offline/);
    globalThis.fetch = async () => Response.json({});
    await assert.rejects(requestSettings(), /Invalid settings/);
  } finally { globalThis.fetch = prior; }
});

test("mobile prompt controls use labeled textareas and radios with explicit scope", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const source = await readFile(new URL("../src/live-controls.ts", import.meta.url), "utf8");
  assert.match(html, /for="conversation-prompt"/);
  assert.match(html, /for="voice-prompt"/);
  assert.match(html, /reset when the server restarts/);
  assert.match(html, /These samples do not change the conversation voice/);
  assert.doesNotMatch(html, /<select/);
  assert.match(source, /radio.type = "radio"/);
});
