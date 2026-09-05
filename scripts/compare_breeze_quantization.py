"""Fixed MLX precision experiments; retain all failures, never release Fast."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import os
import re
import shutil
import signal
import subprocess  # noqa: S404 - bounded owned subprocesses, no shell commands
import sys
import time
import wave
from array import array
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from simo.config import RuntimeConfig

Record = dict[str, object]
PAIRS = (
    ("bright-guide", 5),
    ("bright-guide", 6),
    ("bright-guide", 9),
    ("grounded-mentor", 5),
    ("warm-companion", 5),
    ("warm-companion", 9),
)
SEEDS = (17, 29, 42)
FLAG_ORDINALS = {0, 4, 8, 9, 13, 14, 16}
AUDIT_SHA = "a171c67256c999bdffb9390c4dcb96d7a762c1659944491583ded18638190b0e"
ASR_SHA = "30016a1e4a7d1d08c2e4145614329c9185fe830a961b979e22138f707793ae34"
SETTINGS_SHA = "8b71c4ef330460a234518e6ee5684b1c7c05fb13136911b138e5af9f1d5cd0ad"
MODEL_SHA = "aebc74eac29ac4729fdf0f8c4d3870c1d8cf4efb72e4e24e9316accaa386462d"
DEPENDENCIES = {
    "torch": "2.9.1",
    "transformers": "4.57.3",
    "qwen-tts": "0.1.1",
    "mlx": "0.32.0",
    "mlx-metal": "0.32.0",
}


@dataclass(frozen=True)
class Arm:
    name: str
    backbone_bits: int | None
    depth_bits: int | None
    argv: tuple[str, ...]

    def settings(self, int8: Record) -> Record:
        return {
            **int8,
            "backbone_quantization": int8["backbone_quantization"] if self.backbone_bits else None,
            "depth_quantization": int8["depth_quantization"] if self.depth_bits else None,
        }


def experiment_arms(*, matrix: bool) -> tuple[Arm, ...]:
    controls = (Arm("bf16", None, None, ()), Arm("int8", 8, 8, ("--quant-bits", "8")))
    return controls + (
        (
            Arm(
                "bf16-backbone-int8-depth",
                None,
                8,
                ("--backbone-quant-bits", "none", "--depth-quant-bits", "8"),
            ),
            Arm(
                "int8-backbone-bf16-depth",
                8,
                None,
                ("--backbone-quant-bits", "8", "--depth-quant-bits", "none"),
            ),
        )
        if matrix
        else ()
    )


def obj(value: object) -> Record:
    if not isinstance(value, dict):
        raise TypeError("Expected JSON object")
    return cast(Record, value)


def rows(value: object) -> list[Record]:
    if not isinstance(value, list):
        raise TypeError("Expected object list")
    return [obj(row) for row in cast(list[object], value)]


def integer(value: object) -> int:
    if type(value) is not int:
        raise TypeError("Expected integer, not boolean")
    return value


def real(value: object) -> float:
    if type(value) not in (int, float):
        raise TypeError("Expected finite numeric value")
    result = float(cast(int | float, value))
    if not math.isfinite(result) or result < 0:
        raise ValueError("Invalid nonnegative numeric value")
    return result


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def same(left: object, right: object) -> bool:
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def bound(path: Path, expected: str) -> Record:
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f"Changed artifact: {path}")
    return obj(cast(object, json.loads(raw)))


def save(path: Path, data: Record | list[Record]) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(data, file, indent=2, allow_nan=False)


def executable(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise RuntimeError(f"Required local executable is missing: {name}")
    return found


def pcm_file(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    with wave.open(io.BytesIO(raw), "rb") as audio:
        count = audio.getnframes()
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
            raise ValueError("Expected untouched mono24k PCM16")
        if not 0 < count <= 120 * 24000:
            raise ValueError("Invalid full clip size")
        pcm = audio.readframes(count)
    if len(pcm) != count * 2 or sha(pcm) != expected:
        raise ValueError("Truncated or changed full clip")
    return pcm


def build_cases(audit: Record, asr: Record) -> list[Record]:
    screened = {str(Path(str(r["benchmark"])).resolve()): r for r in rows(asr["reports"])}
    cohorts = {str(r["cohort"]): r for r in rows(audit["cohorts"]) if r["condition"] == "control"}
    selected: list[Record] = []
    for voice, index in PAIRS:
        ref = cohorts[voice]
        path = Path(str(ref["path"])).resolve()
        report = bound(path, str(ref["sha256"]))
        if (
            report.get("completed") is not True
            or "failure" in report
            or report["instruction_id"] != voice
        ):
            raise ValueError("Invalid historical cohort")
        samples, artifacts = rows(report["samples"]), rows(report["audio_artifacts"])
        transcripts = rows(screened[str(path)]["samples"])
        if (len(samples), len(artifacts), len(transcripts)) != (30, 30, 30):
            raise ValueError("Incomplete historical schedule")
        for offset, seed in enumerate(SEEDS):
            ordinal = index * 3 + offset
            sample, artifact, transcript = (
                samples[ordinal],
                artifacts[ordinal],
                transcripts[ordinal],
            )
            if (sample["index"], sample["seed"], sample["instruction_id"]) != (index, seed, voice):
                raise ValueError("Historical sample identity mismatch")
            if (transcript["prompt"], transcript["seed"]) != (sample["prompt"], seed):
                raise ValueError("Historical ASR ordinal mismatch")
            pcm = pcm_file(Path(str(artifact["path"])), str(artifact["pcm_sha256"]))
            if len(pcm) != integer(sample["frames"]) * 2 or sha(pcm) != sample["pcm_sha256"]:
                raise ValueError("Historical sample/audio mismatch")
            selected.append(
                {
                    "ordinal": len(selected),
                    "voice": voice,
                    "original_index": index,
                    "seed": seed,
                    "text": sample["prompt"],
                    "instruction": report["instruction"],
                    "historical_report": {
                        "path": str(path),
                        "sha256": ref["sha256"],
                        "ordinal": ordinal,
                    },
                    "historical_artifact": {
                        **artifact,
                        "wav_sha256": digest(Path(str(artifact["path"]))),
                    },
                    "historical_asr": transcript,
                }
            )
    if {
        i for i, c in enumerate(selected) if integer(obj(c["historical_asr"])["word_errors"])
    } != FLAG_ORDINALS:
        raise ValueError("Original seven flags changed")
    return selected


def identity(repository: Path) -> Record:
    fork = repository / "vendor/breeze-tts"
    files = [
        p
        for directory in (fork / "models", fork / "breeze_infer")
        for p in sorted(directory.rglob("*.py"))
    ]
    source_hash = hashlib.sha256()
    for path in files:
        source_hash.update(str(path.relative_to(fork)).encode())
        source_hash.update(path.read_bytes())
    paths = files + [
        repository / name
        for name in (
            "scripts/compare_breeze_quantization.py",
            "scripts/evaluate_breeze_audio.py",
            "python/simo/inference.py",
            "python/simo/model_proof.py",
            "python/simo/config.py",
            "uv.lock",
            "services/breeze/uv.lock",
        )
    ]
    model = repository / ".models/Breeze-TTS-2"
    model_hash = hashlib.sha256()
    for path in sorted(model.rglob("*")):
        if path.is_file() and path.suffix in (".json", ".safetensors", ".model", ".txt"):
            model_hash.update(str(path.relative_to(model)).encode())
            with path.open("rb") as file:
                while chunk := file.read(1024 * 1024):
                    model_hash.update(chunk)
    if model_hash.hexdigest() != MODEL_SHA:
        raise ValueError("Original model package content changed")
    distribution = importlib.metadata.distribution("mlx-metal")
    kernels = {
        str(p): digest(Path(str(distribution.locate_file(p))))
        for p in distribution.files or []
        if str(p).endswith(("mlx.metallib", "libmlx.dylib"))
    }
    if len(kernels) != 2:
        raise ValueError("Missing pinned Metal artifacts")
    config = RuntimeConfig.from_environment()
    if config.stt.model_id != "mlx-community/parakeet-tdt-0.6b-v3":
        raise ValueError("Expected unchanged local recognizer")
    original_asr = bound(
        repository / ".artifacts/breeze-performance/mlx-https-v1-control-asr.json", ASR_SHA
    )
    asr_marker_path = config.stt.local_path / ".simo-model.json"
    asr_marker_raw = asr_marker_path.read_bytes()
    asr_marker = obj(cast(object, json.loads(asr_marker_raw)))
    expected_asr = [original_asr["asr_model"], original_asr["asr_revision"]]
    if not same([config.stt.model_id, config.stt.revision], expected_asr) or not same(
        [asr_marker.get("model_id"), asr_marker.get("revision")], expected_asr
    ):
        raise ValueError("Local recognizer marker/config differ from the historical screen")
    asr_distribution = importlib.metadata.distribution("parakeet-mlx")
    asr_sources = {
        str(p): digest(Path(str(asr_distribution.locate_file(p))))
        for p in asr_distribution.files or []
        if str(p).endswith(".py")
    }
    revision = subprocess.check_output(  # noqa: S603 - fixed read-only Git argv
        [executable("git"), "-C", str(fork), "rev-parse", "HEAD"], text=True
    ).strip()
    return {
        "source": {"revision": revision, "source_digest": source_hash.hexdigest()},
        "source_sha256": {str(path): digest(path) for path in paths},
        "model_sha256": model_hash.hexdigest(),
        "model_marker": obj(cast(object, json.loads((model / ".simo-model.json").read_bytes()))),
        "metal_artifacts": kernels,
        "asr": {
            "model_id": config.stt.model_id,
            "revision": config.stt.revision,
            "model_marker_sha256": sha(asr_marker_raw),
            "model_marker": asr_marker,
            "weight_digest_verified": False,
            "sources": asr_sources,
            "dependencies": {
                name: importlib.metadata.version(name)
                for name in ("parakeet-mlx", "mlx", "mlx-metal", "numpy")
            },
        },
    }


def group_exists(pgid: int) -> bool:
    if not hasattr(os, "killpg"):
        raise RuntimeError("POSIX process groups are required")
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS can transiently report EPERM while a signalled group exits.
        # Uncertainty counts as still present, never as successful cleanup.
        return True
    return True


def cleanup_group(process: subprocess.Popen[bytes], *, grace_s: float = 3) -> Record:
    """Reap the leader and independently remove its entire freshly owned session group."""
    if not hasattr(os, "killpg") or not hasattr(signal, "SIGKILL"):
        raise RuntimeError("POSIX process-group cleanup is required")
    sent: list[str] = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        # poll() reaps the leader; its exit does not establish descendant cleanup.
        process.poll()
        if not group_exists(process.pid):
            process.wait(timeout=grace_s)
            return {"group_gone": True, "signals": sent}
        try:
            os.killpg(process.pid, sig)
            sent.append(sig.name)
        except (ProcessLookupError, PermissionError):
            pass
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            process.poll()
            if not group_exists(process.pid):
                process.wait(timeout=grace_s)
                return {"group_gone": True, "signals": sent}
            time.sleep(0.02)
    raise RuntimeError(f"Cleanup uncertain for owned process group {process.pid}")


def run_attempt(
    directory: Path,
    command: list[str],
    repository: Path,
    *,
    timeout_s: float = 900,
    label: str | None = None,
) -> Record:
    if not hasattr(os, "killpg") or not hasattr(signal, "SIGKILL"):
        raise RuntimeError("This isolated probe requires POSIX process-group cleanup")
    directory.mkdir(exist_ok=False)
    report: Record = {"command": command, "started_unix_ns": time.time_ns(), "completed": False}
    if label is not None:
        report["label"] = label
    environment = {
        **os.environ,
        "PYTHONPATH": str(repository / "vendor/breeze-tts"),
        "UV_CACHE_DIR": "/private/tmp/simo-uv-cache",
        "TIKTOKEN_CACHE_DIR": str(repository / ".cache/tiktoken"),
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }
    process: subprocess.Popen[bytes] | None = None
    with (
        (directory / "report.json").open("xb") as output,
        (directory / "stderr.log").open("xb") as errors,
    ):
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed argv from this script; no shell
                command,
                cwd=repository,
                env=environment,
                stdout=output,
                stderr=errors,
                start_new_session=True,
            )
            report["pid"] = process.pid
            report["exit_code"] = process.wait(timeout=timeout_s)
            if group_exists(process.pid):
                raise RuntimeError("Launcher exited with a surviving owned process group")
            report["completed"] = report["exit_code"] == 0
        except BaseException as error:
            report["failure"] = {"type": type(error).__name__, "message": str(error)}
            if process is not None:
                try:
                    report["cleanup"] = cleanup_group(process)
                except BaseException as cleanup_error:
                    report["cleanup_failure"] = {
                        "type": type(cleanup_error).__name__,
                        "message": str(cleanup_error),
                    }
                report["exit_code"] = process.returncode
        finally:
            report["finished_unix_ns"] = time.time_ns()
            report["stdout_sha256"] = digest(directory / "report.json")
            report["stderr_sha256"] = digest(directory / "stderr.log")
            save(directory / "attempt.json", report)
    return report


def validate_sample(
    sample: Record, artifact: Record, case: Record, path: Path, seen: set[str]
) -> Record:
    if not same(
        [sample.get("prompt"), sample.get("instruction"), sample.get("seed")],
        [case["text"], case["instruction"], case["seed"]],
    ):
        raise ValueError("Probe case order/instruction/seed changed")
    producer = obj(sample["producer"])
    if sample.get("failure") is not None or any(
        producer.get(k) is not v
        for k, v in (("completed", True), ("eos_reached", True), ("cancelled", False))
    ):
        raise ValueError("Incomplete probe speech")
    request_id = str(producer["request_id"])
    if re.fullmatch(r"portable-[0-9a-f]{32}", request_id) is None or request_id in seen:
        raise ValueError("Duplicate/invalid producer ID")
    seen.add(request_id)
    actual = Path(str(artifact["path"])).resolve()
    if actual != path.resolve():
        raise ValueError("Probe WAV escaped exact expected destination")
    pcm = pcm_file(actual, str(artifact["pcm_sha256"]))
    count, frames = integer(producer["audio_samples"]), integer(producer["codec_frames"])
    if (
        count != len(pcm) // 2
        or count != frames * 1920
        or integer(artifact["samples"]) != count
        or integer(artifact["sample_rate"]) != 24000
    ):
        raise ValueError("Probe codec/sample/WAV totals differ")
    arrivals = rows(sample["arrivals"])
    times = [real(row["seconds"]) for row in arrivals]
    if len(arrivals) != frames or any(integer(row["samples"]) != 1920 for row in arrivals):
        raise ValueError("Probe arrival/sample totals differ")
    if times != sorted(times) or not times or times[0] <= 0:
        raise ValueError("Invalid arrival order")
    duration = count / 24000
    total = real(sample["total_s"])
    steady = (times[-1] - times[0]) / (duration - 0.08) if frames > 1 else None
    if total < times[-1] or real(sample["preparation_s"]) > times[0]:
        raise ValueError("Invalid request stage timing")
    if any(
        not math.isclose(real(got), expected, rel_tol=1e-10, abs_tol=1e-10)
        for got, expected in (
            (sample["first_pcm_s"], times[0]),
            (sample["audio_s"], duration),
            (producer["audio_s"], duration),
            (sample["total_rtf"], total / duration),
        )
    ):
        raise ValueError("Probe duration/RTF/first-PCM mismatch")
    if steady is None or not math.isclose(real(sample["steady_rtf"]), steady, rel_tol=1e-10):
        raise ValueError("Probe steady-state RTF mismatch")
    if integer(sample["ended_unix_ns"]) <= integer(sample["started_unix_ns"]):
        raise ValueError("Invalid request wall clock")
    return {
        "path": str(actual),
        "wav_sha256": digest(actual),
        "pcm_sha256": sha(pcm),
        "samples": count,
        "request_id": request_id,
        "steady_rtf": steady,
        "first_pcm_s": times[0],
    }


def validate_probe(
    report: Record,
    expected: Record,
    cases: list[Record],
    directory: Path,
    *,
    settings: Record,
    seen: set[str],
) -> Record:
    for field in ("source", "model_marker", "metal_artifacts", "corpus"):
        if not same(report[field], expected[field]):
            raise ValueError(f"Probe {field} identity changed")
    if (
        report.get("compiled") is not True
        or report.get("quality_acceptance") is not False
        or report.get("lifecycle") != []
    ):
        raise ValueError("Unexpected probe mode or release claim")
    if not same(report["dependencies"], DEPENDENCIES) or not same(
        report["effective_settings"], settings
    ):
        raise ValueError("Probe dependencies/effective recipe changed")
    samples, artifacts, warmups = (
        rows(report["samples"]),
        rows(report["audio_artifacts"]),
        rows(report["warmups"]),
    )
    if (len(cases), len(samples), len(artifacts), len(warmups)) != (18, 18, 18, 3):
        raise ValueError("Incomplete18+3 probe schedule")
    checked_warmups = [
        validate_sample(
            obj(row["result"]), obj(row["artifact"]), cases[0], directory / f"warmup-{i}.wav", seen
        )
        for i, row in enumerate(warmups)
    ]
    checked = [
        validate_sample(sample, artifact, case, directory / f"sample-{i // 3}-{i % 3}.wav", seen)
        for i, (sample, artifact, case) in enumerate(zip(samples, artifacts, cases, strict=True))
    ]
    ordered_samples = [obj(row["result"]) for row in warmups] + samples
    previous_end = integer(report["started_unix_ns"])
    for sample in ordered_samples:
        if integer(sample["started_unix_ns"]) < previous_end:
            raise ValueError("Overlapping or reversed request wall clocks")
        previous_end = integer(sample["ended_unix_ns"])
    if previous_end > integer(report["ended_unix_ns"]):
        raise ValueError("Request outside probe wall clocks")
    return {
        "warmups": checked_warmups,
        "timed": checked,
        "steady_rtf_p95": sorted(real(r["steady_rtf"]) for r in checked)[math.ceil(18 * 0.95) - 1],
    }


def compare_pcm(probe: Record, case: Record) -> Record:
    historical = obj(case["historical_artifact"])
    before = pcm_file(Path(str(historical["path"])), str(historical["pcm_sha256"]))
    after = pcm_file(Path(str(probe["path"])), str(probe["pcm_sha256"]))
    result: Record = {
        "ordinal": case["ordinal"],
        "same_samples": len(before) == len(after),
        "conversion_compatible": False,
    }
    if len(before) == len(after):
        left, right = array("h", before), array("h", after)
        if sys.byteorder != "little":
            left.byteswap()
            right.byteswap()
        maximum = changed = 0
        away = endpoints = True
        for original, rounded in zip(left, right, strict=True):
            difference = rounded - original
            maximum = max(maximum, abs(difference))
            changed += difference != 0
            away = away and (
                difference == 0 or (abs(rounded) >= abs(original) and original * rounded >= 0)
            )
            endpoints = endpoints and min(original, rounded) >= -32767
        result.update(
            maximum_lsb=maximum,
            away_from_zero=away,
            changed_samples=changed,
            conversion_compatible=maximum <= 1 and away and endpoints,
        )
    return result


def join_asr(
    asr: Record,
    reports: list[Path],
    cases: list[Record],
    *,
    arm_names: tuple[str, ...] = ("bf16", "int8"),
) -> list[Record]:
    groups = rows(asr["reports"])
    allowed_names = tuple(tuple(a.name for a in experiment_arms(matrix=m)) for m in (False, True))
    if arm_names not in allowed_names:
        raise ValueError("Unexpected ASR arm names/order")
    if (
        len(groups) != len(arm_names)
        or len(reports) != len(arm_names)
        or len({p.resolve() for p in reports}) != len(arm_names)
        or asr.get("quality_acceptance") is not False
        or asr.get("resident_screen") is not None
    ):
        raise ValueError("Unexpected ASR mode/report count")
    result: list[Record] = []
    for name, group, report_path in zip(arm_names, groups, reports, strict=True):
        path_label = (
            report_path.parent.name if report_path.name == "report.json" else report_path.stem
        )
        if path_label != name:
            raise ValueError("ASR path label differs from the fixed arm")
        if Path(str(group["benchmark"])).resolve() != report_path.resolve():
            raise ValueError("ASR report order mismatch")
        transcripts = rows(group["samples"])
        if len(transcripts) != 18:
            raise ValueError("Incomplete ASR schedule")
        for ordinal, (transcript, case) in enumerate(zip(transcripts, cases, strict=True)):
            if not same([transcript["prompt"], transcript["seed"]], [case["text"], case["seed"]]):
                raise ValueError("ASR case ordinal differs")
            reference = cast(list[str], re.findall(r"[a-z0-9]+", str(case["text"]).lower()))
            heard = cast(list[str], re.findall(r"[a-z0-9]+", str(transcript["transcript"]).lower()))
            previous = list(range(len(heard) + 1))
            for index, word in enumerate(reference, 1):
                current = [index]
                for column, token in enumerate(heard, 1):
                    current.append(
                        min(
                            current[-1] + 1,
                            previous[column] + 1,
                            previous[column - 1] + (word != token),
                        )
                    )
                previous = current
            if (integer(transcript["word_errors"]), integer(transcript["reference_words"])) != (
                previous[-1],
                len(reference),
            ):
                raise ValueError("ASR word-error count mismatch")
            result.append(
                {
                    "arm": name,
                    "report_sha256": digest(report_path),
                    "ordinal": ordinal,
                    "voice": case["voice"],
                    "original_index": case["original_index"],
                    "transcript": transcript,
                    "historical_asr": case["historical_asr"],
                }
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--matrix", action="store_true", help="Add both independent component precision arms"
    )
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    directory = cast(Path, args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    base = repository / ".artifacts/breeze-performance"
    arms = experiment_arms(matrix=cast(bool, args.matrix))
    summary: Record = {
        "completed": False,
        "quality_acceptance": False,
        "arms": [asdict(arm) for arm in arms],
        "input_sha256": {"audit": AUDIT_SHA, "asr": ASR_SHA, "settings": SETTINGS_SHA},
        "started_unix_ns": time.time_ns(),
        "limits": "Fixed matched producer subset, not release corpus, causal acoustic/perceptual acceptance or physical playback. All outputs/failures retained. No original weight contents or live serving recipe/default change; isolated selector source is identified separately.",
    }
    try:
        cases = build_cases(
            bound(base / "mlx-https-v1-full-audit.json", AUDIT_SHA),
            bound(base / "mlx-https-v1-control-asr.json", ASR_SHA),
        )
        corpus = [
            {"text": cases[i]["text"], "instruction": cases[i]["instruction"]}
            for i in range(0, 18, 3)
        ]
        corpus_path = directory / "corpus.json"
        save(corpus_path, corpus)
        initial = identity(repository)
        expected = {**initial, "corpus": {"path": str(corpus_path), "sha256": digest(corpus_path)}}
        summary.update(cases=cases, identity=expected)
        save(directory / "manifest.json", summary)
        if not cast(bool, args.run):
            print(json.dumps({"prepared": True, "directory": str(directory)}))
            return 0
        original = bound(base / "mlx-speech-int8-3-v2.json", SETTINGS_SHA)
        int8_settings = obj(original["effective_settings"])
        summary["settings_source_sha256"] = SETTINGS_SHA
        attempts: list[Record] = []
        summary["attempts"] = attempts
        checked: list[Record] = []
        summary["validated_probes"] = checked
        report_paths: list[Path] = []
        seen: set[str] = set()
        for spec in arms:
            if (
                not same(identity(repository), initial)
                or digest(corpus_path) != obj(expected["corpus"])["sha256"]
            ):
                raise ValueError("Source/model/corpus identity drift")
            arm = directory / spec.name
            command = [
                executable("uv"),
                "run",
                "--offline",
                "--project",
                "services/breeze",
                "--frozen",
                "--with",
                "mlx==0.32.0",
                "--with",
                "pytest==8.4.2",
                "python",
                "-m",
                "breeze_infer.probe_mlx_speech",
                "--model-path",
                ".models/Breeze-TTS-2",
                "--corpus",
                str(corpus_path),
                "--warmups",
                "3",
                "--seeds",
                "17",
                "29",
                "42",
                "--audio-dir",
                str(arm / "audio"),
            ]
            command += list(spec.argv)
            print(f"Running {spec.name}:18 timed cases and3 warmups", flush=True)
            attempt = run_attempt(arm, command, repository, label=spec.name)
            attempts.append(attempt)
            if attempt.get("completed") is not True:
                raise RuntimeError(f"{spec.name} process failed; partial attempt retained")
            report_path = arm / "report.json"
            report = bound(report_path, str(attempt["stdout_sha256"]))
            checked.append(
                {
                    "arm": asdict(spec),
                    **validate_probe(
                        report,
                        expected,
                        cases,
                        arm / "audio",
                        settings=spec.settings(int8_settings),
                        seen=seen,
                    ),
                }
            )
            report_paths.append(report_path)
        if (
            not same(identity(repository), initial)
            or digest(corpus_path) != obj(expected["corpus"])["sha256"]
        ):
            raise ValueError("Final source/model/corpus identity changed")
        summary["int8_api_pcm"] = [
            compare_pcm(clip, case)
            for clip, case in zip(
                rows(next(row for row in checked if obj(row["arm"])["name"] == "int8")["timed"]),
                cases,
                strict=True,
            )
        ]
        asr_attempt = run_attempt(
            directory / "asr",
            [
                executable("uv"),
                "run",
                "--offline",
                "--frozen",
                "python",
                "scripts/evaluate_breeze_audio.py",
                *(str(p) for p in report_paths),
            ],
            repository,
            label="asr",
        )
        summary["asr_attempt"] = asr_attempt
        if asr_attempt.get("completed") is not True:
            raise RuntimeError("ASR failed; retained attempt is not acceptance")
        asr = bound(directory / "asr/report.json", str(asr_attempt["stdout_sha256"]))
        for report_path, attempt in zip(report_paths, attempts, strict=True):
            bound(report_path, str(attempt["stdout_sha256"]))
        for arm in checked:
            for clip in rows(arm["timed"]) + rows(arm["warmups"]):
                if digest(Path(str(clip["path"]))) != clip["wav_sha256"]:
                    raise ValueError("ASR input WAV changed")
        if (
            not same(identity(repository), initial)
            or digest(corpus_path) != obj(expected["corpus"])["sha256"]
        ):
            raise ValueError("Source/model/corpus identity changed during ASR")
        recognizer = obj(initial["asr"])
        if (asr.get("asr_model"), asr.get("asr_revision")) != (
            recognizer["model_id"],
            recognizer["revision"],
        ):
            raise ValueError("ASR recognizer identity changed")
        summary["asr_rows"] = join_asr(
            asr, report_paths, cases, arm_names=tuple(a.name for a in arms)
        )
        summary["completed"] = True
    except BaseException as error:
        summary["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        summary["finished_unix_ns"] = time.time_ns()
        save(directory / "comparison.json", summary)
    print(
        json.dumps(
            {"completed": summary["completed"], "report": str(directory / "comparison.json")}
        )
    )
    return 0 if summary["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
