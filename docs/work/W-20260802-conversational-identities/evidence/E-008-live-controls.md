---
type: Evidence Record
title: Live prompts and longer conversation replies
description: Verifies bounded session-local settings, speech grouping, cancellation and a longer local-model reply without physical playback claims.
tags: [evidence, livekit, lan, voice, prompts]
status: draft
generated: { by: process:simo-conversation-integration, at: 2026-09-05T17:25:00Z }
simo:
  profile_version: 1
  stable_id: W-20260802-conversational-identities-E-008
  authority: evidence
  repository_paths: [python/simo/live_controls.py, python/simo/lan_site.py, python/simo/livekit_runtime.py, python/simo/config.py, python/simo/adapters/livekit, tests/python, web]
  owner: process:simo-conversation-integration
  work: { parent_id: W-20260802-conversational-identities }
---
# E-008: Live prompts and longer replies

T-011/A-018 source state: Simo `2ffe040c322139174ffd8269625c8a34dcd66ccd` plus the bounded L-022 edits above and pre-existing uncommitted performance work. Root made no engine/dependency/immutable alias/profile changes and no commit or push. Python3.13/macOS M3 Ultra, existing frozen environment; LiveKit API behavior checked against current upstream docs using Context7 and the installed implementation.

## Findings and executable checks

The live adapter hard-coded one/two sentences under35 words; environment text budget was64 tokens; this alias's actual persona said “Respond briefly and naturally for voice testing.” The profile's historical `prompt` and `response` fields were not read by the live resolver, so those fields alone were not the effective cause. Breeze receives the intended generic instruction and fixed CFG4/seed42, but LiveKit previously began a separate instruction-only generation for each sentence. R-101 records the distinction between voice design and persistent speaker conditioning.

With `UV_CACHE_DIR=/private/tmp/simo-uv-cache` and `TIKTOKEN_CACHE_DIR=.cache/tiktoken`, root ran:

| Check | Result |
|---|---|
| `uv run --frozen python -m unittest discover -s tests/python -p 'test_live_controls.py' -q` | 7 passed: revision/type/size/origin validation, job snapshots, canonical instruction replacement, Qwen rejection, multi-sentence grouping, Unicode/unbroken overflow and cancellation/retry |
| Same command with `test_livekit*.py`, `test_config.py`, `test_lan_site.py` | 25 +5 +4 passed |
| `uv run --frozen --extra dev ruff check python/simo tests/python`; corresponding `ruff format --check` | Pass;90 files formatted |
| `uv run --frozen --extra dev ty check --error-on-warning`; `basedpyright` | Pass, no diagnostics |
| `pnpm --dir web check`; `test`; `build` | Pass;61 tests; production HTML/CSS/JS built |
| Text-only `LocalLLM(MLXTextGenerator(config.text.local_path), live_controls=...)` | Asking for6–8 complete sentences about autumn leaf colors, with a non-brief prompt and1024-token budget, produced7 complete sentences/213 words/1378 characters; no audio or transcript injection |
| Documentation validator; knowledge regression; `git diff --check` | Pass;5 knowledge tests. Existing four advisory warnings remain; operations length increased |

Independent review R-102 found and then confirmed fixes for per-turn system-instruction preservation and a limit-one passage-loop edge case. Full model/listening/performance acceptance, browser automation and microphone use were not run.

## LAN deployment

Final reviewed reload: CA-validated IP GET/PUT/readback again confirmed revision1,1024 tokens, the intended prompt, unchanged voice, CFG4/seed42 and served controls. The configured `mikesMacStudio.local` name failed local DNS resolution, so the handoff uses the verified IP link rather than claiming both URLs work.

Resume conversation `44b866ce-e8a2-4136-a720-e109a9d0e29d` for existing alias `852214f4-d474-4e88-b1ac-516e48fa8328`, using `.artifacts/breeze-proof-data`, hostname `mikesMacStudio.local`, node IP `192.168.1.83`, existing `.artifacts/breeze-performance/tls/lan.pem`/`lan-key.pem`, HTTPS8443 and the existing Fast endpoint `http://127.0.0.1:7861/v1/audio/speech`. Prefix normal `simo serve` with `SIMO_BREEZE_ENDPOINT` and `SIMO_TTS_CFG_SCALE=4`; no inference restart or model promotion.

CA-validated urllib requests verified the new static form and `GET`/same-origin `PUT /api/controls`. Applied revision1 uses a non-brief, user-request-matching conversation prompt and1024-token budget, while preserving the original voice instruction, CFG4 and seed42. The running Fast service reports fingerprint `6968213c4f48391589a4baee8631983091e53e372d61ba51ef93a1669a12c506`, source digest `d866f8038f31cbd59f7c25ba362e87ba542773de79747cf2f744b636ce18d739`, ready and `release_accepted=false`. Startup initially rejected a missing task index; the index was added and validation passed before successful startup.

Proves: bounded live control/data flow, retained in-flight selections, longer text-generation capability, grouping without dropping suffixes, scripted cancellation, and verified LAN delivery of the revised UI. Does not prove: stable cross-turn speaker identity, actual mobile layout/playback, long speech EOS on arbitrary inputs, timing/underrun targets, semantic quality, or formal Fast acceptance. Settings are intentionally process-local; restart restores defaults. No old integration evidence is rewritten.
