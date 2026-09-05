---
type: Work Acceptance
title: Breeze performance acceptance
description: Breeze performance acceptance for bounded M3 Ultra implementation and evidence.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T11:32:57Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-ACCEPTANCE
  authority: coordination
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests, docs]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Breeze performance acceptance

- [x] A-010: README charts and technical specifications reproduce recorded measurements from checked-in data; matched comparisons, chronology, source/settings provenance, sample counts, units, and experimental/quality limits are explicit. Flecs copy removed from README; fork remains untouched. Eleven chart tests, independent source/data audit and documentation/static gates pass without rerunning inference; [E-024](evidence/E-024-readme-benchmarks.md). This does not close A-001/A-006/A-007.

Current T-020: [E-020](evidence/E-020-process-startup.md) adds full process startup and first-use/warm measurements. Three fresh groups yield12 complete identical clips: launch-to-ready8.329–9.157s, first-use PCM0.939–1.337s, nine warm requests0.280–0.304s. These are observations, not p95/disk-cold/device proof. A-001's process-cold portion is now measured; A-001/A-006/A-007 remain open for actual playback/listening evidence. This supersedes the earlier missing-cold-start summary below, without changing historical results.

Current T-019: [E-019](evidence/E-019-listening-interface.md) delivers the blinded72-clip deck and separate fresh device trial interface at the experimental LAN page. CLI preparation/verification, cryptographic recipe attribution, configured CPU DOM/Stop/retry/export, exact served PCM and request-bound fresh smoke pass. No user ratings, actual audible onset or observed device underruns have been collected. A-001/A-006/A-007 remain open; this is an evidence-collection tool, not Fast acceptance.

Current T-018: [E-018](evidence/E-018-component-precision.md) validates the full four-arm84-output/72-ASR matrix. BF16 backbone/int8 depth reaches0.770 p95 steady RTF but introduces a previously clean case's flag; the reverse reaches1.008 and also adds a flag. All three shared flags persist. Neither hybrid earns quality or Fast promotion. T-019 now prepares user-operated matched listening and separate fresh-device evidence; A-001/A-006/A-007 remain open.

Latest T-017: [E-017](evidence/E-017-matched-quantization.md) validates42 full producer outputs/36 fresh ASR rows and all18 historical int8 PCM conversion checks. BF16 reduces selected flags7→3 but p95steadyRTF1.088 misses throughput; int8 repeats all seven at0.688. Four recipe-associated transcript differences justify selective-precision screening, not acoustic or instruction acceptance. Three shared flags, physical playout and full release remain unaccepted; A-001/A-006/A-007 are unchanged.

- [ ] **A-001 — Reproducible measurement:** Fresh warm/cold uncached results identify model, source, dependencies, effective recipe, output duration, frames, stage/first PCM and playback timings; historical evidence stays historical.
- [x] **A-002 — Progressive delivery:** Generation, codec and HTTP delivery remain incremental; buffers are bounded, sample-aligned, cancellable, and only complete previews enter cache. D-011 retains complete-clip playback for Quality/default previews. D-016 permits separately tested exact-runtime experimental streaming with640ms reserve/two-second credits; neither decision waives Fast latency acceptance.
- [x] **A-003 — Decoder correctness:** Cached batched CFG preserves branch ordering, sampling policy and precision; numerical/greedy tests and actual MPS execution cover EOS, input limits and reuse.
- [x] **A-004 — Candidate evidence:** Attention, compilation and 8/4-bit candidates are independently screened with actual shapes; rejected/unavailable candidates stay explicit. No unproved v5 migration or quantization promotion.
- [x] **A-005 — Operator contract:** Quality default, startup-only mode selection, immutable profiles unchanged, effective runtime fingerprints, and locked rollback. Unaccepted Fast recipes fail closed.
- [ ] **A-006 — Fast release:** Three warmups and ten prompts across three seeds, voice instructions and long utterances establish warm uncached p95 tap-to-playback <=2s, p95 steady-state RTF <=0.8, and zero observed underruns; repeat with other Simo models resident.
- [ ] **A-007 — Quality and physical playout:** Complete intelligible text, requested instructions, no truncation/repetition; matched listening and actual device playback are separate from automated scheduling evidence. No Safari or computer-use testing per user direction.
- [x] **A-008 — Regression and handoff:** Fork, Python/native/web/static/docs/knowledge gates pass; independent review, durable concepts and exact publication/no-publication state recorded. Unmet release/physical gates remain open.
- [x] **A-009 — Smooth preview buffering:** Quality/default preview buttons collect a complete, bounded clip before starting; delayed network arrivals cause no scripted playback gaps, incomplete/oversized responses never start, and Stop settles during buffering and playback.25 tests, independent review and [E-006](evidence/E-006-smooth-preview.md) establish that historical scripted gate. D-016's opted-in experimental exception uses640ms reserve/two-second credits, exposes rebuffering and stops queued audio on late failure, which may follow earlier playback.36 tests and exact75-clip replay are [E-013](evidence/E-013-progressive-playback.md); neither replaces actual audible acceptance A-007.

A-001 is partial: fresh attributed HTTPS/producer timings and retained-trace simulation are available; no new cold startup or physical onset measurement. Existing live Quality still fails sustained throughput. The isolated MLX candidate passes producer and ten full fixed HTTPS control/resident cohorts:252 timed clips with p95steadyRTF0.685–0.698, exact paired PCM and zero modeled playback gaps ([E-015](evidence/E-015-https-corpus-residency.md)). A-006 remains unaccepted without actual device playback and all release evidence. A-007 remains open: all seven non-segmentation ASR candidates persist across four recognizer paths; six exact-input Quality controls are clean while one shares the initial-A omission ([E-016](evidence/E-016-quality-localization.md)). These different sampled backends do not isolate quantization or establish an acoustic defect, matched listening or instruction adherence. Neither aggregate throughput nor simulated0.704–0.816s first-render p95 waives those gates. Checked items refer to bounded implementation/numerical/regression evidence, not perceptual or Fast release acceptance. See [verification](verification.md).
