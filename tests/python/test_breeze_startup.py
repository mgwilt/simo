from __future__ import annotations

import hashlib
import http.client
import json
import subprocess  # noqa: S404 - mocked process boundary only
import tempfile
import time
import unittest
import wave
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

from scripts import measure_breeze_startup as probe

Record = dict[str, object]
FINGERPRINT = "a" * 64
REQUEST_ID = "api-" + "1" * 32
PCM = b"\x01\x00" * 1920


class Response:
    def __init__(self, chunks: list[bytes | BaseException]) -> None:
        self.status = 200
        self.chunks: list[bytes | BaseException] = chunks
        self.headers = {
            "X-Breeze-Runtime": FINGERPRINT,
            "X-Breeze-Request-ID": REQUEST_ID,
            "X-Sample-Rate": "24000",
            "X-Sample-Format": "s16le",
        }

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self.headers.items())

    def getheader(self, key: str) -> str | None:
        return self.headers.get(key)

    def read1(self, size: int) -> bytes:
        value = self.chunks.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class Connection:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls: list[tuple[str, str, bytes, dict[str, str]]] = []
        self.closed = False

    def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
        self.calls.append((method, path, body, headers))

    def getresponse(self) -> Response:
        return self.response

    @contextmanager
    def bounded(self, deadline: float) -> Generator[http.client.HTTPConnection]:
        try:
            yield cast(http.client.HTTPConnection, cast(object, self))
        finally:
            self.closed = True


