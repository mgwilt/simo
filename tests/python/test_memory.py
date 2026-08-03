from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from simo.memory import LearningStatus, SafeMemoryLearner
from simo.persistence import ConversationEventType, RecordNotFoundError, SimoStore


class PrivateMemoryTests(unittest.TestCase):
    def test_independent_store_writers_serialize_one_alias_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data"
            setup = SimoStore(root)
            alias = setup.create_alias("Ada")
            conversation = setup.create_conversation(alias.alias_id)
            conversation_id = conversation.conversation.conversation_id
            human = setup.add_participant(
                conversation_id,
                "human:local",
                kind="human",
                display_name="Local user",
            )
            events = tuple(
                setup.append_event(
                    conversation_id,
                    ConversationEventType.USER_TRANSCRIPT_FINAL,
                    participant_id=human.participant_id,
                    text=text,
                )
                for text in ("I like tea.", "I like coffee.")
            )

            def promote(index: int) -> LearningStatus:
                independent = SimoStore(root)
                return (
                    SafeMemoryLearner(independent)
                    .learn_event(
                        alias.alias_id,
                        human.participant_id,
                        events[index],
                    )
                    .status
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = tuple(executor.map(promote, range(2)))

            self.assertEqual((LearningStatus.PROMOTED, LearningStatus.PROMOTED), statuses)
            reopened = SimoStore(root)
            self.assertEqual(
                {"Likes tea.", "Likes coffee."},
                {claim.content for claim in reopened.list_memory_claims(alias.alias_id)},
            )
            relationships = root / "aliases" / alias.alias_id / "knowledge" / "relationships"
            markdown = "\n".join(
                path.read_text(encoding="utf-8") for path in relationships.rglob("*.md")
            )
            self.assertIn("Likes tea.", markdown)
            self.assertIn("Likes coffee.", markdown)

    def test_safe_learning_correction_isolation_restart_and_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data"
            store = SimoStore(root)
            ada = store.create_alias("Ada")
            mira = store.create_alias("Mira")
            conversation = store.create_conversation(ada.alias_id)
            conversation_id = conversation.conversation.conversation_id
            ada_participant = f"alias:{ada.alias_id}"
            mira_participant = f"alias:{mira.alias_id}"
            store.add_participant(
                conversation_id,
                mira_participant,
                kind="alias",
                alias_id=mira.alias_id,
                display_name="Mira",
                transport_participant_id="livekit-mira",
            )
            learner = SafeMemoryLearner(store)

            likes = store.append_event(
                conversation_id,
                ConversationEventType.USER_TRANSCRIPT_FINAL,
                participant_id=mira_participant,
                text="I like jazz.",
            )
            first = learner.learn_event(
                ada.alias_id,
                mira_participant,
                likes,
                subject_alias_id=mira.alias_id,
            )
            self.assertEqual(LearningStatus.PROMOTED, first.status)
            self.assertIsNotNone(first.claim_id)

            favorite = store.append_event(
                conversation_id,
                ConversationEventType.USER_TRANSCRIPT_FINAL,
                participant_id=ada_participant,
                text="My favorite color is blue.",
            )
            second = learner.learn_event(
                mira.alias_id,
                ada_participant,
                favorite,
                subject_alias_id=ada.alias_id,
            )
            self.assertEqual(LearningStatus.PROMOTED, second.status)
            self.assertEqual(
                ["Likes jazz."],
                [claim.content for claim in store.list_memory_claims(ada.alias_id)],
            )
            self.assertEqual(
                ["Favorite color is blue."],
                [claim.content for claim in store.list_memory_claims(mira.alias_id)],
            )

            correction = store.append_event(
                conversation_id,
                ConversationEventType.USER_TRANSCRIPT_FINAL,
                participant_id=mira_participant,
                text="I no longer like jazz.",
            )
            corrected = learner.learn_event(
                ada.alias_id,
                mira_participant,
                correction,
                subject_alias_id=mira.alias_id,
            )
            self.assertEqual(LearningStatus.PROMOTED, corrected.status)
            active = store.list_memory_claims(ada.alias_id, status="active")
            superseded = store.list_memory_claims(ada.alias_id, status="superseded")
            self.assertEqual(["No longer likes jazz."], [claim.content for claim in active])
            self.assertEqual(["Likes jazz."], [claim.content for claim in superseded])
            self.assertEqual(superseded[0].claim_id, active[0].supersedes_claim_id)
            self.assertEqual(superseded[0].claim_id, active[0].contradicts_claim_id)
            self.assertEqual(
                "livekit-mira",
                store.get_conversation(conversation_id).participants[1].transport_participant_id,
            )

            prohibited_text = "My password is synthetic-secret-123."
            prohibited = store.append_event(
                conversation_id,
                ConversationEventType.USER_TRANSCRIPT_FINAL,
                participant_id=mira_participant,
                text=prohibited_text,
            )
            rejected = learner.learn_event(
                ada.alias_id,
                mira_participant,
                prohibited,
                subject_alias_id=mira.alias_id,
            )
            self.assertEqual(LearningStatus.REJECTED, rejected.status)
            relationships = root / "aliases" / ada.alias_id / "knowledge" / "relationships"
            retained_markdown = "\n".join(
                path.read_text(encoding="utf-8") for path in relationships.rglob("*.md")
            )
            self.assertNotIn("synthetic-secret-123", retained_markdown)
            self.assertEqual(1, store.get_alias(ada.alias_id).active_persona_version)
            self.assertEqual(1, store.get_alias(ada.alias_id).active_runtime_profile_version)

            reopened = SimoStore(root)
            self.assertEqual(
                ["No longer likes jazz."],
                [
                    claim.content
                    for claim in reopened.list_memory_claims(ada.alias_id, status="active")
                ],
            )
            active_path = root / "aliases" / ada.alias_id / active[0].materialized_path
            self.assertTrue(active_path.is_file())
            self.assertIn(conversation_id, active_path.read_text(encoding="utf-8"))

            reopened.delete_conversation(conversation_id)
            self.assertEqual((), reopened.list_memory_claims(ada.alias_id))
            self.assertEqual((), reopened.list_memory_claims(mira.alias_id))
            remaining_markdown = "\n".join(
                path.read_text(encoding="utf-8") for path in relationships.rglob("*.md")
            )
            self.assertNotIn("jazz", remaining_markdown)

    def test_operator_correction_forgetting_and_alias_export_are_portable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = SimoStore(root / "source")
            alias = source.create_alias("Ada")
            conversation = source.create_conversation(alias.alias_id)
            conversation_id = conversation.conversation.conversation_id
            human = source.add_participant(
                conversation_id,
                "human:local",
                kind="human",
                display_name="Local user",
            )
            event = source.append_event(
                conversation_id,
                ConversationEventType.USER_TRANSCRIPT_FINAL,
                participant_id=human.participant_id,
                text="My goal is build a conversational lab.",
            )
            decision = SafeMemoryLearner(source).learn_event(
                alias.alias_id,
                human.participant_id,
                event,
            )
            self.assertIsNotNone(decision.claim_id)
            original = source.get_memory_claim(decision.claim_id or "")
            corrected = source.correct_memory_claim(
                original.claim_id,
                "Goal: build a reproducible conversational lab.",
            )
            self.assertEqual(original.claim_id, corrected.supersedes_claim_id)

            export_path = source.export_alias(alias.alias_id, root / "ada.simo-alias")
            imported_store = SimoStore(root / "imported")
            imported_store.import_alias(export_path)
            imported_active = imported_store.list_memory_claims(alias.alias_id, status="active")
            self.assertEqual([corrected.content], [claim.content for claim in imported_active])
            self.assertIsNone(imported_active[0].source_conversation_id)
            self.assertEqual(conversation_id, imported_active[0].provenance["conversation_id"])

            forgotten = imported_store.forget_memory_claim(imported_active[0].claim_id)
            self.assertEqual(corrected.content, forgotten.content)
            with self.assertRaises(RecordNotFoundError):
                imported_store.get_memory_claim(forgotten.claim_id)
            materialized = (
                root / "imported" / "aliases" / alias.alias_id / forgotten.materialized_path
            )
            self.assertFalse(materialized.exists())


if __name__ == "__main__":
    unittest.main()
