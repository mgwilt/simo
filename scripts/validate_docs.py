from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import tiktoken
import yaml


RESERVED_FILENAMES = {"index.md", "log.md"}
OKF_STATUSES = {"draft", "stable", "deprecated"}
SIMO_AUTHORITIES = {
    "product",
    "architecture",
    "interface",
    "governance",
    "operations",
    "coordination",
    "evidence",
    "reference",
    "proposal",
}
WORK_STATES = {"proposed", "ready", "active", "review", "done", "blocked", "cancelled"}
WORK_ID_RE = re.compile(r"^W-\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*$")
ACTOR_RE = re.compile(r"^(?:human:[^\s:]+|process:[^\s:]+|[^\s/]+/[^\s/]+)$")
DATE_HEADING_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
FOOTNOTE_USE_RE = re.compile(r"\[\^([^\]]+)\](?!:)")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
DEFAULT_TOKEN_WARNING = 4_000
SEVERE_TOKEN_WARNING = 8_000
PLAN_TOKEN_TARGET = 2_000


@dataclass(frozen=True)
class Diagnostic:
    path: str
    code: str
    severity: str
    message: str


@dataclass
class ParsedMarkdown:
    path: Path
    relative: str
    metadata: dict[str, Any] | None
    body: str
    raw: str


@dataclass
class ValidationReport:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    concept_count: int = 0
    token_counts: dict[str, int] = field(default_factory=dict)

    def add(self, path: str, code: str, severity: str, message: str) -> None:
        self.diagnostics.append(Diagnostic(path, code, severity, message))

    @property
    def errors(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "warning"]


def parse_markdown(path: Path, bundle_root: Path) -> ParsedMarkdown:
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)
    metadata: dict[str, Any] | None = None
    body = raw
    if match:
        loaded = yaml.safe_load(match.group(1))
        if loaded is not None and not isinstance(loaded, dict):
            raise ValueError("frontmatter must be a YAML mapping")
        metadata = loaded or {}
        body = raw[match.end() :]
    return ParsedMarkdown(path, path.relative_to(bundle_root).as_posix(), metadata, body, raw)


def _valid_actor(value: Any) -> bool:
    return isinstance(value, str) and bool(ACTOR_RE.fullmatch(value))


