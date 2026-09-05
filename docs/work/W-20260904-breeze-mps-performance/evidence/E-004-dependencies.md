---
type: Evidence Record
title: Native quantization and dependency compatibility
description: Native quantization and dependency compatibility with bounded evidence and explicit release limits.
tags: [work, breeze, performance, mps]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-04T23:50:49Z }
sources:
  - id: qwen-dependencies
    resource: https://github.com/QwenLM/Qwen3-TTS/blob/main/pyproject.toml
    title: Qwen TTS dependency contract
  - id: native-mps
    resource: https://github.com/pytorch/pytorch/blob/v2.9.1/aten/src/ATen/native/mps/operations/Quantized.mm
    title: Pinned native MPS quantization implementation
  - id: metal-quantization
    resource: https://huggingface.co/docs/transformers/quantization/metal
    title: Transformers Metal quantization documentation
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-004
  authority: evidence
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# Native quantization and dependency compatibility

Claim: the existing lock supports testable native MPS quantization without a Transformers migration.

Method: `PYTHONPATH=vendor/breeze-tts services/breeze/.venv/bin/python -m breeze_infer.probe_quantization --model-path .models/Breeze-TTS-2 --repeats 3`. Artifact: .artifacts/breeze-performance/native-quant-matrix.json. All32 actual-weight/bit-width/dtype cases passed the declared kernel-reference tolerances, including sliced inputs, leading dimensions, row isolation, zeros and duplicate rows. Eight representative projection/MLP weights cover backbone/depth; each record identifies tensor digest, source/method digest and settings.

Native ops are pinned by the unchanged torch2.9.1 artifact in services/breeze/uv.lock. Int8 is per-channel; int4 uses64-value groups.[^native-mps] Eligible layer nn.Linear modules alone are replaced in memory; embeddings, normalization, custom/output heads and codec are excluded. Startup reports exact selected modules, packed bytes and model-parameter coverage. Original checkpoint files remain unchanged. Packed weights are rebuilt on startup, not silently saved over originals.

Paired alternating100-call blocks distinguish amortized throughput from synchronized single-call latency. Gains are shape-dependent: some MLP projections improve, small projections are mixed, and depth down-projection/prefill can regress. Successful kernels did not translate to the fast utterance gate; see [screening](E-002-screening.md).

Compatibility review: qwen-tts0.1.1 pins Transformers4.57.3.[^qwen-dependencies] The examined5.16.1 generation interfaces remove/change helpers used by Breeze (_get_initial_cache_position, _prepare_generation_config and positional prepare_inputs). Current Metal kernel packaging additionally changes torch/huggingface-hub compatibility.[^metal-quantization] No dependency override or newer version was accepted. Primary evidence also includes installed locked metadata/source and the dependency review packet.

Proves: actual host kernel execution, documented candidate coverage and a justified retained lock. Does not prove: quantized perceptual acceptance, end-to-end speedup, v5 compatibility, other torch versions or CUDA. Verifier: root matrix run plus read-only dependency review; freshness2026-09-04.

[^qwen-dependencies]: Official Qwen package dependency declaration and installed qwen-tts0.1.1 metadata, inspected by the dependency reviewer on2026-09-04.
[^native-mps]: PyTorch v2.9.1 native source, with test_mps.py and common_quantization.py reference formulas, inspected before actual-shape probes.
[^metal-quantization]: Official Metal documentation and candidate package/build metadata inspected by the dependency reviewer; not evidence of Breeze or codec compatibility.
