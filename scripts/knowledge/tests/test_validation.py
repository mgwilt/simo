from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_docs import validate_bundle


VALID_CONCEPT = """---
type: Architecture Concept
title: Test concept
description: A valid test concept.
tags: [test]
status: draft
generated: { by: process:test, at: 2026-08-02T00:00:00Z }
simo:
  profile_version: 1
  stable_id: DOC-0001
  authority: proposal
  repository_paths: [src]
  owner: unassigned
---
# Test concept
"""


class ValidationTests(unittest.TestCase):
    def make_bundle(
        self, concept: str = VALID_CONCEPT
    ) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        repository = Path(temporary.name)
        docs = repository / "docs"
        docs.mkdir()
        (docs / "index.md").write_text(
            '---\nokf_version: "0.2"\n---\n# Test knowledge\n\n- [Concept](concept.md) - A valid test concept.\n',
            encoding="utf-8",
        )
        (docs / "concept.md").write_text(concept, encoding="utf-8")
        return temporary, repository

    def test_valid_bundle_passes(self) -> None:
        temporary, repository = self.make_bundle()
        self.addCleanup(temporary.cleanup)
        report = validate_bundle(repository)
        self.assertEqual([], report.errors)
        self.assertEqual(1, report.concept_count)

    def test_missing_type_is_okf_error(self) -> None:
        concept = VALID_CONCEPT.replace("type: Architecture Concept\n", "")
        temporary, repository = self.make_bundle(concept)
        self.addCleanup(temporary.cleanup)
        report = validate_bundle(repository)
        self.assertIn("OKF006", {item.code for item in report.errors})

    def test_unmatched_source_is_profile_error(self) -> None:
        concept = VALID_CONCEPT.replace(
            "simo:\n",
            "sources:\n  - id: upstream\n    resource: https://example.com/source\n    title: Source\nsimo:\n",
        )
        temporary, repository = self.make_bundle(concept)
        self.addCleanup(temporary.cleanup)
        report = validate_bundle(repository)
        self.assertIn("SIMO019", {item.code for item in report.errors})

    def test_duplicate_stable_ids_fail(self) -> None:
        temporary, repository = self.make_bundle()
        self.addCleanup(temporary.cleanup)
        docs = repository / "docs"
        (docs / "other.md").write_text(
            VALID_CONCEPT.replace("Test concept", "Other concept"), encoding="utf-8"
        )
        (docs / "index.md").write_text(
            (docs / "index.md").read_text(encoding="utf-8")
            + "- [Other](other.md) - Another concept.\n",
            encoding="utf-8",
        )
        report = validate_bundle(repository)
        self.assertIn("SIMO023", {item.code for item in report.errors})

    def test_work_plan_requires_canonical_bundle_path(self) -> None:
        concept = VALID_CONCEPT.replace(
            "type: Architecture Concept", "type: Work Plan"
        ).replace(
            "  owner: unassigned\n",
            "  owner: process:test\n"
            "  work:\n"
            "    schema_version: 1\n"
            "    id: W-20260802-test\n"
            "    state: proposed\n"
            "    mode: read_only\n"
            "    priority: p1\n"
            "    accountable: process:test\n"
            "    created_at: 2026-08-02T00:00:00Z\n"
            "    updated_at: 2026-08-02T00:00:00Z\n"
            "    depends_on: []\n"
            "    knowledge_refs: []\n"
            "    write_paths: []\n"
            "    next_action: Define scope.\n"
            "    blocker: null\n",
        )
        temporary, repository = self.make_bundle(concept)
        self.addCleanup(temporary.cleanup)
        report = validate_bundle(repository)
        self.assertIn("WORK007", {item.code for item in report.errors})


if __name__ == "__main__":
    unittest.main()
