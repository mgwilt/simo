---
type: Evidence Record
title: Blinded listening and fresh device trial interface
description: CLI-prepared immutable recordings, user-operated playback and local export are verified without claiming acoustic acceptance.
tags: [work, breeze, playback, quality, lan]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T12:52:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-019
  authority: evidence
  repository_paths: [python/simo/breeze_listening.py, python/simo/preview_site.py, python/simo/cli.py, web, tests/python, docs/work/W-20260904-breeze-mps-performance]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Blinded listening and fresh device trial interface

T-019/L-017, root sole writer. Base Simo2ffe040c322139174ffd8269625c8a34dcd66ccd/fork a294fe402eda72b7330dd30fd977c829e72137db plus all prior dirty work preserved. Engine/model/codec/kernel/lock/identity/default recipes were not changed. The four-arm source experiment and historical failed/shared/new quality flags remain [E-018](E-018-component-precision.md); this stage supplies a user-operated acceptance interface, not another model promotion.

## Implemented contract

The CLI adds prepare-listening and verify-listening; serve-preview optionally accepts --listening-deck. Preparation pins comparison c3deab334d425ba14e9b694c07a9ec18990126fcce7dce42f02775cb75bc95a5 and joins all four named producer reports to18 exact text/instruction/seed cases. It checks completed/EOS/noncancelled unique request IDs, whole WAV and PCM hashes/counts, and copies all72 timed clips unchanged into an exclusive directory. Twelve warmups are excluded by schedule, not audio-hash deduplication. Case order and each A–D recipe mapping are randomized independently.

Only opaque allowlisted PCM routes are exposed. The public deck contains text/instruction/seed, opaque IDs, labels, audio hashes/counts and a private-key content commitment. Recipe, source, request and ASR mappings remain private. Symlinks, malformed/oversized artifacts, query/body overrides, stale deck requests and changed/truncated audio fail closed. The same checked bytes are returned, with RECORDED metadata and no live fingerprint/request ID. Full PCM body hash/count verification occurs before the complete-buffer worklet receives EOF.

The separate fresh panel uses the existing fixed short/long/instruction/seed route. Requests require BYPASS, exact manifest/runtime/policy and unique actual IDs. At transport EOF the worklet is sealed immediately; matching producer completion is then retrieved with bounded409 retries and a five-second abort deadline. Completion requires validated producer sample/frame/EOS state and playback drain. A later request cannot substitute for unavailable evidence. Stop propagates through fetch and the existing inference cleanup path.

Player construction happens only from a tap, after an attempt record exists. Setup failures, Stop, partial failures and retries remain exported. Recorded ratings include complete listening, intelligibility, full words, instruction, artifacts/gaps, uncertainty and notes; optional preference ties are allowed. User device/output/network conditions and subjective observations are separate. Download is local-only; no upload, microphone, conversational memory or automatic playback. Leaving the page loses undownloaded ratings.

The verifier checks structure and deck/key/clip identity, reports missing ratings and reveals recipe attribution locally. It never promotes Fast. Render/output-clock estimates and callback fallback are labeled separately; acoustic onset remains unmeasured. Browser-paced receipt is not unpaced producer throughput, and recorded playback measures no synthesis latency.

## Held source and independent review

| Source | SHA256 |
|---|---|
| python/simo/breeze_listening.py |95050d41d079ed422a22e7ccbefe7abc346af2a170037934b0d68b85ff5ea876|
| python/simo/preview_site.py |a4dd0ebd308d5d1f4ecb8a31141aa6bd0018f1e6888e8b356bd213435cfbe369|
| python/simo/cli.py |b4aec928af9ac1496ecbe2a93d3cb7ac12ae021c3558d39d4b300c5029eb368f|
| web/src/listening-review.ts |5345e8fb864b3295dad0c11345a0ec30f4443484c8409904af60d21ec60430d1|
| web/src/preview-player.ts |ffad65280c941531453d73aef27509fa0d344454f0f4f8e73abb64dd5aaa755c|
| web/src/preview-only.ts |9e1231fb95f2d3aff0667294f9be0fb1c526ee5cd8f08aae776c7c9cf6aaec07|
| tests/python/test_breeze_listening.py |d220c49bd8565117cf5fd5b552dedf328f68521a64916d4b70cf2fd041c5a2ba|
| web/tests/listening-review.test.mjs |c1571546c1a9e7a196769d7d9443b37db5f3eeef71d76b0082ad5ee6e3b37ca1|
| web/tests/preview-player.test.mjs |210087118606f9ff05182125229710e28c1d12fd465795c78506e83f42724658|

[R-129](../results/R-129.md) independently found and verified the private-mapping correction: changing any recipe/identity/ASR/request field now fails before attribution. Eleven focused Python tests and all72 actual unchanged WAV joins pass. [R-130](../results/R-130.md) found and verified the fresh-EOF/metrics race corrections;52 independent Node tests and TypeScript pass on unchanged held hashes. Configured CPU DOM coverage includes load/advance/export without player creation, constructor failure, busy controls, Stop and retry. Neither reviewer used a browser, model, network or audio device.

## CLI and actual LAN evidence

Preparation command:

```sh
UV_CACHE_DIR=/private/tmp/simo-uv-cache uv run --frozen simo breeze prepare-listening --comparison .artifacts/breeze-performance/mlx-precision-matrix-v1/comparison.json --expected-sha c3deab334d425ba14e9b694c07a9ec18990126fcce7dce42f02775cb75bc95a5 --output-dir .artifacts/breeze-performance/listening-v2
pnpm --dir web exec vite build --config vite.preview.config.ts --outDir ../.artifacts/breeze-performance/preview-listening-v1
```

