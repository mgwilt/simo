---
name: curate-simo-knowledge
description: Maintain Simo's repository-native OKF 0.2 bundle, including creating, revising, splitting, auditing, deprecating, or promoting concepts; preserving provenance, trust, freshness, indexes, and runtime-authority boundaries; and validating documentation changes. Use whenever work changes Markdown under docs/ or changes the policies and tooling that govern Simo knowledge.
---

# Curate Simo Knowledge

Treat `docs/` as a governed OKF bundle, not a general document folder.

## Establish context

1. Inspect `git status` and preserve unrelated staged, unstaged, and untracked work.
2. Start at `../../../docs/index.md`; follow only the narrowest relevant indexes and concepts.
3. Read `../../../docs/governance/DOC-0001-documentation-and-work-management.md` while it remains the governing draft.
4. Read `../../../vendor/knowledge-catalog/okf/SPEC.md` when conformance or optional-field semantics are material.
5. Use `$track-simo-work` for significant work. Work Plans coordinate change; normal concepts and ADRs remain durable authority.
6. Read [references/authoring-contract.md](references/authoring-contract.md) before creating, moving, deprecating, or promoting a concept.

## Curate the narrowest owner

- Update an existing authoritative concept instead of creating parallel truth.
- Keep concepts semantic and independently retrievable. Split large material at semantic boundaries behind shallow indexes; never build a flat chronological record.
- Preserve unknown frontmatter keys, stable IDs, source IDs, claim footnotes, internal links, and lifecycle history unless the task changes them explicitly.
- Update direct-parent indexes for material additions, moves, deprecations, or description changes. Use `log.md` only for major scope-level events; Git holds edit history.
- Deprecate with a replacement link instead of deleting knowledge that has inbound links or historical value.
- Keep coordination, evidence, and proposal documents from silently overriding product, architecture, interface, or runtime authority.

## Preserve provenance and truth boundaries

- Prefer pinned first-party repository evidence and primary external sources.
- Give every cited source a stable `sources[].id` and required `resource`; join material claims to matching Markdown footnotes.
- Record `generated` only for the current content's last meaningful change. Add `verified` only after a real source or resource check.
- Never use `human:` unless that person performed the action.
- Use an absolute `stale_after` for mutable external or current-state claims.
- State what evidence proves and does not prove. Documentation validation is not runtime, latency, deployment, or attestation proof.
- Describe Flecs entities, relationships, and graphs as `proposed` until first-party schemas/code and proportional runtime evidence exist. OKF links are documentation edges, not live Flecs state.

## Keep context bounded

- Keep indexes to direct children and one-line descriptions.
- Prefer the narrowest relevant concept and active Work Plan artifacts; load full bundles only when needed.
- Treat file-length measurements as restructuring signals, not OKF conformance failures.
- Store raw logs outside concepts and link to compact Evidence Records or immutable artifacts.

## Validate and hand off

Run:

```bash
UV_CACHE_DIR=/private/tmp/simo-uv-cache \
TIKTOKEN_CACHE_DIR=.cache/tiktoken \
uv run --frozen python scripts/validate_docs.py

UV_CACHE_DIR=/private/tmp/simo-uv-cache \
TIKTOKEN_CACHE_DIR=.cache/tiktoken \
uv run --frozen python -m unittest discover -s scripts/knowledge/tests -v
```

The validator reports upstream OKF errors separately from Simo-profile and context diagnostics. Token warnings identify restructuring opportunities and do not fail an otherwise conformant bundle. Also run `git diff --check` against changed files.

Report changed concept IDs and stable aliases, indexes updated, source-footnote joins, generation/verification state, stale or unverified knowledge, checks performed, and any runtime claims deliberately left unproven.
