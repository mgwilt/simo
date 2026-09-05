---
type: Evidence Record
title: Recipe-bound progressive experimental playback
description: Bounded player credits, reserve comparison, exact retained-PCM replay and actual served policy without physical or Fast acceptance.
tags: [work, breeze, mlx, streaming, playback]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T08:35:28Z }
sources:
  - id: stream-errors
    resource: https://streams.spec.whatwg.org/#readable-stream-error
    title: WHATWG Streams error and reader closed semantics
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-013
  authority: evidence
  repository_paths: [web, python/simo/preview_site.py, python/simo/cli.py, tests/python/test_preview_site.py]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Recipe-bound progressive experimental playback

T-014 implements D-016 only on the isolated experimental site. Quality/default/unknown policies keep complete-clip playback. Fast remains rejected. Model, fork, codec, dependency and inference settings are unchanged from [E-012](E-012-experimental-serving.md).

## Policy and failure contract

The operator must select the exact loaded fingerprint with `serve-preview --streaming-runtime`. The site checks that fingerprint and the unaccepted mlx-int8-v1 identity on health/listing/audio requests; stale identity returns503. Site health/listing and PCM/WAV response headers identify mlx-stream-v1. The page checks the response fingerprint and policy before posting any PCM. Unknown policy falls back to complete-clip buffering; malformed identity for a known streaming policy fails. There is no UI mode selector or immutable-profile change.

Streaming starts/rebuffers at15,360 frames (640ms at24kHz). Posted-minus-acknowledged-consumed credits cap in-flight worklet PCM at48,000 frames (two seconds), including messages not yet consumed. Each transfer is at most4,800 frames. Credit checks are integer/monotonic and cannot exceed posted frames. Worklet ring storage has the same two-second bound. The existing120-second total-response cap, sample alignment, short EOF handling and complete-only server cache remain. This does not claim a bound on browser-internal network buffering.

State distinguishes buffering, playing, rebuffering, draining, complete, stopped and failed. A late response failure may follow already played experimental audio; queued audio is stopped/cleared and the original failure retained, with no false completion or partial cache. Stop settles even when credits or reader cancellation are stalled. A stream can error while the player is waiting for credits rather than calling read; monitoring reader.closed detects that independently. Deliberate abort/release cleanup cannot replace the original error.[^stream-errors]

## Reserve selection and exact replay

Independent [R-114](../results/R-114.md) compared480/640ms reserves across75 retained arrival traces. Both avoided recorded gaps.640ms cost about107ms overall p95 in that queue screen but tolerated the tested500ms post-start tail delay;480ms failed that synthetic500ms case. Neither proves arbitrary LAN jitter tolerance. Root selected640ms before the held-source implementation review.

The reusable CLI loads the actual PreviewPlayer and actual PCM worklet/queue. It replays retained PCM bytes with recorded arrival/EOF times, structured-clone transfers, simulated MessagePorts/context setup/output timestamps and a128-frame24kHz render clock. It verifies every rendered sample in order, completion, credits, ring capacity and interior gaps. Producer-only reports need a synthetic wire fingerprint, explicitly marked; actual HTTP reports retain their real identity. No browser or computer-use automation ran.

| Retained cohort | Clips | Simulated first-render p95 | Recorded-trace gaps |
|---|---:|---:|---:|
| Matched producer short control |30|0.784s|0|
| Matched producer long control |6|0.805s|0|
| Matched producer short resident |30|0.779s|0|
| Matched producer long resident |6|0.795s|0|
| Actual HTTP seed17/29 screen |2|0.672s|0|
| Actual HTTP seed17 repeat |1|0.704s|0|

All75 complete with exact PCM; maximum outstanding and ring occupancy48,000 frames. These are simulated first-render times, not fresh tap-to-playback measurements. The72 producer traces retain E-011's prior source and idle-residency provenance; the three actual HTTP traces retain E-012's service source. Replaying them does not rerun the model or resident holder. The post-review network-error fix gives a byte-identical replay report.

```sh
node web/scripts/replay-preview.mjs \
  .artifacts/breeze-performance/mlx-int8-matched-control-short.json \
  .artifacts/breeze-performance/mlx-int8-matched-control-long.json \
  .artifacts/breeze-performance/mlx-int8-matched-resident-short.json \
  .artifacts/breeze-performance/mlx-int8-matched-resident-long.json \
  .artifacts/breeze-performance/mlx-experimental-http-seeds-v1.json \
  .artifacts/breeze-performance/mlx-experimental-http-repeat-v1.json
```

Report `.artifacts/breeze-performance/mlx-stream-v1-player-replay-v2.json` SHA256 e4bda0a3f3468b906472b0a2ea77797148a111be01518ad6692e5514f5b5658d includes all six input hashes, source identities, per-clip results and proof limits. It is identical to the preceding replay file; neither report includes real browser scheduling, network backpressure, new LAN jitter, physical sound or perceptual acceptance.

