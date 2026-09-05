from __future__ import annotations

import asyncio
import hashlib
import json
import runpy
import tempfile
import unittest
import wave
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import FunctionType
from typing import cast
from unittest.mock import patch

from simo.breeze import BENCHMARK_PROMPTS, LONG_BENCHMARK_PROMPTS
from simo.config import RuntimeConfig
from simo.inference import AudioChunk

Record = dict[str, object]


class BreezeQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = cast(
            Record,
            runpy.run_path(
                str(Path(__file__).resolve().parents[2] / "scripts/triage_breeze_audio.py")
            ),
        )
        cls.build = staticmethod(cast(Callable[..., Record], cls.script["build_manifest"]))
        cls.run_diag = staticmethod(cast(Callable[..., Record], cls.script["run_diagnostic"]))
        cls.flags = cast(set[tuple[str, int, int]], cls.script["EXPECTED_FLAGS"])
        cls.run_controls = staticmethod(
            cast(
                Callable[..., Coroutine[object, object, Record]], cls.script["run_quality_controls"]
            )
        )

    def fixture(self, root: Path) -> tuple[Path, Path]:
        asr_reports: list[Record] = []
        cohorts: list[Record] = []
        for name in ("short", "long", "warm-companion", "bright-guide", "grounded-mentor"):
            instruction = "default" if name in ("short", "long") else name
            suite = "long" if name == "long" else "short"
            prompts = LONG_BENCHMARK_PROMPTS if suite == "long" else BENCHMARK_PROMPTS
            samples: list[Record] = []
            artifacts: list[Record] = []
            transcripts: list[Record] = []
            for index, prompt in enumerate(prompts):
                for seed in (17, 29, 42):
                    audio_path = root / f"{name}-{index}-{seed}.wav"
                    pcm = b"\x01\x00" * 1920
                    with wave.open(str(audio_path), "wb") as output:
                        output.setnchannels(1)
                        output.setsampwidth(2)
                        output.setframerate(24000)
                        output.writeframes(pcm)
                    digest = hashlib.sha256(pcm).hexdigest()
                    samples.append(
                        {
                            "instruction_id": instruction,
                            "index": index,
                            "seed": seed,
                            "prompt": prompt,
                            "frames": 1920,
                            "pcm_sha256": digest,
                        }
                    )
                    artifacts.append({"path": str(audio_path), "pcm_sha256": digest})
                    transcript = prompt
                    if suite == "short" and (instruction, index, seed) in self.flags:
                        transcript = " ".join(prompt.split(" ")[1:])
                    elif suite == "long" and index == 0:
                        transcript = prompt.replace("tradeoffs", "trade offs")
                    errors = cast(Callable[[str, str], tuple[int, int]], self.script["word_errors"])
                    count, words = errors(prompt, transcript)
                    transcripts.append(
                        {
                            "prompt": prompt,
                            "seed": seed,
                            "transcript": transcript,
                            "word_errors": count,
                            "reference_words": words,
                        }
                    )
            report_path = root / f"{name}.json"
            report: Record = {
                "completed": True,
                "samples": samples,
                "audio_artifacts": artifacts,
                "instruction_id": instruction,
                "instruction": instruction,
                "suite": suite,
                "timed_case_count": len(samples),
                "manifest": {"runtime_fingerprint": "fixture-runtime"},
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")
            cohorts.append(
                {
                    "condition": "control",
                    "cohort": name,
                    "path": str(report_path),
                    "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                }
            )
            asr_reports.append({"benchmark": str(report_path), "samples": transcripts})
        asr_path, audit_path = root / "asr.json", root / "audit.json"
        asr_path.write_text(
            json.dumps(
                {
                    "quality_acceptance": False,
                    "reports": asr_reports,
                    "asr_model": "fixture",
                    "asr_revision": "fixture",
                }
            ),
            encoding="utf-8",
        )
        audit_path.write_text(json.dumps({"completed": True, "cohorts": cohorts}), encoding="utf-8")
        return asr_path, audit_path

    def manifest(self, asr: Path, audit: Path) -> Record:
        return self.build(
            asr,
            audit,
            asr_sha=hashlib.sha256(asr.read_bytes()).hexdigest(),
            audit_sha=hashlib.sha256(audit.read_bytes()).hexdigest(),
        )

    def test_all_flags_counterparts_pairs_and_segmentation_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.manifest(*self.fixture(root))
            clips = cast(list[Record], result["clips"])
            self.assertEqual(len(clips), 13)
            self.assertEqual(sum(clip["role"] == "flagged" for clip in clips), 7)
            self.assertEqual(len(cast(list[Record], result["pairs"])), 7)
            self.assertEqual(len(cast(list[Record], result["all_original_flags"])), 10)
            self.assertFalse(result["quality_acceptance"])
            self.assertIn("not matched reference-model", str(result["limits"]))
            self.assertEqual(result, json.loads(json.dumps(result)))

    def test_changed_source_digest_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            asr, audit = self.fixture(Path(directory))
            with self.assertRaisesRegex(ValueError, "Artifact changed"):
                self.build(asr, audit)

    def test_missing_or_changed_asr_case_rejected(self) -> None:
        for change in ("missing", "seed", "count", "cohort"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                asr, audit = self.fixture(Path(directory))
                data = cast(Record, json.loads(asr.read_text(encoding="utf-8")))
                reports = cast(list[Record], data["reports"])
                samples = cast(list[Record], reports[2]["samples"])
                if change == "missing":
                    samples.pop()
                elif change == "seed":
                    samples[0]["seed"] = 999
                elif change == "count":
                    samples[0]["word_errors"] = 99
                else:
                    reports.append(reports[0])
                asr.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.manifest(asr, audit)

    def test_changed_full_clip_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.manifest(*self.fixture(root))
            clip = cast(list[Record], result["clips"])[0]
            path = Path(str(clip["path"]))
            path.write_bytes(path.read_bytes()[:-2])
            checked = cast(Callable[[Record], bytes], self.script["checked_clip"])
            with self.assertRaisesRegex(ValueError, "Truncated"):
                checked(clip)

    def test_all_methods_or_failure_are_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.manifest(*self.fixture(root))
            calls: list[str] = []

            def transcribe(clip: Record, method: str) -> Record:
                calls.append(method)
                return {"method": method, "text": "fixture"}

            report = self.run_diag(manifest, root / "complete.json", transcribe, {})
            self.assertTrue(report["completed"])
            self.assertFalse(report["quality_acceptance"])
            self.assertEqual(len(calls), 52)
            calls.clear()

            def fail(clip: Record, method: str) -> Record:
                calls.append(method)
                if len(calls) == 3:
                    raise RuntimeError("fixture decode failure")
                return {"method": method}

            failed = self.run_diag(manifest, root / "failed.json", fail, {})
            self.assertFalse(failed["completed"])
            self.assertFalse(failed["quality_acceptance"])
            first = cast(list[Record], failed["clips"])[0]
            self.assertEqual(len(cast(list[Record], first["results"])), 2)
            self.assertEqual(first["pending_method"], "offline-same-array")
            self.assertEqual(cast(Record, failed["failure"])["message"], "fixture decode failure")

    def test_existing_output_fails_before_transcription(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.manifest(*self.fixture(root))
            output = root / "existing.json"
            output.write_text("preserved", encoding="utf-8")
            calls: list[str] = []

            def transcribe(clip: Record, method: str) -> Record:
                calls.append(method)
                return {}

            with self.assertRaises(FileExistsError):
                self.run_diag(manifest, output, transcribe, {})
            self.assertEqual(calls, [])
            self.assertEqual(output.read_text(encoding="utf-8"), "preserved")

    def test_exact_seven_controls_and_unchanged_pcm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.manifest(*self.fixture(root))
            calls: list[Record] = []
            pcm = b"\x02\x00" * 1920

            async def generate(clip: Record) -> tuple[Record, bytes]:
                calls.append(clip)
                return {"completed": True, "request_id": f"api-{len(calls):032x}"}, pcm

            report = asyncio.run(self.run_controls(manifest, root, generate))
            self.assertTrue(report["completed"])
            self.assertFalse(report["quality_acceptance"])
            self.assertEqual(len(calls), 7)
            self.assertTrue(all(clip["role"] == "flagged" for clip in calls))
            checked = cast(Callable[[Record], bytes], self.script["checked_clip"])
            for original, clip in zip(calls, cast(list[Record], report["clips"]), strict=True):
                self.assertEqual(clip["instruction"], original["instruction"])
                self.assertEqual(clip["candidate_id"], original["id"])
                self.assertEqual(checked(clip), pcm)
            with self.assertRaises(FileExistsError):
                asyncio.run(self.run_controls(manifest, root, generate))
            self.assertEqual(len(calls), 7)

    def test_control_partial_stops_without_next_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.manifest(*self.fixture(root))
            calls: list[Record] = []

            async def generate(clip: Record) -> tuple[Record, bytes]:
                calls.append(clip)
                return {"completed": False, "failure": {"message": "fixture"}}, b"\x02\x00"

            result = asyncio.run(self.run_controls(manifest, root, generate))
            self.assertFalse(result["completed"])
            self.assertFalse(result["quality_acceptance"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["clips"], [])
            partial = cast(list[Record], result["controls"])[0]
            self.assertEqual(Path(str(partial["partial_path"])).read_bytes(), b"\x02\x00")
            self.assertEqual(list(root.glob("*-quality.wav")), [])

    def check_quality_request_case(self, failure: str | None) -> None:
        loaded = self.script["generate_quality_control"]
        assert isinstance(loaded, FunctionType)
        namespace = cast(dict[str, object], loaded.__globals__)
        function = cast(
            Callable[[Record, RuntimeConfig], Coroutine[object, object, tuple[Record, bytes]]],
            loaded,
        )
        runtime = str(self.script["QUALITY_RUNTIME"])
        request_id = "api-" + "a" * 32
        clip: Record = {"sample": {"prompt": "Exact text", "seed": 29}, "instruction": "Full voice"}
        metrics: Record = {
            "request_id": request_id,
            "completed": True,
            "cancelled": False,
            "eos_reached": True,
            "audio_samples": 1920,
            "codec_frames": 1,
            "audio_s": 0.08,
        }
        config = RuntimeConfig.from_environment()
        calls: list[Record] = []
        closed: list[bool] = []
        health_calls: list[bool] = []

        def fake_health(config: RuntimeConfig) -> Record:
            health_calls.append(True)
            after = len(health_calls) > 1
            result: Record = {
                "runtime_fingerprint": runtime,
                "status": "ready",
                "busy": False,
                "performance_mode": "quality",
                "quantization": "none",
                "cfg_policy": "request",
                "last_request": dict(metrics) if after else {"request_id": "api-" + "b" * 32},
            }
            if failure == ("after" if after else "before"):
                result["runtime_fingerprint"] = "changed"
            if failure == "busy-once" and len(health_calls) == 2:
                result["busy"] = True
            if after and failure in ("stale", "eos", "count"):
                last = cast(Record, result["last_request"])
                if failure == "stale":
                    last["request_id"] = "api-" + "c" * 32
                if failure == "eos":
                    last["eos_reached"] = False
                if failure == "count":
                    last["audio_samples"] = 3840
            return result

        class FakeSynth:
            response_request_id = request_id

            def __init__(self, endpoint: str, **kwargs: object) -> None:
                calls.append({"endpoint": endpoint, **kwargs})

            async def synthesize(self, text: str):
                calls[-1]["text"] = text
                try:
                    if failure == "empty":
                        return
                    yield AudioChunk(
                        b"\x02\x00" * 1920 + (b"x" if failure == "odd" else b""), 24000
                    )
                    if failure == "stream":
                        raise RuntimeError("fixture stream error")
                    if failure == "stream-cancel":
                        raise asyncio.CancelledError("fixture cancelled")
                finally:
                    closed.append(True)

        with patch.dict(namespace, {"health": fake_health, "BreezeHTTPSynthesizer": FakeSynth}):
            result, pcm = asyncio.run(function(clip, config))
        self.assertEqual(result["completed"], failure in (None, "busy-once"))
        self.assertEqual(calls[0]["instruction"], "Full voice")
        self.assertEqual(calls[0]["seed"], 29)
        self.assertEqual(calls[0]["cfg_scale"], 4.0)
        self.assertEqual(calls[0]["expected_runtime"], runtime)
        self.assertTrue(calls[0]["require_request_id"])
        if failure == "before":
            self.assertNotIn("text", calls[0])
            self.assertEqual(closed, [])
        else:
            self.assertEqual(calls[0]["text"], "Exact text")
            self.assertEqual(closed, [True])
        if failure is None:
            self.assertEqual(pcm, b"\x02\x00" * 1920)
        if failure == "stream-cancel":
            self.assertEqual(pcm, b"\x02\x00" * 1920)
            self.assertEqual(result["response_request_id"], request_id)
            self.assertEqual(cast(Record, result["failure"])["type"], "CancelledError")

    def test_quality_request_identity_bounds_and_cleanup(self) -> None:
        for failure in (
            None,
            "before",
            "after",
            "stale",
            "eos",
            "count",
            "empty",
            "odd",
            "stream",
            "stream-cancel",
            "busy-once",
        ):
            with self.subTest(failure=failure):
                self.check_quality_request_case(failure)


if __name__ == "__main__":
    unittest.main()
