from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from livekit.agents import llm
from livekit.agents.voice.events import (
    ConversationItemAddedEvent,
    UserInputTranscribedEvent,
)
from simo.adapters.livekit import LiveKitSessionEventBridge
from simo.context import EnqueueResult
from simo.persistence import SimoStore


class FakeEngine:
    def __init__(self) -> None:
        self.transcripts: list[tuple[str, str, bool]] = []
        self.ticks = 0

    def enqueue_transcript(self, speaker: str, text: str, is_final: bool) -> EnqueueResult:
        self.transcripts.append((speaker, text, is_final))
        return EnqueueResult(True, len(self.transcripts))

    def tick(self) -> int:
        self.ticks += 1
        return 1


class LiveKitSessionEventBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SimoStore(Path(self.temp.name))
        self.alias_id = str(uuid4())
        self.alias = self.store.create_alias("Ada", alias_id=self.alias_id)
        self.conversation = self.store.create_conversation(self.alias_id)
        self.alias_participant_id = f"alias:{self.alias_id}"
        self.store.add_participant(
            self.conversation.conversation.conversation_id,
            "alias:bea",
            kind="external",
            display_name="Bea",
            transport_participant_id="lk-bea",
        )
        self.engine = FakeEngine()
        self.bridge = LiveKitSessionEventBridge(
            self.store,
            self.engine,  # type: ignore[arg-type]
            alias_id=self.alias_id,
            conversation_id=self.conversation.conversation.conversation_id,
            alias_participant_id=self.alias_participant_id,
            remote_participant_id="alias:bea",
            remote_transport_id="lk-bea",
            participant_ids={self.alias_participant_id, "alias:bea"},
            capacity=8,
            enable_learning=False,
        )
        self.bridge.start()

    async def asyncTearDown(self) -> None:
        await self.bridge.aclose()

    async def test_persists_generated_submitted_and_actually_spoken_text(self) -> None:
        self.bridge.assistant_generated("full generated response", "llm-1")
        self.bridge.tts_submitted("full generated response", "tts-1")
        self.bridge.observe_conversation_item(
            ConversationItemAddedEvent(
                item=llm.ChatMessage(
                    id="assistant-1",
                    role="assistant",
                    content=["actually spoken"],
                    interrupted=True,
                )
            )
        )
        await self.bridge.drain()

        detail = self.store.get_conversation(self.conversation.conversation.conversation_id)
        self.assertEqual(
            ["assistant.generated", "assistant.tts.submitted", "assistant.spoken"],
            [event.event_type for event in detail.events],
        )
        self.assertEqual("actually spoken", detail.events[-1].text)
        self.assertTrue(detail.events[-1].interrupted)
        self.assertEqual(self.alias.active_persona_version, detail.events[-1].persona_version)
        self.assertEqual(
            [(self.alias_participant_id, "actually spoken", True)],
            self.engine.transcripts,
        )

    async def test_commits_user_chat_item_once_with_transport_attribution(self) -> None:
        self.bridge.observe_user_transcription(
            UserInputTranscribedEvent(
                transcript="my favorite color is blue",
                is_final=True,
                item_id="user-1",
                speaker_id="lk-bea",
            )
        )
        self.bridge.observe_conversation_item(
            ConversationItemAddedEvent(
                item=llm.ChatMessage(
                    id="user-1",
                    role="user",
                    content=["my favorite color is blue"],
                )
            )
        )
        await self.bridge.drain()

        detail = self.store.get_conversation(self.conversation.conversation.conversation_id)
        self.assertEqual(1, len(detail.events))
        event = detail.events[0]
        self.assertEqual("user.transcript.final", event.event_type)
        self.assertEqual("alias:bea", event.participant_id)
        self.assertEqual("lk-bea", event.metadata["transport_participant_id"])
        self.assertEqual(
            [("alias:bea", "my favorite color is blue", True)],
            self.engine.transcripts,
        )

    async def test_bounded_queue_drops_oldest_before_worker_starts(self) -> None:
        await self.bridge.aclose()
        replacement = LiveKitSessionEventBridge(
            self.store,
            self.engine,  # type: ignore[arg-type]
            alias_id=self.alias_id,
            conversation_id=self.conversation.conversation.conversation_id,
            alias_participant_id=self.alias_participant_id,
            remote_participant_id="alias:bea",
            remote_transport_id="lk-bea",
            participant_ids={self.alias_participant_id, "alias:bea"},
            capacity=2,
            enable_learning=False,
        )
        replacement.assistant_generated("one", "1")
        replacement.assistant_generated("two", "2")
        replacement.assistant_generated("three", "3")

        self.assertEqual(1, replacement.stats().dropped)
        replacement.start()
        await replacement.aclose()
        self.bridge = replacement


if __name__ == "__main__":
    unittest.main()
