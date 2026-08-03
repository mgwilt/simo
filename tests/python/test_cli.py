from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from simo.cli import main


class CliTests(unittest.TestCase):
    def test_doctor_json_is_machine_readable(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["doctor", "--json"])
        report = json.loads(output.getvalue())
        self.assertEqual(0, status)
        self.assertTrue(report["ready"])
        self.assertEqual("headless", report["mode"])

    def test_headless_runs_native_lifecycle_and_emits_snapshot(self) -> None:
        output = io.StringIO()
        events = io.StringIO()
        with redirect_stdout(output), redirect_stderr(events):
            status = main(
                [
                    "headless",
                    "--transcript",
                    "hello",
                    "--transcript",
                    "remember the blue door",
                ]
            )
        result = json.loads(output.getvalue())
        self.assertEqual(0, status)
        self.assertEqual(2, result["snapshot"]["revision"])
        self.assertEqual(
            ["hello", "remember the blue door"],
            [item["text"] for item in result["snapshot"]["items"]],
        )
        self.assertEqual(2, result["stats"]["processed"])
        self.assertEqual(2, result["pipeline"]["context_injections"])
        self.assertEqual(2, result["pipeline"]["llm_text_frames"])
        self.assertEqual(2, result["pipeline"]["tts_audio_frames"])
        self.assertGreater(result["knowledge"]["concepts"], 0)
        self.assertGreater(result["knowledge"]["links"], 0)
        self.assertEqual("completed", result["operations"]["shutdown_reason"])
        self.assertTrue(result["operations"]["clean_shutdown"])
        self.assertEqual(2, result["operations"]["world_revision"])
        self.assertEqual(2, result["operations"]["stages"]["text_inference"]["calls"])
        self.assertEqual(2, result["operations"]["stages"]["tts"]["calls"])
        self.assertNotIn("remember the blue door", events.getvalue())
        structured = [json.loads(line) for line in events.getvalue().splitlines()]
        self.assertEqual("starting", structured[0]["phase"])
        self.assertEqual("metrics", structured[-1]["event"])


if __name__ == "__main__":
    unittest.main()