def _valid_datetime(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_actor_event(
    report: ValidationReport, relative: str, code: str, name: str, value: Any
) -> None:
    if not isinstance(value, dict):
        report.add(relative, code, "error", f"{name} must be a mapping")
        return
    if not _valid_actor(value.get("by")):
        report.add(relative, code, "error", f"{name}.by must use the OKF actor convention")
    if not _valid_datetime(value.get("at")):
        report.add(relative, code, "error", f"{name}.at must be an ISO 8601 datetime")


def _validate_reserved(report: ValidationReport, parsed: ParsedMarkdown, bundle_root: Path) -> None:
    if parsed.path.name == "index.md":
        if parsed.path == bundle_root / "index.md":
            if parsed.metadata != {"okf_version": "0.2"}:
                report.add(
                    parsed.relative,
                    "OKF001",
                    "error",
                    'root index frontmatter must contain only okf_version: "0.2"',
                )
        elif parsed.metadata is not None:
            report.add(parsed.relative, "OKF002", "error", "subdirectory index.md has frontmatter")
        return

    if parsed.metadata is not None:
        report.add(parsed.relative, "OKF003", "error", "log.md has frontmatter")
    headings = DATE_HEADING_RE.findall(parsed.body)
    parsed_dates: list[date] = []
    for heading in headings:
        try:
            parsed_dates.append(date.fromisoformat(heading))
        except ValueError:
            report.add(parsed.relative, "OKF004", "error", f"invalid log date {heading}")
    if parsed_dates != sorted(parsed_dates, reverse=True):
        report.add(parsed.relative, "OKF005", "error", "log dates are not newest first")


def _validate_profile(report: ValidationReport, parsed: ParsedMarkdown) -> None:
    metadata = parsed.metadata or {}
    if not isinstance(metadata.get("type"), str) or not metadata["type"].strip():
        report.add(parsed.relative, "OKF006", "error", "concept requires a non-empty type")
        return

    report.concept_count += 1
    for key in ("title", "description"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            report.add(parsed.relative, "SIMO001", "error", f"concept requires non-empty {key}")
    description = metadata.get("description")
    if isinstance(description, str) and "\n" in description:
        report.add(parsed.relative, "SIMO002", "error", "description must be one line")
    tags = metadata.get("tags")
    if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not tag for tag in tags):
        report.add(parsed.relative, "SIMO003", "error", "tags must be a non-empty string list")
    if metadata.get("status") not in OKF_STATUSES:
        report.add(parsed.relative, "SIMO004", "error", "status must be draft, stable, or deprecated")

    generated = metadata.get("generated")
    _validate_actor_event(report, parsed.relative, "SIMO005", "generated", generated)
    verified = metadata.get("verified")
    if verified is not None:
        events = verified if isinstance(verified, list) else [verified]
        if not events:
            report.add(parsed.relative, "SIMO006", "error", "verified must not be an empty list")
        for event in events:
            _validate_actor_event(report, parsed.relative, "SIMO006", "verified", event)

    stale_after = metadata.get("stale_after")
    if stale_after is not None:
        try:
            stale_date = stale_after if isinstance(stale_after, date) else date.fromisoformat(str(stale_after))
        except ValueError:
            report.add(parsed.relative, "SIMO007", "error", "stale_after must be YYYY-MM-DD")
        else:
            if date.today() >= stale_date:
                report.add(parsed.relative, "SIMO008", "warning", f"concept is stale as of {stale_date}")

    simo = metadata.get("simo")
    if not isinstance(simo, dict):
        report.add(parsed.relative, "SIMO009", "error", "concept requires a simo mapping")
        return
    if simo.get("profile_version") != 1:
        report.add(parsed.relative, "SIMO010", "error", "simo.profile_version must be 1")
    stable_id = simo.get("stable_id")
    if not isinstance(stable_id, str) or not stable_id.strip():
        report.add(parsed.relative, "SIMO011", "error", "simo.stable_id is required")
    if simo.get("authority") not in SIMO_AUTHORITIES:
        report.add(parsed.relative, "SIMO012", "error", "simo.authority is invalid")
    repository_paths = simo.get("repository_paths")
    if not isinstance(repository_paths, list) or not repository_paths or any(
        not isinstance(item, str) or not item for item in repository_paths
    ):
        report.add(parsed.relative, "SIMO013", "error", "simo.repository_paths must be non-empty")
    owner = simo.get("owner")
    if owner != "unassigned" and not _valid_actor(owner):
        report.add(parsed.relative, "SIMO014", "error", "simo.owner must be unassigned or an OKF actor")

    sources = metadata.get("sources", [])
    if not isinstance(sources, list):
        report.add(parsed.relative, "SIMO015", "error", "sources must be a list")
        sources = []
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("resource"), str) or not source["resource"]:
            report.add(parsed.relative, "OKF007", "error", "every source requires resource")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            report.add(parsed.relative, "SIMO016", "error", "Simo sources require a stable id")
        elif source_id in source_ids:
            report.add(parsed.relative, "SIMO017", "error", f"duplicate source id {source_id}")
        else:
            source_ids.add(source_id)

    used = set(FOOTNOTE_USE_RE.findall(parsed.body))
    defined = set(FOOTNOTE_DEF_RE.findall(parsed.body))
    for source_id in sorted(used | defined):
        if source_id not in source_ids:
            report.add(parsed.relative, "SIMO018", "error", f"footnote {source_id} has no source entry")
    for source_id in sorted(source_ids):
        if source_id not in used or source_id not in defined:
            report.add(parsed.relative, "SIMO019", "error", f"source {source_id} lacks a used and defined claim footnote")

    work = simo.get("work")
    if metadata.get("type") == "Work Plan":
        if not isinstance(work, dict):
            report.add(parsed.relative, "WORK001", "error", "Work Plan requires simo.work")
        else:
            parts = Path(parsed.relative).parts
            expected_id = parts[1] if len(parts) == 3 and parts[0] == "work" and parts[2] == "plan.md" else None
            work_id = work.get("id")
            if expected_id is None or not WORK_ID_RE.fullmatch(str(work_id)) or work_id != expected_id:
                report.add(
                    parsed.relative,
                    "WORK007",
                    "error",
                    "Work Plan must be work/<work-id>/plan.md with matching W-YYYYMMDD-slug id",
                )
            if simo.get("stable_id") != work_id:
                report.add(parsed.relative, "WORK008", "error", "Work Plan stable_id must equal simo.work.id")
            if work.get("state") not in WORK_STATES:
                report.add(parsed.relative, "WORK002", "error", "invalid simo.work.state")
            if work.get("mode") not in {"read_only", "mutation"}:
                report.add(parsed.relative, "WORK003", "error", "invalid simo.work.mode")
            if not isinstance(work.get("next_action"), str) or not work["next_action"].strip():
                report.add(parsed.relative, "WORK004", "error", "Work Plan requires next_action")
            if work.get("mode") == "read_only" and work.get("write_paths"):
                report.add(parsed.relative, "WORK005", "error", "read_only work cannot declare write_paths")
            accountable = work.get("accountable")
            if accountable != "unassigned" and not _valid_actor(accountable):
                report.add(parsed.relative, "WORK009", "error", "work accountable must be unassigned or an OKF actor")
            for key in ("created_at", "updated_at"):
                if not _valid_datetime(work.get(key)):
                    report.add(parsed.relative, "WORK010", "error", f"work {key} must be an ISO 8601 datetime")
            if work.get("state") == "blocked" and not isinstance(work.get("blocker"), dict):
                report.add(parsed.relative, "WORK011", "error", "blocked work requires blocker details")
            if work.get("state") in {"done", "cancelled"} and metadata.get("status") != "stable":
                report.add(parsed.relative, "WORK012", "error", "terminal Work Plans require status stable")


