from __future__ import annotations

import copy
import hashlib
import json
import os
import runpy
import sys
import tempfile
import unittest
import wave
from collections.abc import Callable
from pathlib import Path
from types import FunctionType
from typing import Protocol, cast
from unittest.mock import patch

Record = dict[str, object]


class ArmView(Protocol):
    name: str
    backbone_bits: int | None
    depth_bits: int | None
    argv: tuple[str, ...]

    def settings(self, int8: Record) -> Record: ...


class QuantizationComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = cast(
            Record,
            runpy.run_path(
                str(Path(__file__).resolve().parents[2] / "scripts/compare_breeze_quantization.py")
            ),
        )
        cls.validate = staticmethod(cast(Callable[..., Record], cls.script["validate_probe"]))
        cls.compare = staticmethod(
            cast(Callable[[Record, Record], Record], cls.script["compare_pcm"])
        )
        cls.attempt = staticmethod(cast(Callable[..., Record], cls.script["run_attempt"]))
        cls.join = staticmethod(cast(Callable[..., list[Record]], cls.script["join_asr"]))

    def wav(self, path: Path, pcm: bytes) -> Record:
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(pcm)
        return {
            "path": str(path),
            "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "samples": len(pcm) // 2,
            "sample_rate": 24000,
        }

    def fixture(self, root: Path) -> tuple[Record, Record, list[Record], Record]:
        cases: list[Record] = [
            {
                "ordinal": i,
                "text": "Same words",
                "instruction": f"Voice {i // 3}",
                "voice": f"v{i // 3}",
                "original_index": 5,
                "seed": (17, 29, 42)[i % 3],
                "historical_asr": {},
            }
            for i in range(18)
        ]
        settings: Record = {"dtype": "fixture"}
        identity: Record = {"source": {}, "model_marker": {}, "metal_artifacts": {}, "corpus": {}}
        samples: list[Record] = []
        artifacts: list[Record] = []
        warmups: list[Record] = []
        for i in range(21):
            case = cases[max(0, i - 3)]
            name = f"warmup-{i}" if i < 3 else f"sample-{(i - 3) // 3}-{(i - 3) % 3}"
            artifact = self.wav(root / f"{name}.wav", b"\x01\x00" * 3840)
            sample: Record = {
                "prompt": case["text"],
                "instruction": case["instruction"],
                "seed": case["seed"],
                "failure": None,
                "started_unix_ns": i * 10 + 1,
                "ended_unix_ns": i * 10 + 2,
                "producer": {
                    "completed": True,
                    "eos_reached": True,
                    "cancelled": False,
                    "request_id": f"portable-{i:032x}",
                    "audio_samples": 3840,
                    "codec_frames": 2,
                    "audio_s": 0.16,
                },
                "arrivals": [{"seconds": 0.1, "samples": 1920}, {"seconds": 0.2, "samples": 1920}],
                "total_s": 0.21,
                "preparation_s": 0.01,
                "first_pcm_s": 0.1,
                "audio_s": 0.16,
                "total_rtf": 0.21 / 0.16,
                "steady_rtf": 1.25,
            }
            if i < 3:
                warmups.append({"result": sample, "artifact": artifact})
            else:
                samples.append(sample)
                artifacts.append(artifact)
        report: Record = {
            **identity,
            "started_unix_ns": 0,
            "ended_unix_ns": 1000,
            "compiled": True,
            "quality_acceptance": False,
            "lifecycle": [],
            "dependencies": self.script["DEPENDENCIES"],
            "effective_settings": settings,
            "samples": samples,
            "audio_artifacts": artifacts,
            "warmups": warmups,
        }
        return report, identity, cases, settings

    def test_complete_schedule_and_global_request_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, identity, cases, settings = self.fixture(root)
            seen: set[str] = set()
            result = self.validate(report, identity, cases, root, settings=settings, seen=seen)
            self.assertEqual(len(cast(list[Record], result["timed"])), 18)
            self.assertEqual(len(cast(list[Record], result["warmups"])), 3)
            self.assertEqual(len(seen), 21)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                self.validate(report, identity, cases, root, settings=settings, seen=seen)

    def test_schedule_and_identity_drift_rejected(self) -> None:
        for change in (
            "missing",
            "voice",
            "warmup",
            "source",
            "kernel",
            "recipe",
            "dependencies",
            "compiled",
            "truthy",
            "clock",
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report, identity, cases, settings = self.fixture(root)
                report = copy.deepcopy(report)
                samples = cast(list[Record], report["samples"])
                if change == "missing":
                    samples.pop()
                elif change == "voice":
                    samples[0], samples[3] = samples[3], samples[0]
                elif change == "warmup":
                    cast(Record, cast(list[Record], report["warmups"])[0]["result"])["seed"] = 29
                elif change == "source":
                    report["source"] = {"changed": True}
                elif change == "kernel":
                    report["metal_artifacts"] = {"changed": True}
                elif change == "recipe":
                    report["effective_settings"] = {"dtype": "other"}
                elif change == "dependencies":
                    report["dependencies"] = {}
                elif change == "compiled":
                    report["compiled"] = False
                elif change == "truthy":
                    cast(Record, samples[0]["producer"])["completed"] = 1
                elif change == "clock":
                    samples[0]["started_unix_ns"] = 0
                with self.assertRaises((ValueError, TypeError)):
                    self.validate(report, identity, cases, root, settings=settings, seen=set())

    def test_numeric_eos_audio_and_path_guards(self) -> None:
        for change in (
            "nan",
            "infinite",
            "negative",
            "order",
            "first",
            "count",
            "bool",
            "eos",
            "failure",
            "path",
            "wav",
            "rtf",
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report, identity, cases, settings = self.fixture(root)
                sample = cast(list[Record], report["samples"])[0]
                producer = cast(Record, sample["producer"])
                arrivals = cast(list[Record], sample["arrivals"])
                artifact = cast(list[Record], report["audio_artifacts"])[0]
                if change == "nan":
                    arrivals[0]["seconds"] = float("nan")
                elif change == "infinite":
                    arrivals[0]["seconds"] = float("inf")
                elif change == "negative":
                    arrivals[0]["seconds"] = -1
                elif change == "order":
                    arrivals.reverse()
                elif change == "first":
                    sample["first_pcm_s"] = 1
                elif change == "count":
                    producer["audio_samples"] = 1920
                elif change == "bool":
                    producer["codec_frames"] = True
                elif change == "eos":
                    producer["eos_reached"] = False
                elif change == "failure":
                    sample["failure"] = "failed"
                elif change == "path":
                    artifact["path"] = str(root.parent / "elsewhere.wav")
                elif change == "wav":
                    Path(str(artifact["path"])).write_bytes(b"truncated")
                elif change == "rtf":
                    sample["steady_rtf"] = 0.1
                with self.assertRaises((ValueError, TypeError, EOFError, wave.Error)):
                    self.validate(report, identity, cases, root, settings=settings, seen=set())

    def test_pcm_round_truncate_compatibility_not_equality(self) -> None:
        values = [
            (-1, -2, True),
            (1, 2, True),
            (0, -1, True),
            (1, 0, False),
            (-1, 0, False),
            (32767, -32767, False),
            (-32767, -32768, False),
        ]
        for before, after, expected in values:
            with (
                self.subTest(before=before, after=after),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                left = self.wav(root / "before.wav", before.to_bytes(2, "little", signed=True) * 10)
                right = self.wav(root / "after.wav", after.to_bytes(2, "little", signed=True) * 10)
                result = self.compare(right, {"ordinal": 0, "historical_artifact": left})
                self.assertEqual(result["conversion_compatible"], expected)

    def test_asr_join_uses_report_ordinal_not_ambiguous_text_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, cases, _ = self.fixture(root)
            reports = [root / "bf16.json", root / "int8.json"]
            for path in reports:
                path.write_text("{}", encoding="utf-8")
            groups: list[Record] = [
                {
                    "benchmark": str(path),
                    "samples": [
                        {
                            "prompt": c["text"],
                            "seed": c["seed"],
                            "transcript": "Same words",
                            "word_errors": 0,
                            "reference_words": 2,
                        }
                        for c in cases
                    ],
                }
                for path in reports
            ]
            asr: Record = {"quality_acceptance": False, "resident_screen": None, "reports": groups}
            result = self.join(asr, reports, cases)
            self.assertEqual(len(result), 36)
            self.assertNotEqual(result[0]["voice"], result[3]["voice"])
            self.assertEqual((result[0]["ordinal"], result[3]["ordinal"]), (0, 3))
            cast(list[Record], groups[0]["samples"])[0]["word_errors"] = 1
            with self.assertRaisesRegex(ValueError, "word-error"):
                self.join(asr, reports, cases)

    def test_attempt_retains_exit_failure_timeout_and_exclusive_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failed = self.attempt(
                root / "failed",
                [sys.executable, "-c", "print('retained');raise SystemExit(3)"],
                root,
            )
            self.assertFalse(failed["completed"])
            self.assertEqual(failed["exit_code"], 3)
            self.assertEqual(
                (root / "failed/report.json").read_text(encoding="utf-8"), "retained\n"
            )
            with self.assertRaises(FileExistsError):
                self.attempt(root / "failed", [sys.executable, "-c", "raise SystemExit(0)"], root)
            timed = self.attempt(
                root / "timed",
                [sys.executable, "-c", "import time;time.sleep(60)"],
                root,
                timeout_s=0.1,
            )
            self.assertFalse(timed["completed"])
            self.assertEqual(cast(Record, timed["failure"])["type"], "TimeoutExpired")
            self.assertIsNotNone(timed["exit_code"])

    def test_first_arm_failure_stops_before_second_or_asr(self) -> None:
        loaded = self.script["main"]
        assert isinstance(loaded, FunctionType)
        namespace = cast(Record, loaded.__globals__)
        main = cast(Callable[[], int], loaded)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, cases, _ = self.fixture(root)
            calls: list[Path] = []

            def failed(path: Path, command: list[str], repository: Path, *, label: str) -> Record:
                calls.append(path)
                return {"completed": False, "exit_code": 1}

            def fixture_cases(*args: object) -> list[Record]:
                return cases

            def fixture_bound(*args: object) -> Record:
                return {"effective_settings": {}}

            def fixture_identity(*args: object) -> Record:
                return {}

            with (
                patch.dict(
                    namespace,
                    {
                        "build_cases": fixture_cases,
                        "bound": fixture_bound,
                        "identity": fixture_identity,
                        "run_attempt": failed,
                    },
                ),
                patch.object(
                    sys, "argv", ["compare", "--output-dir", str(root / "output"), "--run"]
                ),
            ):
                self.assertEqual(main(), 1)
            self.assertEqual([p.name for p in calls], ["bf16"])
            retained = cast(Record, json.loads((root / "output/comparison.json").read_bytes()))
            self.assertFalse(retained["completed"])
            self.assertFalse(retained["quality_acceptance"])

    def test_owned_descendant_ignoring_term_is_killed_after_leader_exits(self) -> None:
        if not hasattr(os, "killpg"):
            self.skipTest("POSIX process groups required")
            return
        # The child acknowledges its TERM handler before the leader can exit.
        child = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print('ready',flush=True);time.sleep(15)"
        setup = (
            "import subprocess,sys,time;"
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.PIPE);"
            "assert p.stdout.readline()==b'ready\\n';print(p.pid,flush=True);"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, ending in (("timeout", "time.sleep(15)"), ("exit", "sys.exit(0)")):
                with self.subTest(name=name):
                    result = self.attempt(
                        root / name, [sys.executable, "-c", setup + ending], root, timeout_s=1
                    )
                    self.assertFalse(result["completed"])
                    self.assertTrue(cast(Record, result["cleanup"])["group_gone"])
                    self.assertIn(
                        "SIGKILL", cast(list[str], cast(Record, result["cleanup"])["signals"])
                    )
                    with self.assertRaises(ProcessLookupError):
                        os.killpg(cast(int, result["pid"]), 0)

    def test_matrix_exact_crossproduct_legacy_argv_and_actual_inventories(self) -> None:
        factory = cast(Callable[..., tuple[ArmView, ...]], self.script["experiment_arms"])
        controls, matrix = factory(matrix=False), factory(matrix=True)
        self.assertEqual([a.argv for a in controls], [(), ("--quant-bits", "8")])
        self.assertEqual(tuple(controls), tuple(matrix[:2]))
        self.assertEqual(
            [(a.backbone_bits, a.depth_bits) for a in matrix],
            [(None, None), (8, 8), (None, 8), (8, None)],
        )
        self.assertEqual(len({a.name for a in matrix}), 4)
        settings: Record = {
            "backbone_quantization": {"inventory": "backbone"},
            "depth_quantization": {"inventory": "depth"},
            "codec_dtype": "float32",
        }
        for arm in matrix:
            actual = arm.settings(settings)
            self.assertEqual(
                actual["backbone_quantization"],
                settings["backbone_quantization"] if arm.backbone_bits else None,
            )
            self.assertEqual(
                actual["depth_quantization"],
                settings["depth_quantization"] if arm.depth_bits else None,
            )
            self.assertEqual(actual["codec_dtype"], "float32")
        self.assertEqual(
            matrix[2].argv, ("--backbone-quant-bits", "none", "--depth-quant-bits", "8")
        )
        self.assertEqual(
            matrix[3].argv, ("--backbone-quant-bits", "8", "--depth-quant-bits", "none")
        )

    def test_four_arm_full_pcm_ids_and_72_asr_joins(self) -> None:
        factory = cast(Callable[..., tuple[ArmView, ...]], self.script["experiment_arms"])
        names = tuple(a.name for a in factory(matrix=True))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seen: set[str] = set()
            reports: list[Path] = []
            groups: list[Record] = []
            cases: list[Record] = []
            last: tuple[Record, Record, Path, Record] | None = None
            for arm_index, name in enumerate(names):
                arm = root / name
                arm.mkdir()
                report, identity, cases, settings = self.fixture(arm)
                ordered = [
                    cast(Record, row["result"]) for row in cast(list[Record], report["warmups"])
                ] + cast(list[Record], report["samples"])
                for i, sample in enumerate(ordered):
                    cast(Record, sample["producer"])["request_id"] = (
                        f"portable-{arm_index * 21 + i:032x}"
                    )
                self.validate(report, identity, cases, arm, settings=settings, seen=seen)
                last = (report, identity, arm, settings)
                path = arm / "report.json"
                path.write_text(json.dumps(report), encoding="utf-8")
                reports.append(path)
                groups.append(
                    {
                        "benchmark": str(path),
                        "samples": [
                            {
                                "prompt": c["text"],
                                "seed": c["seed"],
                                "transcript": "Same words",
                                "word_errors": 0,
                                "reference_words": 2,
                            }
                            for c in cases
                        ],
                    }
                )
            self.assertEqual(len(seen), 84)
            assert last is not None
            report, identity, arm, settings = last
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                self.validate(report, identity, cases, arm, settings=settings, seen=seen)
            asr: Record = {"reports": groups, "quality_acceptance": False, "resident_screen": None}
            result = self.join(asr, reports, cases, arm_names=names)
            self.assertEqual(len(result), 72)
            self.assertEqual([result[i * 18]["arm"] for i in range(4)], list(names))
            for bad_names in (names[:3], (*names[:2], names[3], names[2]), (names[0],) * 4):
                with self.assertRaises(ValueError):
                    self.join(asr, reports, cases, arm_names=bad_names)
            for bad_groups, bad_paths in (
                (groups[::-1], reports),
                (groups[:3], reports),
                (groups, reports[:2] + reports[:2]),
                (groups[::-1], reports[::-1]),
            ):
                with self.assertRaises(ValueError):
                    self.join({**asr, "reports": bad_groups}, bad_paths, cases, arm_names=names)

    def test_middle_matrix_failure_preserves_controls_and_stops_later_work(self) -> None:
        loaded = self.script["main"]
        assert isinstance(loaded, FunctionType)
        namespace = cast(Record, loaded.__globals__)
        main = cast(Callable[[], int], loaded)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, cases, _ = self.fixture(root)
            calls: list[str] = []

            def attempt(path: Path, command: list[str], repository: Path, *, label: str) -> Record:
                self.assertEqual(path.name, label)
                calls.append(label)
                return {
                    "label": label,
                    "completed": len(calls) < 3,
                    "exit_code": 0 if len(calls) < 3 else 1,
                    "stdout_sha256": "fixture",
                }

            def case_stub(*args: object) -> list[Record]:
                return cases

            def bound_stub(*args: object) -> Record:
                return {
                    "effective_settings": {"backbone_quantization": {}, "depth_quantization": {}}
                }

            def identity_stub(*args: object) -> Record:
                return {}

            def validate_stub(*args: object, **kwargs: object) -> Record:
                return {"timed": [], "warmups": []}

            with (
                patch.dict(
                    namespace,
                    {
                        "build_cases": case_stub,
                        "bound": bound_stub,
                        "identity": identity_stub,
                        "run_attempt": attempt,
                        "validate_probe": validate_stub,
                    },
                ),
                patch.object(
                    sys,
                    "argv",
                    ["compare", "--output-dir", str(root / "output"), "--run", "--matrix"],
                ),
            ):
                self.assertEqual(main(), 1)
            retained = cast(Record, json.loads((root / "output/comparison.json").read_bytes()))
            self.assertEqual(calls, ["bf16", "int8", "bf16-backbone-int8-depth"])
            self.assertEqual(len(cast(list[Record], retained["validated_probes"])), 2)
            self.assertEqual(len(cast(list[Record], retained["attempts"])), 3)
            self.assertNotIn("asr_attempt", retained)
            self.assertFalse(retained["completed"])


if __name__ == "__main__":
    unittest.main()