V2 contains72 byte-exact WAVs,6,977,280 PCM frames/290.72s. Deck SHA417e0171a0e3a0b2cb30808da4e5fc1d8b1f5418b7560cb544225698a5a0338c; private-key file SHA1a4cf00309e9508a3c06d228f0f47236d09a4e35c8cb0411f4477a226e2ae761; its committed content hash7513dba228d9d6fcd51d70f3814fa9185b2996063672c2a46790481a96dd9df8. Initial listening-v1 remains unchanged as pre-review evidence, not the served deck.

Only the experimental HTTPS listener was gracefully reloaded after verified idle inference/no established8444 connections. Old PID90526/session5485 exited130 from intentional Ctrl-C; new PID82750/session83932 serves https://192.168.1.83:8444 with the existing certificate/key, new isolated assets, --enable-benchmarks, unchanged exact --streaming-runtime f0cac89f955ee07d3f1b1bfac9d2cd8f5a2e1be5dcdb8ae4be828c66cdb24acd and --listening-deck .artifacts/breeze-performance/listening-v2/deck.json.

CA/hostname-verified CLI requests compare all72 served PCM bodies and metadata to the deck; all match. Private-key/deck-file/raw-directory routes return404. All five served assets match the benchmark manifest40d5013b16f2064e75182598ef9f03131af7208a08daceff30e9e919031c7ca3. Build JS3cccc12a2e6e3cab4c89292b4a4e0d7b52a200c0b5857fb271665d6d5081032e, CSSc7cbf5b7e82ed1df0285fdd40a81949e850780620e639e932c379b989fcf0ca0 and HTML676f6b747fe7467ebdbeff30a7d97e9796c39be309c675c84a1b9325ff3476ff are retained. Queue/worklet sources are unchanged; full asset/source maps are in the fresh-smoke report.

One fresh CLI smoke used zero warmups, short limit1, default instruction and seed17, existing CA, new listening-v2/fresh-smoke directory. It completed request api-f66b171dac7349d3b0d03f15417911e4 with BYPASS, EOS,59,520 PCM samples/31frames/2.48s. First HTTPS PCM0.337416s, steadyRTF0.681963, totalRTF0.820113. This one sample is not a new p95 cohort or release claim. Report SHA532418812a3ece708486085e434253aea98b428ec1324a90132664167f1439ad; full PCM SHA7b5824c56965abe4b9567d4a9d0ca8d5e208257e5dd49087ca582a0a519b0c98. Existing CLI replay of that report is sample-exact with0 modeled underruns,0.730667s first render and29,568 maximum outstanding frames, below48,000. Replay clocks/ports are simulated, not device proof.

The CLI verify-listening command also validates an explicitly empty synthetic export:0 rated/72 unrated/0 attempts, quality_accepted=false, acoustic_onset=unmeasured. Its fixture SHAbbfdf81a454d7e22688dae6bac91f31f947d9401523ce116c8c2ad1c411ee472 is not user feedback.

## Gates, retained failures and limits

Final fork regression with existing local Metal access passes200 tests in4.11s. Its first sandbox invocation passed136 CPU tests and failed64 MLX cases because no Metal device was available; the same unchanged source/command passes outside that restriction. No new model benchmark or CUDA validation is inferred. Docs144/zero errors/four warnings and five knowledge tests pass; the additional operational/execution size warnings remain diagnostics, not conformance failures. The linked operations leaf is kept atomic with its existing launch/TLS/preview contract for now. No source was changed after final reviewer holds. A newly observed untracked51-byte :memory:.ses file is left untouched because its ownership was not established; it is not staged or included in the result.

Root173 canonical Python tests pass with TIKTOKEN_CACHE_DIR=.cache/tiktoken;52 Node tests, TypeScript, full parent Ruff/format/ty/BasedPyright, five knowledge tests and diff checks pass. Both separate preview build and normal UI build pass; the latter writes only listening-v2/normal-ui-build, preserving original web/dist/served8443 assets. Native source is unchanged and its boundary tests are included; no new native build claim.

Initial development lint/type errors and Node strip-only parameter-property syntax were corrected before final holds. Initial full Python invocation omitted the required token cache, failed unrelated knowledge DNS lookups and stalled a dependent test; root identified/interrupted only child75360 (session63928 exit130), then reran173 cached tests successfully in13.878s with no download. The first custom HTTPS verification used case-sensitive dictionary header lookup and failed its diagnostic assertion; normalized header names reran all72 checks successfully. Both independent review failures remain recorded above; no failed attempt counts as acceptance.

Quality127.0.0.1:7860 remains PID46660/session62395 with fingerprint7d52e5a4dfa21507711928e32a26a758ecca1fb93871e8c9afefedd6dc05c96b; experimental inference7861 remains PID98272/session98210 with f0cac89f… and its prior loaded source/recipe, not the later mixed-precision source. Both freshly report ready/nonbusy. Original LAN UI PID47503/session8514 https://192.168.1.83:8443 and new8444 page both return200 with existing CA/hostname verification.

Proves: bounded implementation, unchanged comparison clips, identity/private-key integrity, configured CPU UI/player behavior, actual trusted-LAN serving and one uncached request/replay. Does not prove: user listening, real browser downloads/gestures, acoustic onset, remote Wi-Fi, physical underruns, perceptual acceptance or a Fast release. No Safari/CUA, microphone, autoplay, trust changes, external/private-data transfer, paid compute, commits or pushes. Quality remains default; Fast disabled. The next useful gate is user-operated listening/device observation and a downloaded export, not further tuning solely against fixed ASR flags.
