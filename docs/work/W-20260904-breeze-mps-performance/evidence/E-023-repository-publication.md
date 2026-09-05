---
type: Evidence Record
title: Breeze fork and Simo publication checkpoint
description: Records verified gates and ordered publication of the owned MLX fork and matching Simo integration.
tags: [evidence, git, publication, breeze, mlx]
status: draft
generated: { by: process:simo-performance-integration, at: 2026-09-05T18:43:10Z }
simo:
  profile_version: 1
  stable_id: W-20260904-breeze-mps-performance-E-023
  authority: evidence
  repository_paths: [vendor/breeze-tts, services/breeze, python/simo, web, tests, scripts, docs, README.md]
  owner: process:simo-performance-integration
  work: { parent_id: W-20260904-breeze-mps-performance }
---
# E-023: Repository publication checkpoint

Source: Simo base `2ffe040c322139174ffd8269625c8a34dcd66ccd` plus the preserved scoped working tree; owned fork started at local `a294fe402eda72b7330dd30fd977c829e72137db` with remote `origin/simo-apple-silicon` at `a38d7d1`. The user explicitly authorized commit and push of Simo and `mgwilt/breeze-tts-mps` on2026-09-05. Publication order was fork, remote verification, parent gitlink, parent commit and remote verification. Unrelated untracked `:memory:.ses` was excluded.

Fork result: commit `05129be2aea0d26680e9f77e1e80ead11f322296` (`feat: add MLX inference runtime`) adds the experimental MLX backbone/depth/speech runtime, probes, API integration and tests on top of earlier unpublished `9ab3fb9`/`a294fe4`. Commit `78a79bbe7996f88766ee1885140909ca696c7055` (`docs: document Apple Silicon MLX runtime`) replaces the stale full-utterance MPS description with the shipped runtime split, measured status, commands, limitations, attribution and licensing boundary. Ordered pushes published `a38d7d1..05129be` and then `05129be..78a79bb`; final `git ls-remote origin refs/heads/simo-apple-silicon` returned `78a79bbe7996f88766ee1885140909ca696c7055`. The first restricted test run passed136 and failed64 solely because Metal was unavailable; the identical host-access run passed200, and a post-format rerun passed200. Changed files pass Python compilation, Ruff formatting and bounded fatal/undefined-name checks; fork diff check passes. Broad Simo Ruff policy is not the fork's configured gate and reports existing upstream annotation/private-member/test-assert conventions.

Parent prepublication result:201 Python tests,61 Node tests, TypeScript check, normal and isolated preview builds, parent Ruff/format/ty/BasedPyright, documentation validation (160 concepts, zero errors, four advisory categories), five knowledge regressions and diff checks pass. The first parent suite found one stale test expectation after the default token budget changed64→512; correcting that fixture produced the clean201-test result. Generated evidence/audio under ignored `.artifacts` was not staged. The existing Fast/model services are runtime state, not Git publication proof.

Parent commit and remote SHA are appended in the follow-up publication metadata commit because a commit cannot contain its own hash. This evidence proves ordered, reachable source publication and the listed repository checks. It does not prove the Fast release targets, physical audio, stable cross-turn speaker identity, listener acceptance, or correction of the known End conversation whole-server shutdown behavior.
