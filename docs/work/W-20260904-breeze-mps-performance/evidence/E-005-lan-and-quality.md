---
type: Evidence Record
title: Scripted LAN delivery and speech screening
description: CLI-only HTTPS, cache, cancellation and local-ASR evidence with physical playback limits.
tags: [work, breeze, performance, lan, verification]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T00:37:58Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-005
  authority: evidence
  repository_paths: [python/simo/breeze.py, scripts/evaluate_breeze_audio.py, web, tests/python]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Scripted LAN delivery and speech screening

Source: Simo2ffe040 plus this plan's implementation; loaded unquantized SDPA source digest4c15d98721ee6f955d32ad592ff04c6e66ca9154254a1827de39029070bbb7e5; model digest aebc74eac29ac4729fdf0f8c4d3870c1d8cf4efb72e4e24e9316accaa386462d. Root verifier on M3 Ultra,2026-09-04 local date.

Command: `simo breeze verify-preview --url https://mikesMacStudio.local:8443 --connect-address 192.168.1.83 --ca-file <existing-mkcert-rootCA.pem> --json`. No browser/computer use. Explicit CA verification and hostname/SNI were retained; mDNS did not resolve on this host.

PASS: first PCM at0.442s while generation remained busy; disconnect released inference and no partial preview cache appeared. Immediate retry and all three existing voice instructions completed. Warm/bright/grounded first PCM0.338/0.534/0.498s; durations4.80/3.20/5.04s. Legacy WAV replay was a cache HIT and PCM was byte-identical. Artifact .artifacts/breeze-performance/lan-preview-proof.json, SHA256 e250ead27198921945b631bde98e75955f0f1e5111a066f9536e952d78a95f87. Initial probe incorrectly demanded sample alignment from individual TLS reads; corrected, since transport boundaries may split samples. Final review added per-voice stream/WAV format checks and separated stream duration from cache replay timing, with regression tests.

Local ASR screen: `uv run python scripts/evaluate_breeze_audio.py <sdpa-30-samples.json> <int8-screen.json> <int4-screen.json> --resident-screen --long-audio-dir <artifact-directory>`. Existing pinned Parakeet transcribed the30 SDPA WAVs: aggregate word error rate0.003401 (one error/294 reference words). The three int8 and three int4 WAVs each screened at0WER. This is not perceptual or instruction acceptance.

The same process held pinned Parakeet and Qwen3.5-4B-4bit resident after exercising them. Bounded short screen (one warmup, three prompts, seed42) p95 steadyRTF3.197; two long passages, seed42, produced27.84/31.04s of audio at steadyRTF2.995/2.924 and both reached EOS. This is not the full30-case resident release suite. Artifact asr-resident-screen.json SHA256 ad07cac391f38cc9f0b787503e520ea565cc29f5ca91d7d6f58e84b5ebbfbb34.

Long WAVs were separately transcribed by piping `jq '.resident_screen.long'` into the evaluator through /dev/stdin. Both final sentences were present; one transcript split “tradeoffs” into “trade offs” (2 edit operations), the other matched after punctuation normalization. Artifact long-asr-screen.json SHA256 f284090887d2cdd89b92cee2daa36973108eee2c942301df48a8f3a43b35bf98.

Limits: no physical playback, tap-to-audible timestamp, actual underrun count or matched listening is claimed. The user requested CLI/script verification and avoidance of computer use; no further browser automation was attempted. Worklet tests prove bounded scheduling mechanics, not sound at a device.

LAN handoff: DHCP changed the host IP to192.168.1.83. A new leaf certificate under .artifacts/breeze-performance/tls covers that address using the existing CA; old certificates were preserved and no trust store was changed. CA-explicit HTTPS health at https://192.168.1.83:8443 passed. Clients still need to trust that CA; this host's system trust was not assumed.

Final Quality/current-IP rerun against fork a294fe4 passed the strengthened verifier: first cancelled PCM0.528s while generation was busy, lock released, no partial cache, immediate retry, exact24k/s16le metadata and mono PCM16 WAV comparison for all three voices. First completed-preview PCM0.394/0.460/0.477s; all three are cached. Artifact: final-quality-lan-proof.json. Server was left in Quality, not the faster experimental SDPA recipe.
