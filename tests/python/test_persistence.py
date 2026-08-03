from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import cast

import yaml
from simo.persistence import (
    ALIAS_EXPORT_SCHEMA,
    RecordConflictError,
    RecordNotFoundError,
    SimoDataError,
    SimoStore,
    resolve_data_root,
)


class PersistenceTests(unittest.TestCase):
    def test_data_root_prefers_explicit_then_environment(self) -> None:
        explicit = Path("/tmp/simo-explicit")
        configured = Path("/tmp/simo-configured")

        self.assertEqual(explicit.resolve(), resolve_data_root(explicit, {}))
        self.assertEqual(
            configured.resolve(),
            resolve_data_root(environ={"SIMO_DATA_DIR": str(configured)}),
        )

    def test_alias_versions_write_manifest_and_portable_okf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SimoStore(Path(temporary) / "data")
            alias = store.create_alias(
                "Ada",
                persona_summary="An analytical conversationalist.",
                persona_instructions="Be precise and warm.",
            )

            manifest_path = store.aliases_root / alias.alias_id / "alias.yaml"
            manifest = cast(
                dict[str, object],
                cast(object, yaml.safe_load(manifest_path.read_text(encoding="utf-8"))),
            )
            self.assertEqual("simo.alias.v1", manifest["schema"])
            self.assertEqual(alias.alias_id, manifest["alias_id"])
            self.assertEqual(
                '---\nokf_version: "0.2"\n---',
                "\n".join(
                    (store.aliases_root / alias.alias_id / "knowledge" / "index.md")
                    .read_text(encoding="utf-8")
                    .splitlines()[:3]
                ),
            )

            persona = store.revise_persona(
                alias.alias_id,
                "A more playful analytical conversationalist.",
                "Use concise examples and gentle humor.",
            )
            profile = store.revise_runtime_profile(
                alias.alias_id,
                {"schema": "simo.runtime-profile.v1", "voice": "Serena"},
            )
            current = store.get_alias(alias.alias_id)

            self.assertEqual(2, persona.version)
            self.assertEqual(2, profile.version)
            self.assertEqual(2, current.active_persona_version)
            self.assertEqual(2, current.active_runtime_profile_version)
            self.assertEqual(
                [1, 2], [item.version for item in store.list_persona_versions(alias.alias_id)]
            )
            self.assertIn(
                "Version 2",
                (
                    store.aliases_root / alias.alias_id / "knowledge" / "personas" / "index.md"
                ).read_text(encoding="utf-8"),
            )

    def test_alias_export_import_is_lossless_and_fails_on_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_store = SimoStore(root / "source")
            alias = source_store.create_alias("Mira")
            source_store.revise_persona(alias.alias_id, "A patient listener.", "Ask one question.")
            export_path = source_store.export_alias(alias.alias_id, root / "mira.simo-alias")

            with zipfile.ZipFile(export_path) as archive:
                payload = cast(
                    dict[str, object],
                    cast(object, json.loads(archive.read("records.json"))),
                )
            self.assertEqual(ALIAS_EXPORT_SCHEMA, payload["schema"])

            target_store = SimoStore(root / "target")
            imported = target_store.import_alias(export_path)
            self.assertEqual(alias.alias_id, imported.alias_id)
            self.assertEqual(
                [item.as_dict() for item in source_store.list_persona_versions(alias.alias_id)],
                [item.as_dict() for item in target_store.list_persona_versions(alias.alias_id)],
            )
            self.assertEqual(
                (
                    source_store.aliases_root
                    / alias.alias_id
                    / "knowledge"
                    / "personas"
                    / "v0002.md"
                ).read_text(encoding="utf-8"),
                (
                    target_store.aliases_root
                    / alias.alias_id
                    / "knowledge"
                    / "personas"
                    / "v0002.md"
                ).read_text(encoding="utf-8"),
            )
            with self.assertRaises(RecordConflictError):
                target_store.import_alias(export_path)

    def test_conversation_index_and_delete_are_alias_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SimoStore(temporary)
            ada = store.create_alias("Ada")
            mira = store.create_alias("Mira")
            conversation = store.create_conversation(ada.alias_id, title="First meeting")
            store.create_conversation(mira.alias_id, title="Second meeting")

            selected = store.list_conversations(ada.alias_id)
            self.assertEqual(
                [conversation.conversation.conversation_id],
                [item.conversation_id for item in selected],
            )
            detail = store.get_conversation(conversation.conversation.conversation_id)
            self.assertEqual("First meeting", detail.conversation.title)
            self.assertEqual(ada.alias_id, detail.participants[0].alias_id)
            self.assertEqual((), detail.events)

            store.delete_conversation(conversation.conversation.conversation_id)
            with self.assertRaises(RecordNotFoundError):
                store.get_conversation(conversation.conversation.conversation_id)

    def test_import_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            malicious = root / "malicious.simo-alias"
            with zipfile.ZipFile(malicious, "w") as archive:
                archive.writestr("../outside", "unsafe")

            with self.assertRaises(SimoDataError):
                SimoStore(root / "data").import_alias(malicious)


if __name__ == "__main__":
    unittest.main()
