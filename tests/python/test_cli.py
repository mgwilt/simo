from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

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
        with redirect_stdout(output):
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
        self.assertEqual(1, result["snapshot"]["revision"])
        self.assertEqual(
            ["hello", "remember the blue door"],
            [item["text"] for item in result["snapshot"]["items"]],
        )
        self.assertEqual(2, result["stats"]["processed"])


if __name__ == "__main__":
    unittest.main()
