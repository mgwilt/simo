from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simo.config import RunMode, RuntimeConfig
from simo.conversation import PersistedConversationRuntime
from simo.persistence import ConversationEventType, SimoStore


class PersistedConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_twenty_turns_resume_with_ordered_speech_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data"
            store = SimoStore(root)
            alias = store.create_alias("Ada")
            config = RuntimeConfig.from_environment(mode=RunMode.HEADLESS)
            runtime = PersistedConversationRuntime(store, config)
            turns = [
                "My favorite door is blue." if index == 0 else f"Synthetic turn {index + 1}."
                for index in range(20)
            ]
            turns[15] = "Correction: my favorite door is now green."

            first = await runtime.run(alias.alias_id, turns)
            self.assertEqual(20, first.turns_written)
            self.assertEqual(40, len(first.transcript))
            self.assertEqual(40, first.world_revision)
            self.assertEqual("My favorite door is blue.", first.transcript[0].text)
            self.assertEqual(
                "Correction: my favorite door is now green.", first.transcript[30].text
            )

            reopened_store = SimoStore(root)
            resumed = await PersistedConversationRuntime(reopened_store, config).run(
                alias.alias_id,
                ["Continue after restart."],
                conversation_id=first.conversation_id,
                complete=True,
            )
            detail = reopened_store.get_conversation(first.conversation_id)

            self.assertEqual(42, len(resumed.transcript))
            self.assertEqual(42, resumed.world_revision)
            self.assertEqual("completed", detail.conversation.status)
            self.assertEqual(
                list(range(1, len(detail.events) + 1)), [e.sequence for e in detail.events]
            )
            self.assertEqual(
                21,
                sum(
                    event.event_type == ConversationEventType.USER_TRANSCRIPT_FINAL
                    for event in detail.events
                ),
            )
            self.assertEqual(
                21,
                sum(
                    event.event_type == ConversationEventType.ASSISTANT_GENERATED
                    for event in detail.events
                ),
            )
            self.assertEqual(
                21,
                sum(
                    event.event_type == ConversationEventType.ASSISTANT_TTS_SUBMITTED
                    for event in detail.events
                ),
            )
            self.assertEqual(
                21,
                sum(
                    event.event_type == ConversationEventType.ASSISTANT_SPOKEN
                    for event in detail.events
                ),
            )
            self.assertEqual(
                1,
                sum(
                    event.event_type == ConversationEventType.CONVERSATION_RESUMED
                    for event in detail.events
                ),
            )


if __name__ == "__main__":
    unittest.main()
