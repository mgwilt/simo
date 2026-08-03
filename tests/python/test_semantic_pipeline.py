from __future__ import annotations

import unittest
import time
from dataclasses import FrozenInstanceError, replace

from pipecat.frames.frames import LLMTextFrame, TTSAudioRawFrame

from simo.adapters.pipecat.deterministic import run_deterministic_pipeline
from simo.adapters.pipecat.semantic_turn import (
    ContextItem,
    SemanticContextSnapshot,
    format_semantic_context,
)
from simo.context import NativeContextEngine


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
        stale = replace(
            snapshot,
            captured_monotonic_ns=time.monotonic_ns() - 2_000_000_000,
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            stale.require_fresh(1_000)


class DeterministicPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_pipeline_injects_once_and_emits_audio_per_turn(self) -> None:
        with NativeContextEngine() as engine:
            result = await run_deterministic_pipeline(
                engine,
                ["hello", "remember the blue door"],
            )

        self.assertEqual(2, result.injection_count)
        self.assertEqual(2, result.observation_accepted)
        self.assertGreaterEqual(result.observation_duplicates, 2)
        self.assertEqual(2, result.engine_revision)
        self.assertEqual(0, result.engine_dropped)
        self.assertEqual(0, result.observer_mailbox_dropped)
        self.assertEqual(0, result.observer_mailbox_queued)
        self.assertEqual([1, 2], [turn.context.revision for turn in result.turns])
        self.assertEqual(
            [1, 2],
            [len(turn.context.items) for turn in result.turns],
        )
        self.assertEqual(
            2,
            sum(isinstance(frame, LLMTextFrame) for frame in result.frames),
        )
        audio = [
            frame for frame in result.frames if isinstance(frame, TTSAudioRawFrame)
        ]
        self.assertEqual(2, len(audio))
        self.assertTrue(all(frame.audio for frame in audio))
        self.assertTrue(all(frame.sample_rate == 24_000 for frame in audio))


if __name__ == "__main__":
    unittest.main()
