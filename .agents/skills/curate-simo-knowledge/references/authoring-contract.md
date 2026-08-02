# Simo OKF authoring contract

This is the compact authoring contract for the proposed Simo profile. The vendored `vendor/knowledge-catalog/okf/SPEC.md` remains authoritative for upstream OKF 0.2.

## Bundle and identity

- The bundle root is `docs/`.
- `index.md` and `log.md` are reserved. All other Markdown files are concepts.
- The portable OKF concept ID is the bundle-relative path without `.md`.
- `simo.stable_id` is a Simo alias, not an OKF field. Use `DOC-NNNN` for general durable concepts and `ADR-NNNN` for durable decisions when an alias is warranted.
- A move changes the OKF concept ID. Keep a deprecated tombstone at the old path when inbound references or history matter.

## Concept frontmatter

```yaml
---
type: Architecture Concept
title: One human-readable title
description: One sentence suitable for an index preview.
tags: [architecture, realtime]
status: draft
generated: { by: <truthful-actor>, at: <ISO-8601-datetime> }
verified: { by: <truthful-verifier>, at: <ISO-8601-datetime> } # only after a real check
stale_after: <YYYY-MM-DD> # when facts can age
sources:
  - id: stable-source-id
    resource: <HTTPS-URL-or-path>
    title: Source title
simo:
  profile_version: 1
  stable_id: DOC-NNNN
  authority: proposal
  repository_paths: [<affected-path>]
  owner: unassigned
---
```

Require `title`, one-line `description`, non-empty `tags`, explicit `status`, truthful `generated`, and `simo.profile_version`, `stable_id`, `authority`, `repository_paths`, and `owner`. Allowed authority values are `product`, `architecture`, `interface`, `governance`, `operations`, `coordination`, `evidence`, `reference`, and `proposal`.

Use OKF actor forms: `<producer>/<version>`, `human:<id>`, or `process:<id>`. Keep OKF document `status` (`draft`, `stable`, `deprecated`) separate from Work Plan execution state.

## Claims and sources

Place a source-keyed footnote immediately after each material externally derived claim. Keep its label equal to a unique `sources[].id`. A bibliography entry without a claim join is insufficient.

Distinguish:

- `sources[].last_modified`: source change time;
- `generated.at`: concept content change time;
- `verified[].at`: actual confirmation time;
- `stale_after`: date the claim requires review.

Trust metadata is advisory. It is never authorization, a mutation lease, or runtime proof.

## Indexes and logs

- The root `docs/index.md` may contain only `okf_version: "0.2"` frontmatter.
- Subdirectory indexes have no frontmatter.
- Indexes list direct child concepts and child directories with one-line descriptions.
- `log.md` has no frontmatter and uses newest-first `YYYY-MM-DD` headings.
- Do not require an index to carry task state or detailed history.

## Runtime and graph documentation

For an implemented runtime concept, link to its first-party schema/source through `resource` or `sources`, name the owning module, and record lifecycle, serialization boundary, readers/writers, and evidence revision. Mark unimplemented entity/component/relation diagrams `proposed`. Never equate:

- an OKF concept ID with a Flecs entity ID;
- a Markdown link with a typed Flecs relationship;
- `verified` documentation with per-run attestation;
- a Work Plan checkbox with executable behavior.

## Validation checklist

Separate results into upstream conformance and Simo policy.

Upstream OKF:

- Parseable frontmatter and non-empty `type` on every non-reserved concept.
- Reserved index/log structure.
- Valid shapes for optional provenance, lifecycle, trust, actor, and Attested Computation fields when present.

Simo profile:

- Required metadata present and stable IDs unique.
- Source IDs/resources valid and every cited claim joined to its source.
- Internal links resolve and direct-parent indexes cover material children.
- Mutable claims have honest freshness; no fabricated human verification.
- Coordination or evidence documents do not overclaim canonical/runtime authority.
- Proposed runtime concepts remain labeled proposed.
- Token-heavy material is split semantically or carries a concrete reason to stay atomic.