class StartupTests(unittest.TestCase):
    def ready(self) -> Record:
        return {
            **dict.fromkeys(probe.RECIPE_FIELDS, "fixture"),
            "status": "ready",
            "busy": False,
            "source_digest": "source",
            "runtime_fingerprint": FINGERPRINT,
        }

    def metrics(self) -> Record:
        return {
            "runtime_fingerprint": FINGERPRINT,
            "busy": False,
            "last_request": {
                "request_id": REQUEST_ID,
                "completed": True,
                "eos_reached": True,
                "cancelled": False,
                "audio_samples": 1920,
                "codec_frames": 1,
                "audio_s": 0.08,
            },
        }

    def measure(self, path: Path, *, seen: set[str] | None = None) -> Record:
        now = time.perf_counter()
        return probe.measure_request(
            path,
            FINGERPRINT,
            "Fixture instruction",
            now - 2,
            set() if seen is None else seen,
            ready_at=now - 1,
            ordinal=0,
        )

    def test_source_digest_uses_service_order_and_relative_fork_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            files = {
                "vendor/breeze-tts/breeze_infer/z.py": b"z",
                "vendor/breeze-tts/breeze_infer/a.py": b"a",
                "vendor/breeze-tts/models/m.py": b"m",
                "services/breeze/serve.py": b"launcher",
            }
            for name, raw in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            expected = hashlib.sha256(b"breeze_infer/a.pyabreeze_infer/z.pyzmodels/m.pymlauncher")
            digest, sources = probe.source_identity(root)
            self.assertEqual(digest, expected.hexdigest())
            self.assertEqual(len(sources), 4)

    def test_exact_readiness_source_and_recipe(self) -> None:
        self.assertEqual(probe.validate_ready(self.ready(), self.ready(), "source"), FINGERPRINT)
        for key, value in (
            ("status", "loading"),
            ("busy", True),
            ("busy", 0),
            ("source_digest", "other"),
            ("runtime_fingerprint", "bad"),
            *((key, "changed") for key in probe.RECIPE_FIELDS),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                probe.validate_ready({**self.ready(), key: value}, self.ready(), "source")

    def test_listener_must_belong_to_live_owned_group(self) -> None:
        poll = Mock(return_value=None)
        process = Mock(pid=100, poll=poll)
        result = Mock(returncode=0, stdout="101\n102\n")
        with (
            patch.object(probe.subprocess, "run", return_value=result),
            patch.object(
                probe.os,
                "getpgid",
                return_value=100,
            ) as group,
        ):
            typed = cast(subprocess.Popen[bytes], process)
            self.assertEqual(probe.assert_owned_listener(typed), [101, 102])
            group.return_value = 200
            with self.assertRaisesRegex(RuntimeError, "not owned"):
                probe.assert_owned_listener(typed)
            result.stdout = "101\ninvalid\n"
            with self.assertRaisesRegex(RuntimeError, "Invalid"):
                probe.assert_owned_listener(typed)
            poll.return_value = 1
            with self.assertRaisesRegex(RuntimeError, "exited"):
                probe.assert_owned_listener(typed)

    def test_absolute_deadline_aborts_retained_socket_even_if_connection_drops_it(self) -> None:
        shutdown, close, cancel, join, settimeout = Mock(), Mock(), Mock(), Mock(), Mock()
        transport = Mock(shutdown=shutdown, settimeout=settimeout)
        connection = Mock(sock=transport, close=close)
        timer = Mock(cancel=cancel, join=join)
        aborts: list[Callable[[], None]] = []

        def create_timer(seconds: float, callback: Callable[[], None]) -> Mock:
            aborts.append(callback)
            return timer

        with (
            patch.object(probe.http.client, "HTTPConnection", return_value=connection),
            patch.object(probe.threading, "Timer", side_effect=create_timer),
            self.assertRaisesRegex(TimeoutError, "deadline"),
            probe.bounded_connection(time.perf_counter() + 30),
        ):
            connection.sock = None  # HTTPConnection does this for Connection:close responses.
            aborts[0]()
        shutdown.assert_called()
        cancel.assert_called_once()
        join.assert_called_once_with(timeout=1)
        close.assert_called_once()
        self.assertGreater(cast(float, settimeout.call_args.args[0]), 2)

    def test_expired_deadline_does_not_connect(self) -> None:
        with patch.object(probe.http.client, "HTTPConnection") as factory:
            with self.assertRaises(TimeoutError), probe.bounded_connection(time.perf_counter() - 1):
                self.fail("Expired connection was yielded")
            factory.assert_not_called()

    def test_complete_pcm_metrics_identity_and_actual_arrivals(self) -> None:
        connection = Connection(Response([PCM[:1], PCM[1:], b""]))
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(probe, "bounded_connection", side_effect=connection.bounded),
            patch.object(probe, "health", return_value=self.metrics()),
        ):
            path = Path(temporary).resolve() / "request"
            seen: set[str] = set()
            result = self.measure(path, seen=seen)
            self.assertTrue(result["completed"])
            self.assertEqual(result["pcm_sha256"], probe.sha(PCM))
            self.assertEqual(result["received_bytes"], len(PCM))
            self.assertEqual(seen, {REQUEST_ID})
            self.assertEqual(result["kind"], "first")
            arrivals = cast(list[Record], result["arrivals"])
            self.assertEqual(result["request_to_first_byte_s"], arrivals[0]["seconds"])
            self.assertEqual(result["request_to_first_pcm_s"], arrivals[1]["seconds"])
            self.assertGreater(cast(float, result["verified_ready_to_request_s"]), 1)
            self.assertEqual((path / "received.pcm").read_bytes(), PCM)
            self.assertEqual(probe.read_json(path / "report.json")[0], result)
            with wave.open(str(path / "complete.wav"), "rb") as audio:
                self.assertEqual(audio.readframes(audio.getnframes()), PCM)
            self.assertEqual(connection.calls[0][0:2], ("POST", "/v1/audio/speech"))
            self.assertIn(b"seed=17", connection.calls[0][2])
            self.assertEqual(connection.calls[0][3]["X-Breeze-Runtime"], FINGERPRINT)
            self.assertTrue(connection.closed)

    def test_failed_partial_never_becomes_completed_wav(self) -> None:
        connection = Connection(Response([PCM[:40], TimeoutError("delayed tail")]))
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(probe, "bounded_connection", side_effect=connection.bounded),
            patch.object(probe, "health") as health,
        ):
            path = Path(temporary).resolve() / "request"
            with self.assertRaisesRegex(TimeoutError, "delayed tail"):
                self.measure(path)
            report = probe.read_json(path / "report.json")[0]
            self.assertFalse(report["completed"])
            self.assertEqual(report["received_bytes"], 40)
            self.assertEqual((path / "received.pcm").read_bytes(), PCM[:40])
            self.assertFalse((path / "complete.wav").exists())
            health.assert_not_called()
            self.assertTrue(connection.closed)

    def test_bad_metadata_duplicate_ids_and_incomplete_pcm_fail_closed(self) -> None:
        for kind in (
            "runtime",
            "status",
            "format",
            "rate",
            "id",
            "duplicate",
            "odd",
            "empty",
            "oversized",
        ):
            response = Response([PCM, b""])
            seen: set[str] = set()
            if kind == "runtime":
                response.headers["X-Breeze-Runtime"] = "other"
            elif kind == "status":
                response.status = 500
            elif kind == "format":
                response.headers["X-Sample-Format"] = "float32"
            elif kind == "rate":
                response.headers["X-Sample-Rate"] = "48000"
            elif kind == "id":
                response.headers["X-Breeze-Request-ID"] = "invalid"
            elif kind == "duplicate":
                seen.add(REQUEST_ID)
            elif kind == "odd":
                response.chunks = [b"x", b""]
            elif kind == "empty":
                response.chunks = [b""]
            elif kind == "oversized":
                response.chunks = [b"x" * (probe.MAX_PCM + 1)]
            connection = Connection(response)
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory() as temporary,
                patch.object(probe, "bounded_connection", side_effect=connection.bounded),
            ):
                path = Path(temporary).resolve() / "request"
                with self.assertRaises(ValueError):
                    self.measure(path, seen=seen)
                self.assertFalse(probe.read_json(path / "report.json")[0]["completed"])
                self.assertFalse((path / "complete.wav").exists())

    def test_unmatched_eos_cancelled_or_counts_cannot_complete(self) -> None:
        for key, value in (
            ("eos_reached", False),
            ("cancelled", True),
            ("request_id", "other"),
            ("audio_samples", 3840),
        ):
            metrics = self.metrics()
            cast(Record, metrics["last_request"])[key] = value
            connection = Connection(Response([PCM, b""]))
            with (
                self.subTest(key=key),
                tempfile.TemporaryDirectory() as temporary,
                patch.object(probe, "bounded_connection", side_effect=connection.bounded),
                patch.object(probe, "health", return_value=metrics),
                patch.object(probe.time, "sleep", side_effect=TimeoutError("poll bound")),
            ):
                path = Path(temporary).resolve() / "request"
                with self.assertRaises(TimeoutError):
                    self.measure(path)
                self.assertFalse((path / "complete.wav").exists())

    def test_cycle_failure_still_cleans_owned_process_and_records_failure(self) -> None:
        for cleanup_error in (False, True):
            process = Mock(pid=100, returncode=-15, poll=Mock(return_value=None))
            with (
                self.subTest(cleanup_error=cleanup_error),
                tempfile.TemporaryDirectory() as temporary,
                patch.object(probe, "assert_free_port"),
                patch.object(probe.subprocess, "Popen", return_value=process) as launch,
                patch.object(probe, "health", side_effect=ValueError("invalid ready")),
                patch.object(
                    probe,
                    "cleanup_group",
                    return_value={"group_gone": True},
                    side_effect=RuntimeError("uncertain") if cleanup_error else None,
                ) as cleanup,
            ):
                path = Path(temporary).resolve() / "cycle"
                with self.assertRaises((ValueError, RuntimeError)):
                    probe.run_cycle(path, Path(temporary), {}, "source", set())
                record = probe.read_json(path / "report.json")[0]
                self.assertFalse(record["completed"])
                self.assertIn("failure", record)
                self.assertEqual("cleanup_failure" in record, cleanup_error)
                cleanup.assert_called_once_with(process)
                self.assertTrue(launch.call_args.kwargs["start_new_session"])

    def test_failed_cycle_retained_without_starting_next_cycle(self) -> None:
        reference: Record = {"completed": True}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(probe, "read_json", return_value=(reference, probe.REFERENCE_SHA)),
            patch.object(probe, "run_cycle", side_effect=RuntimeError("cycle failed")) as cycle,
        ):
            path = Path(temporary) / "run"
            with self.assertRaisesRegex(RuntimeError, "cycle failed"):
                probe.run(path, Path(__file__).resolve().parents[2])
            record = cast(Record, json.loads((path / "report.json").read_bytes()))
            self.assertFalse(record["completed"])
            self.assertEqual(record["attempted_cycles"], [str(path / "cycle-0")])
            self.assertEqual(record["cycles"], [])
            cycle.assert_called_once()

    def test_owned_cycle_records_first_plus_three_warm_requests_and_cleanup(self) -> None:
        process = Mock(pid=100, returncode=-15, poll=Mock(return_value=None))
        reference: Record = {"runtime": self.ready(), "instruction": "Fixture instruction"}

        def measured(
            directory: Path,
            fingerprint: str,
            instruction: str,
            launched: float,
            seen: set[str],
            *,
            ready_at: float,
            ordinal: int,
        ) -> Record:
            return {
                "pcm_sha256": "pcm",
                "kind": "first" if ordinal == 0 else "warm",
                "ordinal": ordinal,
            }

        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(probe, "assert_free_port"),
            patch.object(probe.subprocess, "Popen", return_value=process),
            patch.object(probe, "health", return_value=self.ready()) as ready,
            patch.object(probe, "assert_owned_listener", return_value=[101]) as ownership,
            patch.object(probe, "source_identity", return_value=("source", {})),
            patch.object(probe, "measure_request", side_effect=measured) as request,
            patch.object(probe, "cleanup_group", return_value={"group_gone": True}) as cleanup,
            patch("builtins.print"),
        ):
            path = Path(temporary).resolve() / "cycle"
            result = probe.run_cycle(path, Path(temporary), reference, "source", set())
            self.assertTrue(result["completed"])
            self.assertEqual(
                [row["kind"] for row in cast(list[Record], result["requests"])],
                ["first", "warm", "warm", "warm"],
            )
            self.assertEqual(request.call_count, 4)
            self.assertEqual(ownership.call_count, 5)
            ready.assert_called_once()
            cleanup.assert_called_once_with(process)
            self.assertEqual(
                result["attempted_requests"], [str(path / f"request-{i}") for i in range(4)]
            )

    def test_exclusive_output_and_fixed_cycle_bounds(self) -> None:
        for cycles in (0, 4):
            with self.assertRaises(ValueError):
                probe.run(Path("unused"), Path("unused"), cycles=cycles)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileExistsError):
                self.measure(Path(temporary))


if __name__ == "__main__":
    unittest.main()