def _resolve_link(bundle_root: Path, source: Path, target: str) -> Path | None:
    parsed = urlparse(target)
    if parsed.scheme or target.startswith("#"):
        return None
    clean = parsed.path
    if not clean:
        return None
    resolved = bundle_root / clean.lstrip("/") if clean.startswith("/") else source.parent / clean
    resolved = resolved.resolve()
    if resolved.is_dir():
        resolved /= "index.md"
    return resolved


def _validate_links(report: ValidationReport, parsed: ParsedMarkdown, bundle_root: Path) -> set[Path]:
    resolved_links: set[Path] = set()
    for target in LINK_RE.findall(parsed.body):
        resolved = _resolve_link(bundle_root, parsed.path, target)
        if resolved is None:
            continue
        resolved_links.add(resolved)
        if not resolved.exists():
            report.add(parsed.relative, "SIMO020", "error", f"broken internal link {target}")
    return resolved_links


def _validate_index_coverage(
    report: ValidationReport, bundle_root: Path, parsed_by_path: dict[Path, ParsedMarkdown]
) -> None:
    for directory in sorted({path.parent for path in parsed_by_path}):
        index_path = directory / "index.md"
        relevant_files = [
            path for path in parsed_by_path if path.parent == directory and path.name not in RESERVED_FILENAMES
        ]
        child_indexes = [
            path
            for path in parsed_by_path
            if path.name == "index.md" and path.parent.parent == directory and path.parent != directory
        ]
        if not relevant_files and not child_indexes:
            continue
        if index_path not in parsed_by_path:
            relative = directory.relative_to(bundle_root).as_posix() or "."
            report.add(relative, "SIMO021", "error", "directory with knowledge children requires index.md")
            continue
        links = _validate_links(report, parsed_by_path[index_path], bundle_root)
        for child in relevant_files + child_indexes:
            if child.resolve() not in links:
                report.add(
                    index_path.relative_to(bundle_root).as_posix(),
                    "SIMO022",
                    "error",
                    f"index does not list direct child {child.relative_to(directory).as_posix()}",
                )


def _paths_overlap(left: str, right: str) -> bool:
    left_path = Path(left)
    right_path = Path(right)
    return left_path == right_path or left_path in right_path.parents or right_path in left_path.parents


