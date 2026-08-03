"""Validated OKF 0.2 projection into Simo's private Flecs knowledge graph."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import urlparse

import yaml

from simo.context import KnowledgeConcept, KnowledgeRefreshStats, NativeContextEngine

RESERVED_FILENAMES = {"index.md", "log.md"}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")


class KnowledgeValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True, order=True)
class KnowledgeReference:
    source_okf_id: str
    target_okf_id: str


@dataclass(frozen=True, slots=True)
class KnowledgeBundle:
    concepts: tuple[KnowledgeConcept, ...]
    references: tuple[KnowledgeReference, ...]


def load_knowledge_bundle(
    repository: Path,
    *,
    bundle_root: Path | None = None,
) -> KnowledgeBundle:
    """Validate the repository profile, then parse projection-safe values."""

    repository = repository.resolve()
    root = (bundle_root or repository / "docs").resolve()
    _validate_repository_bundle(repository, root)
    concepts: list[KnowledgeConcept] = []
    paths_by_okf_id: dict[str, Path] = {}
    raw_by_okf_id: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        if path.name in RESERVED_FILENAMES:
            continue
        raw = path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(raw)
        if match is None:
            raise KnowledgeValidationError(f"missing frontmatter after validation: {path}")
        metadata = yaml.safe_load(match.group(1))
        if not isinstance(metadata, dict):
            raise KnowledgeValidationError(f"invalid frontmatter after validation: {path}")
        relative = path.relative_to(root)
        okf_id = relative.with_suffix("").as_posix()
        simo = metadata["simo"]
        verified = metadata.get("verified")
        if isinstance(verified, list):
            verified = verified[-1] if verified else None
        verified_at = verified.get("at") if isinstance(verified, dict) else ""
        concept = KnowledgeConcept(
            okf_id=okf_id,
            stable_id=str(simo["stable_id"]),
            type=str(metadata["type"]),
            title=str(metadata["title"]),
            status=str(metadata["status"]),
            authority=str(simo["authority"]),
            source_path=(Path("docs") / relative).as_posix(),
            verified_at=_scalar_text(verified_at),
            stale_after=_scalar_text(metadata.get("stale_after", "")),
            content_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )
        concepts.append(concept)
        paths_by_okf_id[okf_id] = path.resolve()
        raw_by_okf_id[okf_id] = raw

    okf_id_by_path = {path: okf_id for okf_id, path in paths_by_okf_id.items()}
    references: set[KnowledgeReference] = set()
    for source_okf_id, raw in raw_by_okf_id.items():
        source = paths_by_okf_id[source_okf_id]
        for target in LINK_RE.findall(raw):
            resolved = _resolve_internal_link(root, source, target)
            target_okf_id = okf_id_by_path.get(resolved) if resolved else None
            if target_okf_id is not None and target_okf_id != source_okf_id:
                references.add(KnowledgeReference(source_okf_id, target_okf_id))
    return KnowledgeBundle(tuple(concepts), tuple(sorted(references)))


def refresh_knowledge_graph(
    engine: NativeContextEngine,
    repository: Path,
    *,
    bundle_root: Path | None = None,
) -> KnowledgeRefreshStats:
    """Replace the runtime projection only after complete bundle validation."""

    bundle = load_knowledge_bundle(repository, bundle_root=bundle_root)
    engine.begin_knowledge_refresh()
    for concept in bundle.concepts:
        engine.upsert_knowledge_concept(concept)
    for reference in bundle.references:
        engine.add_knowledge_reference(
            reference.source_okf_id,
            reference.target_okf_id,
        )
    return engine.commit_knowledge_refresh()


def _validate_repository_bundle(repository: Path, bundle_root: Path) -> None:
    validator_path = repository / "scripts/validate_docs.py"
    if not validator_path.is_file():
        raise KnowledgeValidationError(f"Simo validator not found: {validator_path}")
    module_name = "_simo_runtime_validate_docs"
    spec = importlib.util.spec_from_file_location(module_name, validator_path)
    if spec is None or spec.loader is None:
        raise KnowledgeValidationError(f"could not load Simo validator: {validator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        report = _run_validator(module, repository, bundle_root)
    finally:
        sys.modules.pop(module_name, None)
    errors = getattr(report, "errors", [])
    if errors:
        detail = "; ".join(f"{item.code} {item.path}: {item.message}" for item in errors[:10])
        raise KnowledgeValidationError(f"knowledge bundle validation failed: {detail}")


def _run_validator(module: ModuleType, repository: Path, bundle_root: Path) -> object:
    validator = getattr(module, "validate_bundle", None)
    if validator is None:
        raise KnowledgeValidationError("Simo validator has no validate_bundle function")
    return validator(repository, bundle_root)


def _resolve_internal_link(root: Path, source: Path, target: str) -> Path | None:
    parsed = urlparse(target)
    if parsed.scheme or target.startswith("#") or not parsed.path:
        return None
    resolved = (
        root / parsed.path.lstrip("/")
        if parsed.path.startswith("/")
        else source.parent / parsed.path
    ).resolve()
    if resolved.is_dir():
        resolved /= "index.md"
    return resolved


def _scalar_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value is not None else ""
