"""Hash-bound T-016 diagnostics on untouched full clips; no Fast acceptance."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import io
import json
import re
import sys
import time
import wave
from collections.abc import Awaitable, Callable
from contextlib import aclosing, redirect_stdout
from dataclasses import replace
from pathlib import Path
from typing import Protocol, Self, cast

from simo.breeze import health
from simo.breeze_benchmark import (
    _completed_metrics,  # noqa: PLC2701 - shared internal proof validator
)
from simo.config import RuntimeConfig
from simo.inference import BreezeHTTPSynthesizer
from simo.model_proof import resample_pcm_s16le

Record = dict[str, object]
ASR_SHA = "30016a1e4a7d1d08c2e4145614329c9185fe830a961b979e22138f707793ae34"
AUDIT_SHA = "a171c67256c999bdffb9390c4dcb96d7a762c1659944491583ded18638190b0e"
DIAGNOSTIC_SHA = "8e814b068692d8077b40b547b7f3c2101eacea30efe44e0f221627f34c839bdb"
QUALITY_RUNTIME = "7d52e5a4dfa21507711928e32a26a758ecca1fb93871e8c9afefedd6dc05c96b"
QUALITY_ENDPOINT = "http://127.0.0.1:7860/v1/audio/speech"
EXPECTED_FLAGS = {
    ("warm-companion", 5, 29),
    ("warm-companion", 5, 42),
    ("warm-companion", 9, 29),
    ("bright-guide", 5, 17),
    ("bright-guide", 6, 29),
    ("bright-guide", 9, 42),
    ("grounded-mentor", 5, 17),
}
METHODS = ("stream-local", "stream-original-attention", "offline-same-array", "offline-file")


class Array(Protocol):
    shape: tuple[int, ...]
    dtype: object

    def __len__(self) -> int: ...


class Token(Protocol):
    text: str
    start: float
    duration: float
    confidence: float


class Result(Protocol):
    text: str
    tokens: list[Token]


class Preprocessor(Protocol):
    sample_rate: int
    hop_length: int


class EncoderConfig(Protocol):
    subsampling_factor: int


class Stream(Protocol):
    result: Result
    finalized_tokens: list[Token]
    draft_tokens: list[Token]
    audio_buffer: Array
    mel_buffer: Array

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None: ...
    def add_audio(self, audio: Array) -> None: ...


class Model(Protocol):
    preprocessor_config: Preprocessor
    encoder_config: EncoderConfig

    def transcribe_stream(self, *, keep_original_attention: bool = False) -> Stream: ...
    def generate(self, mel: Array) -> list[Result]: ...
    def transcribe(self, path: str, *, dtype: object, chunk_duration: None) -> Result: ...


class Mlx(Protocol):
    float32: object

    def array(self, value: object) -> Array: ...


class Parakeet(Protocol):
    def from_pretrained(self, path: str) -> Model: ...


class Audio(Protocol):
    def get_logmel(self, samples: Array, config: Preprocessor) -> Array: ...


def obj(value: object) -> Record:
    if not isinstance(value, dict):
        raise TypeError("Expected JSON object")
    return cast(Record, value)


def rows(value: object) -> list[Record]:
    if not isinstance(value, list):
        raise TypeError("Expected JSON object list")
    return [obj(item) for item in cast(list[object], value)]


def number(value: object) -> int:
    if type(value) is not int:
        raise TypeError("Expected integer")
    return value


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_bound(path: Path, digest: str) -> Record:
    payload = path.read_bytes()
    if sha(payload) != digest:
        raise ValueError(f"Artifact changed: {path}")
    return obj(cast(object, json.loads(payload)))


def word_errors(expected: str, actual: str) -> tuple[int, int]:
    left = cast(list[str], re.findall(r"[a-z0-9]+", expected.lower()))
    right = cast(list[str], re.findall(r"[a-z0-9]+", actual.lower()))
    previous = list(range(len(right) + 1))
    for row, word in enumerate(left, 1):
        current = [row]
        for column, heard in enumerate(right, 1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (word != heard))
            )
        previous = current
    return previous[-1], len(left)


def wav_bytes(path: Path) -> tuple[bytes, bytes]:
    raw = path.read_bytes()
    with wave.open(io.BytesIO(raw), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
            raise ValueError("Expected original mono24k PCM16 WAV")
        frames = audio.getnframes()
        if not 0 < frames <= 120 * 24000:
            raise ValueError("Invalid full-clip frame count")
        pcm = audio.readframes(frames)
    if len(pcm) != frames * 2:
        raise ValueError("Truncated full-clip PCM")
    return raw, pcm


def clip_id(key: tuple[str, int, int]) -> str:
    return f"{key[0]}-p{key[1] + 1}-s{key[2]}"


def build_manifest(
    asr_path: Path, audit_path: Path, *, asr_sha: str = ASR_SHA, audit_sha: str = AUDIT_SHA
) -> Record:
    asr, audit = read_bound(asr_path, asr_sha), read_bound(audit_path, audit_sha)
    if audit.get("completed") is not True or asr.get("quality_acceptance") is not False:
        raise ValueError("Expected complete audited cohorts, not accepted quality")
    asr_rows = rows(asr["reports"])
    asr_reports = {str(Path(str(row["benchmark"])).resolve()): row for row in asr_rows}
    if len(asr_reports) != len(asr_rows) or len(asr_reports) != 5:
        raise ValueError("Expected five distinct ASR cohorts")
    cases: dict[tuple[str, int, int], Record] = {}
    flags: list[Record] = []
    selected: set[tuple[str, int, int]] = set()
    report_identities: list[Record] = []
    canonical_manifest: Record | None = None
    for cohort in rows(audit["cohorts"]):
        if cohort["condition"] != "control":
            continue
        path = Path(str(cohort["path"])).resolve()
        report = read_bound(path, str(cohort["sha256"]))
        if report.get("completed") is not True or "failure" in report:
            raise ValueError("Cannot select from incomplete or failed benchmark")
        current_manifest = obj(report["manifest"])
        if canonical_manifest is None:
            canonical_manifest = current_manifest
        elif current_manifest != canonical_manifest:
            raise ValueError("Mixed runtime/source/settings manifests")
        if len(rows(report["samples"])) != report["timed_case_count"]:
            raise ValueError("Incomplete scheduled cohort")
        instruction = "default" if cohort["cohort"] in ("short", "long") else cohort["cohort"]
        if report["instruction_id"] != instruction:
            raise ValueError("Incorrect cohort instruction")
        screened = asr_reports.pop(str(path))
        report_identities.append({"path": str(path), "sha256": cohort["sha256"]})
        for sample, artifact, transcript in zip(
            rows(report["samples"]),
            rows(report["audio_artifacts"]),
            rows(screened["samples"]),
            strict=True,
        ):
            if any(sample[key] != transcript[key] for key in ("prompt", "seed")):
                raise ValueError("ASR case differs from benchmark")
            prompt, text = str(sample["prompt"]), str(transcript["transcript"])
            errors, words = word_errors(prompt, text)
            if (errors, words) != (transcript["word_errors"], transcript["reference_words"]):
                raise ValueError("ASR word-error counts changed")
            key = (str(sample["instruction_id"]), number(sample["index"]), number(sample["seed"]))
            if errors:
                segmentation = re.sub(r"[^a-z0-9]", "", prompt.lower()) == re.sub(
                    r"[^a-z0-9]", "", text.lower()
                )
                flags.append(
                    {
                        "suite": report["suite"],
                        "key": list(key),
                        "original_asr": transcript,
                        "segmentation_candidate": segmentation,
                    }
                )
                if not segmentation:
                    selected.add(key)
            if report["suite"] == "short":
                if key in cases:
                    raise ValueError("Duplicate diagnostic case")
                cases[key] = {
                    "sample": sample,
                    "artifact": artifact,
                    "asr": transcript,
                    "benchmark": str(path),
                    "instruction": report["instruction"],
                }
    if asr_reports:
        raise ValueError("Unmatched ASR cohorts")
    if selected != EXPECTED_FLAGS:
        raise ValueError("Flagged cases differ from the reviewed seven-case boundary")
    keys = sorted(EXPECTED_FLAGS | {("default", index, seed) for _, index, seed in EXPECTED_FLAGS})
    clips: list[Record] = []
    for key in keys:
        row = cases[key]
        sample, artifact = obj(row["sample"]), obj(row["artifact"])
        path = Path(str(artifact["path"])).resolve()
        raw, pcm = wav_bytes(path)
        if sha(pcm) != artifact["pcm_sha256"] or sha(pcm) != sample["pcm_sha256"]:
            raise ValueError("PCM identity differs from original benchmark")
        if len(pcm) != number(sample["frames"]) * 2:
            raise ValueError("PCM frame total differs")
        clips.append(
            {
                "id": clip_id(key),
                "key": list(key),
                "role": "flagged" if key in EXPECTED_FLAGS else "instruction-counterpart",
                "path": str(path),
                "wav_sha256": sha(raw),
                "pcm_sha256": sha(pcm),
                "frames": len(pcm) // 2,
                "audio_s": len(pcm) / 48000,
                "sample": sample,
                "instruction": row["instruction"],
                "original_asr": row["asr"],
                "benchmark": row["benchmark"],
            }
        )
    return {
        "schema_version": 1,
        "asr_source": {"path": str(asr_path.resolve()), "sha256": asr_sha},
        "audit_source": {"path": str(audit_path.resolve()), "sha256": audit_sha},
        "benchmark_reports": report_identities,
        "tts_manifest": canonical_manifest,
        "original_asr_model": asr["asr_model"],
        "original_asr_revision": asr["asr_revision"],
        "all_original_flags": flags,
        "clips": clips,
        "pairs": [
            {"flagged": clip_id(key), "counterpart": clip_id(("default", key[1], key[2]))}
            for key in sorted(EXPECTED_FLAGS)
        ],
        "quality_acceptance": False,
        "limits": "All7 non-segmentation flags plus6 default counterparts; original full WAVs unchanged. Different instructions are context, not matched reference-model controls. Segmentation candidates remain retained; no perceptual adjudication.",
    }


def checked_clip(clip: Record) -> bytes:
    raw, pcm = wav_bytes(Path(str(clip["path"])))
    if sha(raw) != clip["wav_sha256"] or sha(pcm) != clip["pcm_sha256"]:
        raise ValueError("Diagnostic full clip changed")
    return pcm


def result_record(result: Result, expected: str) -> Record:
    text = result.text.strip()
    errors, words = word_errors(expected, text)
    return {
        "text": text,
        "word_errors": errors,
        "reference_words": words,
        "tokens": [
            {
                "text": token.text,
                "start": token.start,
                "duration": token.duration,
                "confidence": token.confidence,
            }
            for token in result.tokens
        ],
    }


def transcribe_clip(model: Model, clip: Record, method: str) -> Record:
    import numpy as np

    mx = cast(Mlx, importlib.import_module("mlx.core"))
    audio = cast(Audio, importlib.import_module("parakeet_mlx.audio"))
    pcm = checked_clip(clip)
    aligned = resample_pcm_s16le(pcm, 24000, 16000)
    samples = mx.array(np.frombuffer(aligned, dtype="<i2").astype(np.float32) / 32768.0)
    mel = audio.get_logmel(samples, model.preprocessor_config)
    expected = str(obj(clip["sample"])["prompt"])
    metadata: Record = {
        "method": method,
        "resampled_pcm_sha256": sha(aligned),
        "input_samples": len(samples),
        "effective_input_dtype": str(samples.dtype),
        "full_mel_shape": mel.shape,
        "subsampling_factor": model.encoder_config.subsampling_factor,
    }
    started = time.perf_counter()
    if method.startswith("stream-"):
        with model.transcribe_stream(
            keep_original_attention=method == "stream-original-attention"
        ) as stream:
            stream.add_audio(samples)
            result = result_record(stream.result, expected)
            metadata.update(
                finalized_tokens=len(stream.finalized_tokens),
                draft_tokens=len(stream.draft_tokens),
                remaining_audio_samples=len(stream.audio_buffer),
                remaining_mel_frames=stream.mel_buffer.shape[1],
            )
        metadata["after_context"] = result_record(stream.result, expected)
    elif method == "offline-same-array":
        result = result_record(model.generate(mel)[0], expected)
    elif method == "offline-file":
        result = result_record(
            model.transcribe(str(clip["path"]), dtype=mx.float32, chunk_duration=None), expected
        )
        metadata["resampled_pcm_sha256"] = None
        metadata["preprocessing"] = (
            "Parakeet FFmpeg file resampling; not the Simo linear array; mel/input metadata above describes the comparison array, not FFmpeg output"
        )
    else:
        raise ValueError("Unknown diagnostic method")
    return {**metadata, **result, "wall_s": time.perf_counter() - started}


def run_diagnostic(
    manifest: Record, output: Path, transcriber: Callable[[Record, str], Record], identity: Record
) -> Record:
    result_rows: list[Record] = []
    report: Record = {
        "schema_version": 1,
        "manifest": manifest,
        "diagnostic_identity": identity,
        "methods": METHODS,
        "clips": result_rows,
        "completed": False,
        "quality_acceptance": False,
        "started_unix_ns": time.time_ns(),
        "limits": "Recognition-path sensitivity only; no TTS/ASR weights or live adapter changed. Every method/result retained, no voting/best-result selection or perceptual acceptance. Confidence is model output, not proof.",
    }
    with output.open("x", encoding="utf-8") as file:
        try:
            for clip in rows(manifest["clips"]):
                results: list[Record] = []
                row: Record = {"id": clip["id"], "results": results}
                result_rows.append(row)
                for method in METHODS:
                    row["pending_method"] = method
                    checked_clip(clip)
                    results.append(transcriber(clip, method))
                del row["pending_method"]
            report["completed"] = True
        except Exception as error:
            report["failure"] = {"type": type(error).__name__, "message": str(error)}
        finally:
            report["finished_unix_ns"] = time.time_ns()
            json.dump(report, file, indent=2)
    return report


def check_quality_health(current: Record) -> None:
    expected: Record = {
        "runtime_fingerprint": QUALITY_RUNTIME,
        "status": "ready",
        "performance_mode": "quality",
        "quantization": "none",
        "cfg_policy": "request",
    }
    if current.get("busy") is not False or any(current.get(k) != v for k, v in expected.items()):
        raise ValueError("Expected unchanged idle Quality runtime")


async def generate_quality_control(clip: Record, config: RuntimeConfig) -> tuple[Record, bytes]:
    config = replace(config, tts_endpoint=QUALITY_ENDPOINT)
    sample = obj(clip["sample"])
    request: Record = {
        "text": sample["prompt"],
        "instruction": clip["instruction"],
        "seed": number(sample["seed"]),
        "cfg_scale": 4.0,
    }
    result: Record = {"request": request, "endpoint": QUALITY_ENDPOINT, "completed": False}
    pcm = bytearray()
    synth = BreezeHTTPSynthesizer(
        QUALITY_ENDPOINT,
        instruction=str(request["instruction"]),
        cfg_scale=4.0,
        seed=number(request["seed"]),
        expected_runtime=QUALITY_RUNTIME,
        require_request_id=True,
    )
    started = time.perf_counter()
    try:
        before = await asyncio.to_thread(health, config)
        result["health_before"] = before
        check_quality_health(before)
        async with asyncio.timeout(180), aclosing(synth.synthesize(str(request["text"]))) as source:
            async for chunk in source:
                if chunk.sample_rate != 24000 or len(pcm) + len(chunk.pcm_s16le) > 120 * 48000:
                    raise ValueError("Invalid or oversized reference PCM")
                pcm.extend(chunk.pcm_s16le)
        observations: list[Record] = []
        result["completion_observations"] = observations
        for attempt in range(5):
            after = await asyncio.to_thread(health, config)
            observations.append(after)
            if after.get("runtime_fingerprint") != QUALITY_RUNTIME or after.get("busy") is not True:
                break
            if attempt < 4:
                await asyncio.sleep(0.05)
        after = observations[-1]
        result["health_after"] = after
        check_quality_health(after)
        request_id = synth.response_request_id
        if request_id is None:
            raise ValueError("Reference response has no request ID")
        metrics = _completed_metrics(after, QUALITY_RUNTIME, request_id)
        if len(pcm) != number(metrics["audio_samples"]) * 2:
            raise ValueError("Reference PCM differs from completed service totals")
        if obj(before.get("last_request")).get("request_id") == request_id:
            raise ValueError("Stale reference request ID")
        result.update(completed=True, request_id=request_id, metrics=metrics)
    except (Exception, asyncio.CancelledError) as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
    result["response_request_id"] = synth.response_request_id
    result["wall_s"] = time.perf_counter() - started
    return result, bytes(pcm)


async def run_quality_controls(
    manifest: Record,
    directory: Path,
    generator: Callable[[Record], Awaitable[tuple[Record, bytes]]],
) -> Record:
    selected = [clip for clip in rows(manifest["clips"]) if clip["role"] == "flagged"]
    if (
        len(selected) != 7
        or {tuple(cast(list[object], c["key"])) for c in selected} != EXPECTED_FLAGS
    ):
        raise ValueError("Expected exactly the seven original flagged cases")
    controls: list[Record] = []
    generated: list[Record] = []
    repository = Path(__file__).resolve().parents[1]
    source_paths = [
        Path(__file__).resolve(),
        repository / "python/simo/inference.py",
        repository / "python/simo/breeze.py",
        repository / "python/simo/breeze_benchmark.py",
        repository / "uv.lock",
    ]
    source_hashes = {str(path): sha(path.read_bytes()) for path in source_paths}
    report: Record = {
        "schema_version": 1,
        "source_manifest": manifest,
        "controls": generated,
        "clips": controls,
        "completed": False,
        "quality_acceptance": False,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "source_sha256": source_hashes,
        "started_unix_ns": time.time_ns(),
        "limits": "Exactly7 same-text/instruction/nominal-seed Quality controls; no warmups/retries, content-only diagnostic, not a latency benchmark or paired random stream. Backend/arithmetic/quantization differ together; not isolated quantization causality or perceptual acceptance.",
    }
    seen: set[str] = set()
    pending_pcm = b""
    with (directory / "controls.json").open("x", encoding="utf-8") as file:
        try:
            for clip in selected:
                for path in source_paths:
                    if sha(path.read_bytes()) != source_hashes[str(path)]:
                        raise ValueError("Control source changed during run")
                checked_clip(clip)
                report["pending_case"] = clip["id"]
                result, pcm = await generator(clip)
                pending_pcm = pcm
                result["candidate_id"] = clip["id"]
                result["pcm_sha256"] = sha(pcm)
                result["frames"] = len(pcm) // 2
                generated.append(result)
                if result.get("completed") is not True:
                    raise RuntimeError("Quality control failed; prior/partial output retained")
                request_id = str(result["request_id"])
                if request_id in seen or re.fullmatch(r"api-[0-9a-f]{32}", request_id) is None:
                    raise ValueError("Duplicate or invalid reference request ID")
                seen.add(request_id)
                if not pcm or len(pcm) % 2 or len(pcm) > 120 * 48000:
                    raise ValueError("Invalid full reference PCM")
                path = directory / f"{clip['id']}-quality.wav"
                with path.open("xb") as raw, wave.open(raw, "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(24000)
                    audio.writeframes(pcm)
                controls.append(
                    {
                        "id": f"{clip['id']}-quality",
                        "candidate_id": clip["id"],
                        "path": str(path.resolve()),
                        "wav_sha256": sha(path.read_bytes()),
                        "pcm_sha256": sha(pcm),
                        "frames": len(pcm) // 2,
                        "audio_s": len(pcm) / 48000,
                        "instruction": clip["instruction"],
                        "sample": {
                            key: obj(clip["sample"])[key]
                            for key in ("prompt", "seed", "index", "instruction_id")
                        },
                        "request_id": request_id,
                    }
                )
                pending_pcm = b""
            del report["pending_case"]
            report["completed"] = True
        except (Exception, asyncio.CancelledError) as error:
            report["failure"] = {"type": type(error).__name__, "message": str(error)}
            if pending_pcm:
                partial = directory / f"{report['pending_case']}.partial.pcm"
                with partial.open("xb") as raw:
                    raw.write(pending_pcm)
                generated[-1]["partial_path"] = str(partial.resolve())
        finally:
            report["finished_unix_ns"] = time.time_ns()
            json.dump(report, file, indent=2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--diagnose", action="store_true")
    mode.add_argument("--quality-controls", action="store_true")
    args = parser.parse_args()
    config = RuntimeConfig.from_environment()
    base = config.repository / ".artifacts/breeze-performance"
    manifest = build_manifest(
        base / "mlx-https-v1-control-asr.json", base / "mlx-https-v1-full-audit.json"
    )
    output = cast(Path, args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "manifest.json").open("x", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    if not cast(bool, args.diagnose) and not cast(bool, args.quality_controls):
        print(
            json.dumps(
                {"manifest": str(output / "manifest.json"), "clips": len(rows(manifest["clips"]))}
            )
        )
        return 0
    try:
        diagnostic_manifest = manifest
        if cast(bool, args.quality_controls):
            previous = read_bound(
                base / "mlx-quality-triage-v1-diagnostic/diagnostic.json", DIAGNOSTIC_SHA
            )
            if previous.get("completed") is not True or previous.get("manifest") != manifest:
                raise ValueError("Original diagnostic does not match unchanged source clips")
            controls = asyncio.run(
                run_quality_controls(
                    manifest, output, lambda clip: generate_quality_control(clip, config)
                )
            )
            if controls.get("completed") is not True:
                print(json.dumps({"completed": False, "report": str(output / "controls.json")}))
                return 1
            diagnostic_manifest = {
                "schema_version": 1,
                "clips": controls["clips"],
                "controls_source": {
                    "path": str((output / "controls.json").resolve()),
                    "sha256": sha((output / "controls.json").read_bytes()),
                },
                "quality_acceptance": False,
                "limits": controls["limits"],
            }
        marker_path = config.stt.local_path / ".simo-model.json"
        marker = obj(cast(object, json.loads(marker_path.read_bytes())))
        if (
            marker["model_id"] != manifest["original_asr_model"]
            or marker["revision"] != manifest["original_asr_revision"]
        ):
            raise ValueError("Diagnostic recognizer model differs from original screen")
        with redirect_stdout(sys.stderr):
            package = cast(Parakeet, importlib.import_module("parakeet_mlx"))
            model = package.from_pretrained(str(config.stt.local_path))
            if model.preprocessor_config.sample_rate != 16000:
                raise ValueError("Expected unchanged16k recognizer")
            paths = [
                Path(__file__),
                config.repository / "python/simo/inference.py",
                config.repository / "python/simo/model_proof.py",
                config.repository / "scripts/evaluate_breeze_audio.py",
                config.repository / "python/simo/breeze.py",
                config.repository / "python/simo/breeze_benchmark.py",
                config.repository / "uv.lock",
                marker_path,
            ]
            paths.extend(
                Path(str(importlib.import_module(name).__file__))
                for name in (
                    "parakeet_mlx.parakeet",
                    "parakeet_mlx.audio",
                    "parakeet_mlx.alignment",
                )
            )
            identity: Record = {
                "model": marker,
                "weight_digest_verified": False,
                "sources": {str(path.resolve()): sha(path.read_bytes()) for path in paths},
                "dependencies": {
                    name: importlib.metadata.version(name)
                    for name in ("parakeet-mlx", "mlx", "mlx-metal", "numpy")
                },
            }
            report = run_diagnostic(
                diagnostic_manifest,
                output / "diagnostic.json",
                lambda clip, method: transcribe_clip(model, clip, method),
                identity,
            )
    except Exception as error:
        with (output / "initialization-failure.json").open("x", encoding="utf-8") as file:
            json.dump(
                {
                    "completed": False,
                    "quality_acceptance": False,
                    "manifest": manifest,
                    "failure": {"type": type(error).__name__, "message": str(error)},
                },
                file,
                indent=2,
            )
        raise
    print(json.dumps({"completed": report["completed"], "report": str(output / "diagnostic.json")}))
    return 0 if report["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
