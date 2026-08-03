from __future__ import annotations

import unittest

from simo.context import DropPolicy, EnqueueResult
from simo.observation import BoundedTranscriptMailbox, FinalTranscriptObservationBridge


class RecordingSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    def enqueue_transcript(self, speaker: str, text: str, is_final: bool = True) -> EnqueueResult:
        self.calls.append((speaker, text, is_final))
        return EnqueueResult(True, len(self.calls))


class ObservationBridgeTests(unittest.TestCase):
    def test_filters_and_deduplicates_before_sink(self) -> None:
        sink = RecordingSink()
        bridge = FinalTranscriptObservationBridge(sink, dedupe_capacity=2)
        self.assertIsNone(
            bridge.observe(frame_key="partial", speaker="user", text="hel", is_final=False)
        )
        accepted = bridge.observe(frame_key="final-1", speaker="user", text="hello", is_final=True)
        self.assertIsNotNone(accepted)
        self.assertIsNone(
            bridge.observe(frame_key="final-1", speaker="user", text="hello", is_final=True)
        )
        self.assertEqual([("user", "hello", True)], sink.calls)
        self.assertEqual(1, bridge.stats().accepted)
        self.assertEqual(1, bridge.stats().duplicate)
        self.assertEqual(1, bridge.stats().filtered)

    def test_dedupe_cache_is_bounded(self) -> None:
        sink = RecordingSink()
        bridge = FinalTranscriptObservationBridge(sink, dedupe_capacity=1)
        bridge.observe(frame_key="one", speaker="user", text="one", is_final=True)
        bridge.observe(frame_key="two", speaker="user", text="two", is_final=True)
        bridge.observe(frame_key="one", speaker="user", text="one again", is_final=True)
        self.assertEqual(3, len(sink.calls))

    def test_observer_mailbox_bounds_run_ahead_and_promotes_by_key(self) -> None:
        mailbox = BoundedTranscriptMailbox(
            capacity=1,
            drop_policy=DropPolicy.DROP_OLDEST,
        )
        bridge = FinalTranscriptObservationBridge(mailbox)
        bridge.observe(frame_key="one", speaker="user", text="one", is_final=True)
        bridge.observe(frame_key="two", speaker="user", text="two", is_final=True)
        self.assertIsNone(mailbox.pop("one"))
        self.assertEqual("two", mailbox.pop("two").text)  # type: ignore[union-attr]
        self.assertEqual(1, mailbox.stats().dropped)


if __name__ == "__main__":
    unittest.main()