def _validate_active_work_overlap(report: ValidationReport, concepts: list[ParsedMarkdown]) -> None:
    active: list[tuple[str, list[str], str]] = []
    for concept in concepts:
        metadata = concept.metadata or {}
        if metadata.get("type") != "Work Plan":
            continue
        work = metadata.get("simo", {}).get("work", {})
        if work.get("state") == "active" and work.get("mode") == "mutation":
            active.append((str(work.get("id", concept.relative)), work.get("write_paths", []), concept.relative))
    for index, (left_id, left_paths, left_ref) in enumerate(active):
        for right_id, right_paths, _ in active[index + 1 :]:
            for left_path in left_paths:
                for right_path in right_paths:
                    if _paths_overlap(left_path, right_path):
                        report.add(
                            left_ref,
                            "WORK006",
                            "error",
                            f"active mutation plans {left_id} and {right_id} overlap at {left_path} / {right_path}",
                        )


def _validate_work_bundles(
    report: ValidationReport, bundle_root: Path, concepts: list[ParsedMarkdown]
) -> None:
    required = {
        "index.md",
        "plan.md",
        "scope.md",
        "acceptance.md",
        "execution.md",
        "checkpoint.md",
        "decisions.md",
        "verification.md",
        "closure.md",
        "evidence/index.md",
    }
    for concept in concepts:
        if (concept.metadata or {}).get("type") != "Work Plan":
            continue
        work_dir = concept.path.parent
        for relative in sorted(required):
            if not (work_dir / relative).is_file():
                report.add(
                    concept.relative,
                    "WORK013",
                    "error",
                    f"Work Plan bundle is missing {relative}",
                )


def validate_bundle(repository_root: Path, bundle_root: Path | None = None) -> ValidationReport:
    repository_root = repository_root.resolve()
    bundle_root = (bundle_root or repository_root / "docs").resolve()
    report = ValidationReport()
    if not bundle_root.is_dir():
        report.add("docs", "OKF000", "error", "bundle root does not exist")
        return report

    encoding = tiktoken.get_encoding("o200k_base")
    parsed_by_path: dict[Path, ParsedMarkdown] = {}
    concepts: list[ParsedMarkdown] = []
    stable_ids: dict[str, str] = {}

    for path in sorted(bundle_root.rglob("*.md")):
        try:
            parsed = parse_markdown(path, bundle_root)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
            report.add(path.relative_to(bundle_root).as_posix(), "OKF008", "error", str(error))
            continue
        parsed_by_path[path.resolve()] = parsed
        token_count = len(encoding.encode(parsed.raw))
        report.token_counts[parsed.relative] = token_count
        if token_count >= SEVERE_TOKEN_WARNING:
            report.add(parsed.relative, "CTX002", "warning", f"{token_count} tokens; semantic split strongly recommended")
        elif token_count >= DEFAULT_TOKEN_WARNING:
            report.add(parsed.relative, "CTX001", "warning", f"{token_count} tokens; review for semantic splitting")
        if parsed.relative.endswith("/plan.md") and token_count > PLAN_TOKEN_TARGET:
            report.add(parsed.relative, "CTX003", "warning", f"Work Plan entrypoint is {token_count} tokens; target is {PLAN_TOKEN_TARGET}")

        if path.name in RESERVED_FILENAMES:
            _validate_reserved(report, parsed, bundle_root)
        else:
            if parsed.metadata is None:
                report.add(parsed.relative, "OKF009", "error", "concept is missing frontmatter")
                continue
            _validate_profile(report, parsed)
            concepts.append(parsed)
            stable_id = (parsed.metadata.get("simo") or {}).get("stable_id")
            if isinstance(stable_id, str):
                if stable_id in stable_ids:
                    report.add(parsed.relative, "SIMO023", "error", f"duplicate stable ID {stable_id} also used by {stable_ids[stable_id]}")
                else:
                    stable_ids[stable_id] = parsed.relative

        _validate_links(report, parsed, bundle_root)

    _validate_index_coverage(report, bundle_root, parsed_by_path)
    _validate_active_work_overlap(report, concepts)
    _validate_work_bundles(report, bundle_root, concepts)
    return report


def _print_report(report: ValidationReport) -> None:
    for diagnostic in sorted(report.diagnostics, key=lambda item: (item.path, item.severity, item.code)):
        print(f"{diagnostic.severity.upper()} {diagnostic.code} {diagnostic.path}: {diagnostic.message}")
    print(
        f"docs: {report.concept_count} concept(s), "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Simo OKF bundle and producer profile.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-root", type=Path)
    args = parser.parse_args(argv)
    report = validate_bundle(args.repository_root, args.bundle_root)
    _print_report(report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
