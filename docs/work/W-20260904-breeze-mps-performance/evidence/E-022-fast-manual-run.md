---
type: Evidence Record
title: Fast MLX manual Simo run
description: Fast MLX manual Simo run without running or claiming skipped release acceptance.
tags: [work, breeze, runtime]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T16:48:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-022
  authority: evidence
  repository_paths: [services/breeze/serve.py, python/simo/config.py, python/simo/lan_site.py, python/simo/livekit_runtime.py, docs]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Fast MLX manual Simo run

T-022/D-018: user explicitly requests skipping acceptance testing and running Simo using the fast configuration for personal testing. Root inspected startup prerequisites and served availability only; no acceptance corpus, speech-generation probe, microphone/audio, browser/CUA or new implementation was run. Formal gates remain historically unverified, not falsely passed. The reserved released-Fast CLI selector remains disabled; this launch selects the already implemented mlx-int8-v1 candidate.

## Actual startup

At16:41Z the previous7860/7861/8443/8444 services were absent; no existing service was terminated. Normal default alias storage was empty. Root selected the prior Breeze Preview alias852214f4-d474-4e88-b1ac-516e48fa8328 from .artifacts/breeze-proof-data, unchanged persona/profile version1, whose schema is runtime-profile.v2 with Breeze voice_design/CFG4/seed42. The current LAN address192.168.1.83 and existing certificate SAN were verified. Explicit certificate hostname mikesMacStudio.local avoids the machine's differing discovery name.

Commands, with existing files/caches only:

```sh
PYTHONPATH=vendor/breeze-tts UV_CACHE_DIR=/private/tmp/simo-uv-cache \
uv run --offline --project services/breeze --frozen --with mlx==0.32.0 \
  python services/breeze/serve.py .models/Breeze-TTS-2 \
  --host 127.0.0.1 --port 7861 --device mps --experimental-recipe mlx-int8-v1

SIMO_BREEZE_ENDPOINT=http://127.0.0.1:7861/v1/audio/speech \
SIMO_TTS_CFG_SCALE=4 UV_CACHE_DIR=/private/tmp/simo-uv-cache \
TIKTOKEN_CACHE_DIR=.cache/tiktoken uv run --frozen simo \
  --data-dir .artifacts/breeze-proof-data serve \
  --alias 852214f4-d474-4e88-b1ac-516e48fa8328 \
  --hostname mikesMacStudio.local --node-ip 192.168.1.83 \
  --cert .artifacts/breeze-performance/tls/lan.pem \
  --key .artifacts/breeze-performance/tls/lan-key.pem --https-port 8443
```

Engine PID74829/session90260 reports ready/nonbusy, torch-prefill-mlx-decode, mlx-affine-int8-group64, source d866f8038f31cbd59f7c25ba362e87ba542773de79747cf2f744b636ce18d739 and runtime6968213c4f48391589a4baee8631983091e53e372d61ba51ef93a1669a12c506. Release_accepted remains false. Existing tokenizer/SoX/flash-attn startup warnings occurred; startup completed. No model reload recipes or dependencies were changed. One harmless exploratory import guessed a nonexistent persistence subpackage; actual CLI/persistence module discovery corrected that diagnostic.

Full Simo PID76219/session36625 supervises LiveKit76256 and Caddy76257; loopback inference7861, LAN HTTPS8443, WebRTC TCP7881/UDP7882. Doctor live reported all required prerequisites ready. Trusted-CA CLI GET / and /api/health return200/ready; /api/previews returns200 after its backend fingerprint lookup. It does not publish the fingerprint in its JSON, so a diagnostic null there is not actual missing runtime identity. Engine last_request was empty: no speech probe was performed. Active local conversation44b866ce-e8a2-4136-a720-e109a9d0e29d was created by normal startup. Prior conversations and listening-results database remain intact. The separate8444 listening site is not running in this launch.

## Proof boundary

[E-021](E-021-mobile-results.md) retains previous mobile/server-result implementation and its tests. [R-134](../results/R-134.md) independently confirms endpoint/profile compatibility without tests or network. No immutable alias/profile/default/code changes, new downloads, trust changes, commits or pushes. Full conversation uses incremental LiveKit PCM, not the preview-only640ms policy; actual spoken behavior is for the user to test now.

URL: https://192.168.1.83:8443. Tap Start conversation. This record proves startup, selected local backend, normal active conversation state and trusted HTTPS reachability—not physical audio, a full conversation, release latency or acceptance. Freshness is this launch only; process/ports require rechecking after host/session changes.
