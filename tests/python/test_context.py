from __future__ import annotations

import unittest

from simo.context import (
    ContextMemoryClaim,
    ContextParticipant,
    ConversationContextScope,
    DropPolicy,
    NativeContextEngine,
)


class NativeContextTests(unittest.TestCase):
    def test_snapshot_and_stats_cross_native_boundary(self) -> None:
        with NativeContextEngine(
            queue_capacity=2,
            max_segments=2,
            drop_policy=DropPolicy.DROP_OLDEST,
        ) as engine:
            engine.enqueue_transcript("user", "first")
            engine.enqueue_transcript("user", "second")
            engine.enqueue_transcript("agent", "third")
            self.assertEqual(2, engine.tick())
            snapshot = engine.snapshot()
            self.assertEqual(1, snapshot["revision"])
            self.assertEqual(["second", "third"], [item["text"] for item in snapshot["items"]])
            stats = engine.stats()
            self.assertEqual(3, stats.accepted)
            self.assertEqual(1, stats.dropped)
            self.assertEqual(2, stats.retained)

    def test_closed_engine_rejects_use(self) -> None:
        engine = NativeContextEngine()
        engine.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            engine.tick()

    def test_scoped_worlds_are_isolated_and_serialize_values_only(self) -> None:
        left_scope = ConversationContextScope(
            "alias-left",
            "conversation-left",
            "left-local",
            (
                ContextParticipant("left-local", "alias", "alias-left", "Left", "lk-left"),
                ContextParticipant("right-remote", "alias", "alias-right", "Right", "lk-right"),
            ),
        )
        right_scope = ConversationContextScope(
            "alias-right",
            "conversation-right",
            "right-local",
            (
                ContextParticipant("right-local", "alias", "alias-right", "Right", "lk-right"),
                ContextParticipant("left-remote", "alias", "alias-left", "Left", "lk-left"),
            ),
        )
        with (
            NativeContextEngine(scope=left_scope) as left,
            NativeContextEngine(scope=right_scope) as right,
        ):
            with self.assertRaisesRegex(ValueError, "outside the context scope"):
                left.enqueue_transcript("unknown", "must fail closed")
            left.enqueue_transcript("right-remote", "visible only to left")
            right.enqueue_transcript("left-remote", "visible only to right")
            left.begin_memory_refresh()
            left.upsert_memory_claim(
                ContextMemoryClaim(
                    "claim-left",
                    "right-remote",
                    "preference.favorite:door",
                    "preference",
                    "Favorite door is green.",
                    "source-conversation",
                    "source-event",
                    "2027-01-01",
                    0.97,
                )
            )
            memory_stats = left.commit_memory_refresh()
            left.tick()
            right.tick()
            left_snapshot = left.snapshot()
            right_snapshot = right.snapshot()

        self.assertEqual("alias-left", left_snapshot["alias_id"])
        self.assertEqual("conversation-left", left_snapshot["conversation_id"])
        self.assertEqual("left-local", left_snapshot["local_participant_id"])
        self.assertEqual("lk-right", left_snapshot["participants"][1]["transport_participant_id"])
        self.assertEqual("visible only to left", left_snapshot["items"][0]["text"])
        self.assertEqual(1, memory_stats.claims)
        self.assertEqual("Favorite door is green.", left_snapshot["memories"][0]["content"])
        self.assertEqual("visible only to right", right_snapshot["items"][0]["text"])
        self.assertNotIn("visible only to right", str(left_snapshot))
        self.assertFalse(any("entity" in key or "handle" in key for key in left_snapshot))


if __name__ == "__main__":
    unittest.main()
