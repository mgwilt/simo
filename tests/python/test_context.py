from __future__ import annotations

import unittest

from simo.context import DropPolicy, NativeContextEngine


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


if __name__ == "__main__":
    unittest.main()
