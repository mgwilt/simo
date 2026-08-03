from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simo.context import NativeContextEngine
from simo.knowledge import (
    KnowledgeValidationError,
    load_knowledge_bundle,
    refresh_knowledge_graph,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def concept(stable_id: str, title: str, body: str = "") -> str:
    return f"""---
type: Architecture Concept
title: {title}
description: A valid runtime projection fixture.
tags: [test, knowledge]
status: stable
generated: {{ by: process:test, at: 2026-08-03T00:00:00Z }}
verified: {{ by: process:test, at: 2026-08-03T00:00:00Z }}
stale_after: 2026-09-03
simo:
  profile_version: 1
  stable_id: {stable_id}
  authority: architecture
  repository_paths: [src]
  owner: unassigned
---
# {title}

{body}
"""


class KnowledgeProjectionTests(unittest.TestCase):
    def test_repository_bundle_loads_stable_ids_and_typed_references(self) -> None:
        bundle = load_knowledge_bundle(REPOSITORY)
        by_id = {item.okf_id: item for item in bundle.concepts}
        self.assertEqual(
            "DOC-0002",
            by_id["architecture/semantic-context-spine"].stable_id,
        )
        self.assertEqual(
            "docs/architecture/semantic-context-spine.md",
            by_id["architecture/semantic-context-spine"].source_path,
        )
        self.assertIn(
            (
                "governance/DOC-0001-documentation-and-work-management",
                "architecture/semantic-context-spine",
            ),
            {(link.source_okf_id, link.target_okf_id) for link in bundle.references},
        )

    def test_refresh_projects_and_removes_stale_runtime_entities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_bundle(root, include_second=True)
            with NativeContextEngine() as engine:
                first = refresh_knowledge_graph(engine, REPOSITORY, bundle_root=root)
                first_snapshot = engine.knowledge_snapshot()
                self.assertEqual(2, first.concepts)
                self.assertEqual(1, first.links)
                self.assertNotIn("entity_id", first_snapshot["concepts"][0])

                self._write_bundle(root, include_second=False)
                second = refresh_knowledge_graph(engine, REPOSITORY, bundle_root=root)
                second_snapshot = engine.knowledge_snapshot()

            self.assertEqual(2, second.revision)
            self.assertEqual(1, second.concepts)
            self.assertEqual(1, second.removed)
            self.assertEqual([], second_snapshot["links"])
            self.assertEqual(2, len(first_snapshot["concepts"]))

    def test_invalid_bundle_cannot_mutate_runtime_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_bundle(root, include_second=False)
            (root / "one.md").write_text("# missing frontmatter\n", encoding="utf-8")
            with NativeContextEngine() as engine:
                with self.assertRaises(KnowledgeValidationError):
                    refresh_knowledge_graph(engine, REPOSITORY, bundle_root=root)
                self.assertEqual(0, engine.knowledge_snapshot()["revision"])

    def _write_bundle(self, root: Path, *, include_second: bool) -> None:
        second_index = "- [Two](two.md) - A second concept.\n" if include_second else ""
        root.joinpath("index.md").write_text(
            '---\nokf_version: "0.2"\n---\n# Fixture\n\n'
            "- [One](one.md) - A first concept.\n" + second_index,
            encoding="utf-8",
        )
        root.joinpath("one.md").write_text(
            concept("TEST-ONE", "One", "[Two](two.md)" if include_second else ""),
            encoding="utf-8",
        )
        second = root / "two.md"
        if include_second:
            second.write_text(concept("TEST-TWO", "Two"), encoding="utf-8")
        elif second.exists():
            second.unlink()


if __name__ == "__main__":
    unittest.main()
