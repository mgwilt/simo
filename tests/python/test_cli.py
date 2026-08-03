from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import cast
from unittest.mock import patch

from simo.cli import main
from simo.config import RunMode
from simo.doctor import DoctorReport


class CliTests(unittest.TestCase):
    def test_memory_commands_inspect_correct_and_forget_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            alias_output = io.StringIO()
            with redirect_stdout(alias_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(data_dir),
                            "alias",
                            "create",
                            "Ada",
                            "--json",
                        ]
                    ),
                )
            alias = cast(dict[str, object], cast(object, json.loads(alias_output.getvalue())))
            alias_id = cast(str, alias["alias_id"])

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(data_dir),
                            "talk",
                            "--alias",
                            alias_id,
                            "--turn",
                            "I like tea.",
                            "--json",
                        ]
                    ),
                )

            listed_output = io.StringIO()
            with redirect_stdout(listed_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(data_dir),
                            "memory",
                            "list",
                            "--alias",
                            alias_id,
                            "--status",
                            "active",
                            "--json",
                        ]
                    ),
                )
            claims = cast(list[object], cast(object, json.loads(listed_output.getvalue())))
            claim = cast(dict[str, object], claims[0])
            claim_id = cast(str, claim["claim_id"])
            self.assertEqual("Likes tea.", claim["content"])

            shown_output = io.StringIO()
            with redirect_stdout(shown_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(data_dir),
                            "memory",
                            "show",
                            claim_id,
                            "--json",
                        ]
                    ),
                )
            shown = cast(dict[str, object], cast(object, json.loads(shown_output.getvalue())))
            self.assertEqual(claim_id, shown["claim_id"])
            self.assertIn("event_id", cast(dict[str, object], shown["provenance"]))

            corrected_output = io.StringIO()
            with redirect_stdout(corrected_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(data_dir),
                            "memory",
                            "correct",
                            claim_id,
                            "Likes green tea.",
                            "--json",
                        ]
                    ),
                )
            corrected = cast(
                dict[str, object], cast(object, json.loads(corrected_output.getvalue()))
            )
            corrected_id = cast(str, corrected["claim_id"])
            self.assertEqual(claim_id, corrected["supersedes_claim_id"])

            forgotten_output = io.StringIO()
            with redirect_stdout(forgotten_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(data_dir),
                            "memory",
                            "forget",
                            corrected_id,
                            "--yes",
                            "--json",
                        ]
                    ),
                )
            forgotten = cast(
                dict[str, object], cast(object, json.loads(forgotten_output.getvalue()))
            )
            self.assertTrue(forgotten["forgotten"])

    def test_talk_resumes_and_exports_a_persisted_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            alias_output = io.StringIO()
            with redirect_stdout(alias_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(root / "data"),
                            "alias",
                            "create",
                            "Mira",
                            "--json",
                        ]
                    ),
                )
            alias = cast(dict[str, object], cast(object, json.loads(alias_output.getvalue())))
            alias_id = cast(str, alias["alias_id"])

            talk_output = io.StringIO()
            with redirect_stdout(talk_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(root / "data"),
                            "talk",
                            "--alias",
                            alias_id,
                            "--turn",
                            "First turn.",
                            "--turn",
                            "Second turn.",
                            "--json",
                        ]
                    ),
                )
            result = cast(dict[str, object], cast(object, json.loads(talk_output.getvalue())))
            conversation_id = cast(str, result["conversation_id"])
            transcript = cast(list[object], result["transcript"])
            self.assertEqual(4, len(transcript))

            resumed_output = io.StringIO()
            with redirect_stdout(resumed_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(root / "data"),
                            "talk",
                            "--alias",
                            alias_id,
                            "--conversation",
                            conversation_id,
                            "--turn",
                            "Third turn after restart.",
                            "--complete",
                            "--json",
                        ]
                    ),
                )
            resumed = cast(dict[str, object], cast(object, json.loads(resumed_output.getvalue())))
            self.assertEqual(6, len(cast(list[object], resumed["transcript"])))

            export_path = root / "conversation.json"
            export_output = io.StringIO()
            with redirect_stdout(export_output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "--data-dir",
                            str(root / "data"),
                            "conversation",
                            "export",
                            conversation_id,
                            str(export_path),
                            "--json",
                        ]
                    ),
                )
            exported = cast(
                dict[str, object],
                cast(object, json.loads(export_path.read_text(encoding="utf-8"))),
            )
            self.assertEqual(6, len(cast(list[object], exported["transcript"])))

    def test_alias_and_conversation_commands_are_structured_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            alias_output = io.StringIO()
            with redirect_stdout(alias_output):
                status = main(
                    [
                        "--data-dir",
                        str(data_dir),
                        "alias",
                        "create",
                        "Ada",
                        "--json",
                    ]
                )
            alias = cast(dict[str, object], cast(object, json.loads(alias_output.getvalue())))
            alias_id = cast(str, alias["alias_id"])
            self.assertEqual(0, status)
            self.assertEqual("Ada", alias["display_name"])

            conversation_output = io.StringIO()
            with redirect_stdout(conversation_output):
                status = main(
                    [
                        "--data-dir",
                        str(data_dir),
                        "conversation",
                        "create",
                        "--alias",
                        alias_id,
                        "--title",
                        "A durable conversation",
                        "--json",
                    ]
                )
            conversation = cast(
                dict[str, object], cast(object, json.loads(conversation_output.getvalue()))
            )
            conversation_record = cast(dict[str, object], conversation["conversation"])
            self.assertEqual(0, status)
            self.assertEqual("A durable conversation", conversation_record["title"])

            show_output = io.StringIO()
            with redirect_stdout(show_output):
                status = main(
                    [
                        "--data-dir",
                        str(data_dir),
                        "alias",
                        "show",
                        alias_id,
                        "--json",
                    ]
                )
            detail = cast(dict[str, object], cast(object, json.loads(show_output.getvalue())))
            alias_detail = cast(dict[str, object], detail["alias"])
            runtime_profiles = cast(list[object], detail["runtime_profiles"])
            first_profile = cast(dict[str, object], runtime_profiles[0])
            self.assertEqual(0, status)
            self.assertEqual(1, alias_detail["active_persona_version"])
            self.assertEqual(1, first_profile["version"])

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

    def test_terminal_interrupt_returns_shell_status_130(self) -> None:
        errors = io.StringIO()

        def interrupt(coroutine: object) -> None:
            coroutine.close()  # type: ignore[attr-defined]
            raise KeyboardInterrupt

        with (
            redirect_stderr(errors),
            patch("simo.cli.asyncio.run", side_effect=interrupt),
        ):
            status = main(["headless", "--transcript", "private"])

        self.assertEqual(130, status)
        self.assertEqual("simo: interrupted", errors.getvalue().strip())

    def test_subprocess_event_stream_is_jsonl_without_content(self) -> None:
        command = (
            "from simo.cli import main; "
            "raise SystemExit(main(['headless','--transcript','private sentinel']))"
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            check=True,
            capture_output=True,
            text=True,
        )

        events = [json.loads(line) for line in result.stderr.splitlines()]
        self.assertTrue(events)
        self.assertTrue(all(event["schema"] == "simo.event.v1" for event in events))
        self.assertNotIn("private sentinel", result.stderr)

    def test_live_command_stops_at_failed_preflight(self) -> None:
        output = io.StringIO()
        report = DoctorReport(RunMode.LIVE, False, ())
        with (
            redirect_stdout(output),
            patch("simo.cli.inspect_runtime", return_value=report),
            patch("simo.cli.LiveRuntime") as runtime,
        ):
            status = main(["live"])

        self.assertEqual(1, status)
        self.assertIn("Simo live: not ready", output.getvalue())
        runtime.assert_not_called()


if __name__ == "__main__":
    unittest.main()
