from __future__ import annotations

import time
import unittest
from dataclasses import FrozenInstanceError, replace

from pipecat.frames.frames import LLMTextFrame, TTSAudioRawFrame, TTSTextFrame
from simo.adapters.pipecat.deterministic import run_deterministic_pipeline
from simo.adapters.pipecat.semantic_turn import (
    ContextItem,
    SemanticContextSnapshot,
    format_semantic_context,
)
from simo.context import (
    ContextMemoryClaim,
    ContextParticipant,
    ConversationContextScope,
    NativeContextEngine,
)


class SemanticFormattingTests(unittest.TestCase):
    def test_snapshot_is_immutable_and_format_is_bounded(self) -> None:
        snapshot = SemanticContextSnapshot(
            revision=3,
            items=(ContextItem(1, "user", "blue door", True, 1.0),),
        )
        with self.assertRaises(FrozenInstanceError):
            snapshot.revision = 4  # type: ignore[misc]
        self.assertEqual(12, len(format_semantic_context(snapshot, max_chars=12)))
        rendered = format_semantic_context(snapshot, max_chars=100)
        self.assertEqual(
            "Simo semantic context (revision 3):\n- [1] user: blue door",
            rendered,
        )
        with_memory = replace(
            snapshot,
            memory_revision=1,
            memories=(
                ContextMemoryClaim(
                    "claim-1",
                    "user",
                    "preference.favorite:door",
                    "preference",
                    "Favorite door is green.",
                    "conversation-1",
                    "event-1",
                    "2027-01-01",
                    0.97,
                ),
            ),
        )
        memory_rendered = format_semantic_context(with_memory, max_chars=200)
        self.assertIn("[memory preference.favorite:door]", memory_rendered)
        self.assertIn("Favorite door is green.", memory_rendered)
        stale = replace(
            snapshot,
            captured_monotonic_ns=time.monotonic_ns() - 2_000_000_000,
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            stale.require_fresh(1_000)


class DeterministicPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_pipeline_injects_once_and_emits_audio_per_turn(self) -> None:
        scope = ConversationContextScope(
            "alias-test",
            "conversation-test",
            "alias-participant",
            (
                ContextParticipant(
                    "alias-participant", "alias", "alias-test", "Test Simo", "lk-simo"
                ),
                ContextParticipant("remote-user", "human", None, "Test user", "lk-user"),
            ),
        )
        with NativeContextEngine(scope=scope) as engine:
            result = await run_deterministic_pipeline(
                engine,
                ["hello", "remember the blue door"],
                speaker_id="remote-user",
            )

        self.assertEqual(2, result.injection_count)
        self.assertEqual(2, result.observation_accepted)
        self.assertGreaterEqual(result.observation_duplicates, 2)
        self.assertEqual(2, result.engine_revision)
        self.assertEqual(0, result.engine_dropped)
        self.assertEqual(0, result.observer_mailbox_dropped)
        self.assertEqual(0, result.observer_mailbox_queued)
        self.assertEqual([1, 2], [turn.context.revision for turn in result.turns])
        self.assertTrue(all(turn.context.alias_id == "alias-test" for turn in result.turns))
        self.assertTrue(
            all(turn.context.conversation_id == "conversation-test" for turn in result.turns)
        )
        self.assertTrue(
            all(turn.context.local_participant_id == "alias-participant" for turn in result.turns)
        )
        self.assertEqual(
            {"alias-participant", "remote-user"},
            {participant.participant_id for participant in result.turns[-1].context.participants},
        )
        self.assertEqual(
            [1, 2],
            [len(turn.context.items) for turn in result.turns],
        )
        self.assertEqual(
            2,
            sum(isinstance(frame, LLMTextFrame) for frame in result.frames),
        )
        audio = [frame for frame in result.frames if isinstance(frame, TTSAudioRawFrame)]
        self.assertEqual(2, len(audio))
        self.assertTrue(all(frame.audio for frame in audio))
        self.assertTrue(all(frame.sample_rate == 24_000 for frame in audio))
        spoken = [frame for frame in result.frames if isinstance(frame, TTSTextFrame)]
        self.assertEqual(2, len(spoken))
        self.assertTrue(all(frame.will_be_spoken for frame in spoken))


if __name__ == "__main__":
    unittest.main()
