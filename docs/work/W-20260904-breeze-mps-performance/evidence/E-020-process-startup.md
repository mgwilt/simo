---
type: Evidence Record
title: Process-cold startup and warm requests
description: Parent-clock startup measurements separate process launch, verified readiness and first complete PCM.
tags: [work, breeze, startup, performance]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T13:26:00Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-020
  authority: evidence
  repository_paths: [scripts/measure_breeze_startup.py, tests/python/test_breeze_startup.py, services/breeze]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Process-cold startup and warm requests

T-020 closes the missing process-startup portion of A-001, not its physical playback portion. Earlier load_s/uptime_s excluded process launch, imports and full weight hashing. Three fresh processes now measure parent monotonic launch through independently verified readiness, then the first request and three warm identical requests per process. Existing Quality and experimental services remained idle/resident; this is not the full other-model residency release suite.

## Method and identity

Root L-018 owns only the new script/tests and performance bundle. The probe uses exclusive artifacts, fixed local weights/locked overlay and loopback7862. It checks free port, live fresh-session leader, all listener process groups and exact runtime/source/recipe before synthesis. Source checks recur before requests. No hidden warmup occurs. Health polling is100ms with a90s startup deadline; verified readiness includes identity/ownership checks after health observation. Ready-to-request preparation is separate. Speech has a30s absolute retained-socket deadline, bounded PCM and a separate five-second exact-request producer-completion join.

Every attempt preserves bytes/arrivals, headers, actual IDs, completed/EOS/noncancelled metrics, full PCM/WAVs, settings and logs. First byte and first complete PCM16 sample are distinct. Failures remain addressable; uncertain cleanup prevents successor cycles. Fixed input: default-instruction first prompt, seed17, CFG4, unchanged sampling/precision/codec.

```sh
UV_CACHE_DIR=/private/tmp/simo-uv-cache TIKTOKEN_CACHE_DIR=.cache/tiktoken uv run --frozen python -m scripts.measure_breeze_startup --output-dir .artifacts/breeze-performance/startup-v1
```

Session19554 exited0. Report SHA49302b9a8548fdcfb1e3b7ccb39b9930c48845ed12b29a897687fb16f4645c0d. Held script SHA5da95272eb5ec405fb80b3dc1b1262aae8d3fbf310849a022962d7ded81c0bb8; tests SHA61df38d74a563f5b4dae731f36d789912ea95bbf52c6df2b3de6cb26b87525d6. Recorded script/helper/runtime source hashes remain unchanged before/after execution.

Current on-disk composite source d866f8038f31cbd59f7c25ba362e87ba542773de79747cf2f744b636ce18d739 produces new fingerprint6968213c4f48391589a4baee8631983091e53e372d61ba51ef93a1669a12c506, not older live experimental f0cac89f…. Model799624c0b4a1daa8db6d28bbd9850043c0270734/digest aebc74eac29ac4729fdf0f8c4d3870c1d8cf4efb72e4e24e9316accaa386462d; Torch2.9.1/Transformers4.57.3/Qwen0.1.1/MLX+Metal0.32.0 and exact mlx-int8-v1 settings/kernel inventories match [E-019](E-019-listening-interface.md) reference SHA532418812a3ece708486085e434253aea98b428ec1324a90132664167f1439ad. Both backbone/depth use affine8-bit/group64 weights, BF16 decode, TorchBF16 prefill and FP32 codec. No dependency or recipe change.

## Observed results

Seconds below are individual observations, not p95 estimates.

| Fresh cycle | Launch to verified ready | Launch to first PCM | First request to PCM | Three warm requests to PCM |
|---|---:|---:|---:|---|
|0|9.156571|10.561378|1.336947|0.304453,0.279774,0.280786|
|1|8.432018|9.447135|0.947230|0.281079,0.281684,0.283184|
|2|8.328704|9.339865|0.939121|0.290010,0.285978,0.287242|

Service-only load_s values3.582849,3.335166,3.274561 exclude5.05–5.57s of full startup and must not replace parent launch timing. Verified-ready to first POST adds67.9–72.0ms of ownership/source checks. First request EOF2.641–3.037s; warm EOF1.976–2.023s. No reboot or OS/filesystem-cache eviction occurred; readiness and loopback PCM are not acoustic or LAN tap-to-playback events.

All12 globally unique api-* IDs join31 codec frames/59,520 samples/2.48s each. Every full PCM SHA7b5824c56965abe4b9567d4a9d0ca8d5e208257e5dd49087ca582a0a519b0c98 matches all other requests and the historical reference. No failed/truncated model request occurred. [R-131](../results/R-131.md) independently verifies complete records, WAV/PCM, source/recipe pins, exact monotonic joins and epoch corroboration within5.6µs.

Leaders/listeners13469/13470,13736/13737,13985/13986 terminated by scoped SIGTERM after each cycle. Wrapper143 is intentional cleanup, not inference failure. Every group_gone=true record is corroborated by a later independent signal0 absence check; binding7862 succeeds. Four retained services remain unchanged: Quality46660/7860/7d52e5a4…, experimental98272/7861/f0cac89f…, Caddy47503/8443, listening82750/8444. Both inference services are ready/nonbusy with unchanged last requests. Existing-CA hostname-verified LAN checks pass and deck417e0171… remains served.

## Review, gates and limits

R-131 found/corrected an unintended two-second read timeout and one-byte first-PCM attribution;13 independent CPU fixtures pass on final held source. Root13 focused/186 cached Simo tests, full parent Ruff/format/ty/BasedPyright and diff checks pass. Initial fixture reads rejected macOS temporary-directory aliases; resolving fixtures fixes them without relaxing artifact symlink rules. Development lint/type failures preceded final holds. No fork/web/native changes or new build claims; T-019 gates remain historical.

Final knowledge gate:147 concepts, zero errors, four existing warnings (governance/operations/execution size diagnostics and stale Gepard); five knowledge regression tests pass. Source is held unchanged through final documentation checks.

All three logs retain ignored outer VIRTUAL_ENV, tokenizer-regex, optional SoX/flash-attn and shutdown resource-tracker semaphore warnings. Synthesis/identity/PCM and group cleanup pass; group absence does not prove zero leaked OS semaphore resources. No warning or failed check was erased or counted as quality acceptance.

This is process-cold startup/first-use evidence, not p95, disk-cold performance, acoustic onset, actual device underruns, matched listening, instruction adherence or Fast acceptance. A-001/A-006/A-007 stay open; Quality default/Fast disabled and D-012 authority unchanged. No browser/Safari/CUA, microphone, playback, trust changes, downloads, publication or unrelated writes. The remaining release decision requires user listening/device evidence via the existing page, not another fixed-recognizer optimization.
