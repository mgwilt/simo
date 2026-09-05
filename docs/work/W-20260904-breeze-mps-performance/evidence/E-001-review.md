---
type: Evidence Record
title: Breeze performance starting review
description: Breeze performance starting review for bounded M3 Ultra implementation and evidence.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-04T22:48:33Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-001
  authority: evidence
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests, docs]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Breeze performance starting review

Source: clean Simo 2ffe040 and fork a38d7d1, inspected 2026-09-04 by the root integration task and three read-only reviewers.

Findings: CFG depth decoding repeats two uncached growing-prefix forwards per remaining codebook; the eager adapter emits only after complete generation; the Python read coalesces up to 48000 bytes; the preview server/browser await complete WAV/blob; cache identity excludes effective recipe; qwen-tts 0.1.1 pins Transformers 4.57.3.

A read-only delayed socket fixture in the review showed read1 yields the initial 4800-byte chunk immediately while read(48000) waits for the remaining fixture stream. This is transport behavior, not model speedup evidence.

Proves: implementation opportunities and risks supporting T-001 through T-005. Does not prove: accelerated MPS correctness, achieved latency, quantized quality, Safari playout or any new acceptance gate.

Historical model/host results remain [E-007](../../W-20260802-conversational-identities/evidence/E-007-breeze-apple-silicon-lan.md).
