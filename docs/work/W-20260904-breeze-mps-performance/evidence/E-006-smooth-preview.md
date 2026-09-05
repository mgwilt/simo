---
type: Evidence Record
title: Smooth bounded preview buffering
description: Scripted queue and player proof for complete-clip preview buffering with explicit latency and physical-playback limits.
tags: [work, breeze, playback, buffering]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T04:34:40Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-006
  authority: evidence
  repository_paths: [web, docs/operations/lan-voice-site.md]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Smooth bounded preview buffering

Claim: the preview player waits for validated EOF before rendering, with bounded memory, cancellable loading/playback, exact sample preservation and no simulated starvation from recorded slow arrivals. Source: Simo2ffe040 plus prior performance changes and this web-only fix; fork remains clean a294fe4. No inference/model/identity/cache-key changes.

Method: `pnpm --dir web test` passes25 queue/worklet/player tests, including exact120-second capacity silent until EOF, one-frame overflow, odd boundaries, incomplete/error/empty responses, Stop during setup/buffering/drain and immediate cached retry. Independent review found and root fixed processor errors losing their reason during a pending read; the new regression and reviewer rerun pass. TypeScript and Vite build pass. The worklet explicitly gates on EOF; merely setting a large threshold would start at exact capacity before validation. It owns all samples before playback, eliminating main-thread refill dependency.

Replay command (no GPU/browser):

```sh
node web/tests/replay-arrivals.mjs \
  .artifacts/breeze-performance/final-quality-screen.json \
  .artifacts/breeze-performance/sdpa-30-samples.json \
  .artifacts/breeze-performance/asr-resident-screen.json
```

At24kHz with128-frame render ticks, old240ms startup produces44 gaps across3 Quality clips,448 across30 SDPA clips,192 across2 resident-model long clips. Complete-clip gating produces zero modeled gaps and identical consumed frames in all35 traces. Quality first-play times become16.31–19.99s; resident long clips83.99–91.26s. This explicitly fails Fast tap latency, rather than satisfying it through buffering.

Current LAN HTTPS proof used Node fetch with `NODE_EXTRA_CA_CERTS` pointing to the existing mkcert rootCA.pem; no trust changes or certificate bypass. At https://192.168.1.83:8443, served JS/worklet/queue exactly match local SHA256 values:

- index-CDzSbNav.js (including reviewed error fix): 6b054a7c2eb476983370176d22081fafe35d253ee0136e0eb84998d310da5824
- pcm-worklet.js?buffered-v1: 6bb697bcc9abcc7c684a61c34248149c84044376957856ff2a9251ce287c2f38
- pcm-queue.js?buffered-v1: 3170373c677a320aeb4d4ef3a8b75590f2e15bb9d8e060e172d7f3baa4dd39f4

All3 current Quality presets are cache HIT with valid24kHz/s16le responses. Complete cached HTTP fetches took2.70–3.36ms on the host for4.08–4.72s audio. These are fetch timings, not audible start or a remote-device LAN measurement. UI owns the new buffering explanation instead of displaying the older server render_note. Versioned worklet/queue query URLs avoid reuse of the former early-play implementation.

Proves: bounded scripted player behavior, recorded-arrival replay, actual served assets and cached PCM reachability. Does not prove: physical audio quality, remote-device scheduling, conversational smoothness, or Fast latency/throughput. Verifier: root integration process; freshness2026-09-05. Historical E-005 and identities E-007 remain unchanged.
