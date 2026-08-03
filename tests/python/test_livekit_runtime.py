from __future__ import annotations

import unittest

from simo.livekit_runtime import LiveKitAliasRunRequest, build_livekit_history
from simo.persistence import TranscriptTurn


class LiveKitAliasRuntimeTests(unittest.TestCase):
    def test_history_rehydrates_only_review_transcript_roles_and_interruptions(self) -> None:
        transcript = (
            TranscriptTurn(
                1,
                "alias:remote",
                "Bea",
                "external",
                "Do you remember blue?",
                "2026-08-02T00:00:00Z",
                False,
                "user.transcript.final",
            ),
            TranscriptTurn(
                4,
                "alias:local",
                "Ada",
                "alias",
                "Yes, blue.",
                "2026-08-02T00:00:01Z",
                True,
                "assistant.spoken",
            ),
        )

        history = build_livekit_history(transcript, "alias:local")

        self.assertEqual(["user", "assistant"], [item.role for item in history.messages()])
        self.assertEqual(
            ["Do you remember blue?", "Yes, blue."],
            [item.text_content for item in history.messages()],
        )
        self.assertTrue(history.messages()[1].interrupted)

    def test_request_rejects_unbounded_or_unattributed_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "remote display name"):
            LiveKitAliasRunRequest(
                "alias-a",
                "alias:b",
                "",
                "lk-b",
            )
        with self.assertRaisesRegex(ValueError, "max spoken turns"):
            LiveKitAliasRunRequest(
                "alias-a",
                "alias:b",
                "Bea",
                "lk-b",
                max_spoken_turns=0,
            )


if __name__ == "__main__":
    unittest.main()