## Actual serving and regression checks

After independent review, only the experimental HTTPS process was stopped (exit130/listener released) and restarted with the exact f0cac89f955ee07d3f1b1bfac9d2cd8f5a2e1be5dcdb8ae4be828c66cdb24acd fingerprint. It is now PID56024/session69335 at https://192.168.1.83:8444. Site health/listing advertise mlx-stream-v1. Three real TLS stream/WAV pairs carry the correct policy/fingerprint, match cached PCM exactly, and are explicitly HIT; no model request occurred. No cache was archived/deleted or fake fingerprint created. This check is not uncached performance evidence.

All five served candidate assets equal the separate build: HTML646d5798…, JSab22d72b… (`preview-DMfs9KbU.js`), CSS4062580e…, workletf6faa037…, queue3170373c…. All five normal Quality assets still equal their original web/dist hashes. Quality PID46660/7860 and UI47503/8443 are unchanged; Quality is ready/nonbusy with fingerprint7d52e5a4dfa21507711928e32a26a758ecca1fb93871e8c9afefedd6dc05c96b. Candidate inference PID98272/7861 remains ready/nonbusy with unchanged f0cac89f… and service executable d4ba5fd3…. Same-host LAN-IP HTTPS uses the existing verified CA/certificate, not a second Wi-Fi device. Full report `.artifacts/breeze-performance/mlx-stream-v1-served-proof.json` SHA256 7b679d8f2fbf8c45a7a841c3d4bb01c9d92236a384f3fe0138a2e066120b3fce retains exact asset/PCM/runtime identities.

36 web tests and TypeScript checks pass. New tests use actual player/worklet code for reserve/short EOF/odd chunks, delayed/lost credits, Stop/stalled cancellation, late failure/immediate retry, failure while waiting for credits, stale policy/identity, rebuffer/gap, exact120-second/oversized and invalid-credit boundaries.136 full Simo Python tests include five preview tests with actual ASGI cache/header/policy/stale-identity checks. Full parent Ruff/format/ty/basedpyright and separate Vite build pass. Fork/native code is unchanged; E-012's171 overlay/83 locked with three optional skips/native gates are retained, not rerun here. Documentation and knowledge results are in [verification](../verification.md).

R-114 found delayed network-error handling during credit waits; root added reader.closed monitoring and the failing regression, then the reviewer independently reran36 tests/TypeScript and confirmed immediate error, queue clearing, preserved message and no subsequent render. No remaining finding in the held scope. Initial pre-fix tests are not counted as proving this failure path. [R-115](../results/R-115.md) scopes the next uncached full HTTPS corpus/resident measurement; it is advice, not an implemented endpoint.

## Held source

Simo base2ffe040/fork a294fe4 plus preserved dirty paths; no commits/pushes. E-012's fork/model/service executable identities are unchanged. T-014 SHA256:

| File | SHA256 |
|---|---|
| web/src/preview-player.ts |a028664e764ec19f591e57325597c4de62ac5a43c4235e2f06a42c732f7a77bd|
| web/src/preview-only.ts |bbb32170a4c8dbf336bc81461a00e356cf7ca34e20afda61d89d914a02cddfe1|
| web/public/pcm-worklet.js |f6faa0370ea51524644e248df1714d2dd14eba1bcb7f719a72e92613fa6350f2|
| web/public/pcm-queue.js (unchanged) |3170373c677a320aeb4d4ef3a8b75590f2e15bb9d8e060e172d7f3baa4dd39f4|
| web/tests/preview-streaming.test.mjs |1933ac1cdd06ddb61e628c2ee86ba6bb3e537160a68dd1889f9f863e1ccf63e4|
| web/tests/helpers/playback-harness.mjs |37e648c00132a27a186d29237cff3b46ca9a7fa71977e8e2c7a2923edf97e5e1|
| web/scripts/replay-preview.mjs |63760a5e094380be8d676d82a5702a9ad3e22dbe48b99eff526bc0a8b7d907a4|
| python/simo/preview_site.py |e5de3e70070f92cf5d3a126433924d3743b8aa4fe08dc2a856e238375e92d915|
| python/simo/cli.py |1c073065f7c383948bed46f599c54dc0160bf983962eb331f7fb09e777b27d8e|
| tests/python/test_preview_site.py |d103cac6bf021e078cfbd49283e1ebda0a44d4437670cae2e6c9983135bb4026|

The CLI's preview-local settings rename only fixes static narrowing; no normal serve behavior changes. No inference/model/codec/lock/identity/trust-store changes, training, publication, external data transfer or computer use. Fast/A-006/A-007 and the autonomous goal remain open.

[^stream-errors]: WHATWG Streams, ReadableStreamError and reader generic release algorithms, verified2026-09-05. Reader.closed rejects on a source error; releaseLock also rejects the closed promise, requiring the deliberate-cleanup guard. Primary specification: https://streams.spec.whatwg.org/#readable-stream-error.
