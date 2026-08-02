# Simo repository instructions

These instructions apply to all work in this repository.

## Start safely

- Inspect `git status` first. Preserve existing staged, unstaged, and untracked work; never reset, remove, overwrite, stage, or commit unrelated changes.
- Treat `vendor/` as pinned upstream source. Do not edit vendored dependencies unless the user explicitly requests an upstream patch or version change.
- Simo currently has no implemented first-party runtime. Mark architecture and Flecs entity/graph designs as proposed until code and proportional executable evidence exist.

## Knowledge

- `docs/` is the Simo OKF 0.2 bundle. Start at `docs/index.md` and retrieve only the narrowest relevant concepts.
- Use `$curate-simo-knowledge` whenever creating, changing, moving, splitting, auditing, deprecating, or promoting Markdown under `docs/`, or when changing its governing policies or validation.
- Upstream OKF requirements come from `vendor/knowledge-catalog/okf/SPEC.md`. Simo-specific metadata, IDs, authority, ownership, work lifecycle, and validation are the local producer profile; never describe them as upstream requirements.
- Durable product, architecture, interface, governance, and operational concepts are authority. Work Plans, task briefs, result packets, and evidence coordinate or support authority but never replace runtime/code truth.

## Work tracking and agents

- Use `$track-simo-work` for multi-file or multi-session implementation, architecture/public-interface changes, coordinated agents, independent verification, explicit tracking requests, or checkpoint recovery.
- Keep Work Plans progressive and bounded. Resume matching non-terminal work instead of creating parallel plans.
- Parallelize bounded read-only research when useful. Serialize repository mutations through one explicit integration owner and mutation lease; planned write paths do not grant authority.
- Use compact Task Briefs and Result Packets with artifact references. Keep raw logs and transcript history out of durable knowledge.

## Runtime authority and evidence

- Pipecat is the intended latency-sensitive media/frame plane; Flecs is the proposed live semantic state plane; OKF is durable reviewable knowledge. Do not treat documentation links as Flecs relations or documentation verification as runtime attestation.
- First-party source, configuration, schemas, tests, and observed execution become operational authority when implemented.
- Match claims to evidence. Documentation checks prove structure and provenance only; runtime, latency, replay, security, deployment, and user-visible behavior require their own evidence.
