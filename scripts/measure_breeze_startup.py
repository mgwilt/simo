"""Measure process-cold Breeze startup on an already-running Mac; never OS-cold."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess  # noqa: S404 - fixed owned argv, no shell
import threading
import time
import wave
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

from simo.breeze_benchmark import _completed_metrics, _request_id  # noqa: PLC2701
from simo.breeze_listening import encoded, obj, read_json, sha

from scripts.compare_breeze_quantization import cleanup_group

Record = dict[str, object]
REFERENCE_SHA = "532418812a3ece708486085e434253aea98b428ec1324a90132664167f1439ad"
PORT = 7862
MAX_PCM = 120 * 48000
RECIPE_FIELDS = (
    "model_revision",
    "model_digest",
    "dependencies",
    "device",
    "dtype",
    "engine",
    "attention",
    "quantization",
    "depth_cache",
    "performance_mode",
    "experimental_recipe",
    "runtime_settings",
    "sampling",
    "cfg_policy",
    "codec_chunk_frames",
    "release_accepted",
    "sample_rate",
    "metal_artifacts",
)


def source_identity(repository: Path) -> tuple[str, dict[str, str]]:
    fork = repository / "vendor/breeze-tts"
    digest = hashlib.sha256()
    sources: dict[str, str] = {}
    for directory in (fork / "breeze_infer", fork / "models"):
        for path in sorted(directory.rglob("*.py")):
            raw = path.read_bytes()
            digest.update(str(path.relative_to(fork)).encode())
            digest.update(raw)
            sources[str(path)] = sha(raw)
    launcher = repository / "services/breeze/serve.py"
    raw = launcher.read_bytes()
    digest.update(raw)
    sources[str(launcher)] = sha(raw)
    return digest.hexdigest(), sources


def validate_ready(current: Record, reference: Record, source_digest: str) -> str:
    fingerprint = current.get("runtime_fingerprint")
    if (
        current.get("status") != "ready"
        or current.get("busy") is not False
        or current.get("source_digest") != source_digest
        or not isinstance(fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise ValueError("Startup runtime readiness/source mismatch")
    if any(current.get(key) != reference[key] for key in RECIPE_FIELDS):
        raise ValueError("Startup recipe/model/dependency/kernel changed")
    return fingerprint


def assert_free_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", PORT))


def assert_owned_listener(process: subprocess.Popen[bytes]) -> list[int]:
    if not hasattr(os, "getpgid"):
        raise RuntimeError("Startup process ownership requires POSIX")
    getpgid = os.getpgid
    if process.poll() is not None:
        raise RuntimeError("Owned startup process exited")
    result = subprocess.run(  # noqa: S603 - fixed read-only local socket query
        ["/usr/sbin/lsof", "-nP", "-t", f"-iTCP:{PORT}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    values = result.stdout.splitlines()
    if any(not value.isascii() or not value.isdecimal() for value in values):
        raise RuntimeError("Invalid startup listener PID response")
    pids = [int(value) for value in values]
    if result.returncode != 0 or not pids or any(getpgid(pid) != process.pid for pid in pids):
        raise RuntimeError("Startup listener is not owned by this process group")
    return pids


@contextmanager
def bounded_connection(deadline: float) -> Generator[http.client.HTTPConnection]:
    """Interrupt even trickling headers and Connection:close bodies at the deadline."""
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise TimeoutError("Startup HTTP deadline exceeded")
    connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=min(2, remaining))
    timer: threading.Timer | None = None
    transport: socket.socket | None = None
    expired = threading.Event()
    try:
        connection.connect()
        transport = connection.sock
        if transport is None:
            raise ConnectionError("Startup HTTP socket missing")
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("Startup HTTP deadline exceeded")
        transport.settimeout(remaining)

        def abort() -> None:
            expired.set()
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Already closed; retained transport cannot target a reused descriptor.

        timer = threading.Timer(remaining, abort)
        timer.daemon = True
        timer.start()
        yield connection
        if expired.is_set() or time.perf_counter() >= deadline:
            raise TimeoutError("Startup HTTP deadline exceeded")
    finally:
        if timer is not None:
            timer.cancel()
            timer.join(timeout=1)
        if transport is not None:
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()


def health(*, deadline: float | None = None) -> Record:
    health_deadline = min(time.perf_counter() + 1, deadline or float("inf"))
    with bounded_connection(health_deadline) as connection:
        connection.request("GET", "/health")
        response = connection.getresponse()
        if response.status != 200:
            raise ConnectionError(f"Startup health status {response.status}")
        raw = response.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError("Oversized startup health response")
        return obj(cast(object, json.loads(raw)))


def measure_request(
    directory: Path,
    fingerprint: str,
    instruction: str,
    launched: float,
    seen: set[str],
    *,
    ready_at: float,
    ordinal: int,
) -> Record:
    directory.mkdir(exist_ok=False)
    started = time.perf_counter()
    record: Record = {
        "started_unix_ns": time.time_ns(),
        "launch_to_request_s": started - launched,
        "verified_ready_to_request_s": started - ready_at,
        "ordinal": ordinal,
        "kind": "first" if ordinal == 0 else "warm",
        "completed": False,
        "prompt": "Good morning. I am ready when you are.",
        "seed": 17,
        "cfg_scale": 4,
        "instruction": instruction,
    }
    audio = bytearray()
    arrivals: list[Record] = []
    record["arrivals"] = arrivals
    try:
        body = urlencode(
            {"text": record["prompt"], "instruction": instruction, "cfg_scale": "4", "seed": "17"}
        ).encode()
        with bounded_connection(started + 30) as connection:
            connection.request(
                "POST",
                "/v1/audio/speech",
                body,
                {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Breeze-Runtime": fingerprint,
                },
            )
            response = connection.getresponse()
            record["status"] = response.status
            record["headers"] = dict(response.getheaders())
            if (
                response.status != 200
                or response.getheader("X-Breeze-Runtime") != fingerprint
                or response.getheader("X-Sample-Rate") != "24000"
                or response.getheader("X-Sample-Format") != "s16le"
            ):
                raise ValueError("Invalid startup PCM metadata")
            request_id = _request_id(response.getheader("X-Breeze-Request-ID"))
            record["request_id"] = request_id
            if request_id in seen:
                raise ValueError("Repeated startup request ID")
            seen.add(request_id)
            with (directory / "received.pcm").open("xb") as retained:
                while True:
                    if time.perf_counter() >= started + 30:
                        raise TimeoutError("Startup speech deadline exceeded")
                    chunk = response.read1(8192)
                    now = time.perf_counter()
                    if not chunk:
                        break
                    if len(audio) + len(chunk) > MAX_PCM or len(arrivals) >= 10000:
                        raise ValueError("Startup audio exceeds bounds")
                    if not audio:
                        record["request_to_first_byte_s"] = now - started
                    if len(audio) < 2 <= len(audio) + len(chunk):
                        record["request_to_first_pcm_s"] = now - started
                        record["launch_to_first_pcm_s"] = now - launched
                    retained.write(chunk)
                    audio.extend(chunk)
                    arrivals.append({"seconds": now - started, "bytes": len(audio)})
        record["request_to_eof_s"] = time.perf_counter() - started
        if not audio or len(audio) % 2:
            raise ValueError("Incomplete startup PCM")
        last: Record | None = None
        deadline = time.perf_counter() + 5
        while time.perf_counter() < deadline:
            current = health(deadline=deadline)
            try:
                last = _completed_metrics(current, fingerprint, request_id)
                break
            except ValueError:
                time.sleep(0.05)
        if last is None or last["audio_samples"] != len(audio) // 2:
            raise ValueError("Startup PCM lacks matching completed producer")
        record["producer"] = last
        record["pcm_sha256"] = sha(bytes(audio))
        record["audio_samples"] = len(audio) // 2
        record["audio_s"] = len(audio) / 48000
        with wave.open(str(directory / "complete.wav"), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(audio)
        record["completed"] = True
        return record
    except BaseException as error:
        record["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        record["received_bytes"] = len(audio)
        record["finished_unix_ns"] = time.time_ns()
        (directory / "report.json").write_bytes(encoded(record))


def run_cycle(
    directory: Path, repository: Path, reference: Record, source_digest: str, seen: set[str]
) -> Record:
    directory.mkdir(exist_ok=False)
    record: Record = {"completed": False, "requests": [], "attempted_requests": []}
    process: subprocess.Popen[bytes] | None = None
    command = [
        shutil.which("uv") or "uv",
        "run",
        "--offline",
        "--project",
        "services/breeze",
        "--frozen",
        "--with",
        "mlx==0.32.0",
        "python",
        "services/breeze/serve.py",
        ".models/Breeze-TTS-2",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--device",
        "mps",
        "--experimental-recipe",
        "mlx-int8-v1",
    ]
    record["command"] = command
    environment = {
        **os.environ,
        "PYTHONPATH": str(repository / "vendor/breeze-tts"),
        "UV_CACHE_DIR": "/private/tmp/simo-uv-cache",
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }
    try:
        assert_free_port()
        with (
            (directory / "stdout.log").open("xb") as output,
            (directory / "stderr.log").open("xb") as errors,
        ):
            record["launch_unix_ns"] = time.time_ns()
            launched = time.perf_counter()
            process = subprocess.Popen(  # noqa: S603 - fixed owned argv
                command,
                cwd=repository,
                env=environment,
                stdout=output,
                stderr=errors,
                start_new_session=True,
            )
            record["pid"] = process.pid
            deadline = launched + 90
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Startup service exited before readiness")
                if time.perf_counter() >= deadline:
                    raise TimeoutError("Startup readiness deadline exceeded")
                try:
                    current = health(deadline=deadline)
                    break
                except (OSError, http.client.HTTPException):
                    time.sleep(0.1)
            record["launch_to_health_ready_s"] = time.perf_counter() - launched
            fingerprint = validate_ready(current, obj(reference["runtime"]), source_digest)
            record["listener_pids"] = assert_owned_listener(process)
            if current.get("last_request"):
                raise ValueError("Startup service already had a request")
            record["ready"] = current
            ready_at = time.perf_counter()
            record["launch_to_ready_s"] = ready_at - launched
            record["ready_observation_poll_s"] = 0.1
            print(
                json.dumps(
                    {
                        "cycle": directory.name,
                        "launch_to_ready_s": ready_at - launched,
                        "runtime_fingerprint": fingerprint,
                    }
                ),
                flush=True,
            )
            for index in range(4):
                assert_owned_listener(process)
                if source_identity(repository)[0] != source_digest:
                    raise ValueError("Source changed during startup experiment")
                request_path = directory / f"request-{index}"
                cast(list[str], record["attempted_requests"]).append(str(request_path))
                request = measure_request(
                    request_path,
                    fingerprint,
                    str(reference["instruction"]),
                    launched,
                    seen,
                    ready_at=ready_at,
                    ordinal=index,
                )
                cast(list[Record], record["requests"]).append(request)
            if (
                len({request["pcm_sha256"] for request in cast(list[Record], record["requests"])})
                != 1
            ):
                raise ValueError("Identical startup requests produced different PCM")
            record["completed"] = True
    except BaseException as error:
        record["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        if process is not None:
            try:
                record["cleanup"] = cleanup_group(process)
                record["exit_code"] = process.returncode
            except BaseException as error:
                record["completed"] = False
                record["cleanup_failure"] = str(error)
                (directory / "report.json").write_bytes(encoded(record))
                raise
        record["finished_unix_ns"] = time.time_ns()
        (directory / "report.json").write_bytes(encoded(record))
    return record


def run(output: Path, repository: Path, *, cycles: int = 3) -> Record:
    if not 1 <= cycles <= 3:
        raise ValueError("Startup cycles must be between one and three")
    reference_path = (
        repository / ".artifacts/breeze-performance/listening-v2/fresh-smoke/report.json"
    )
    reference, reference_sha = read_json(reference_path)
    if reference_sha != REFERENCE_SHA or reference.get("completed") is not True:
        raise ValueError("Startup reference changed or is incomplete")
    digest, sources = source_identity(repository)
    harness_sources = {
        str(repository / name): sha((repository / name).read_bytes())
        for name in (
            "scripts/measure_breeze_startup.py",
            "scripts/compare_breeze_quantization.py",
            "python/simo/breeze_listening.py",
            "python/simo/breeze_benchmark.py",
        )
    }
    output.mkdir(exist_ok=False)
    report: Record = {
        "schema": "simo.breeze.process-startup.v1",
        "completed": False,
        "reference_sha256": reference_sha,
        "source_digest": digest,
        "sources": sources,
        "harness_sources": harness_sources,
        "probe_sha256": sha(Path(__file__).read_bytes()),
        "started_unix_ns": time.time_ns(),
        "port": PORT,
        "cycles": [],
        "attempted_cycles": [],
        "schedule": {
            "process_cold_cycles": cycles,
            "first_requests_per_cycle": 1,
            "warm_requests_per_cycle": 3,
        },
        "limits": "Process-cold only, already-running machine with existing model/filesystem caches; not OS/disk-cold, resident-release, acoustic or p95 evidence. Live inference/UI services untouched. No recipe promotion.",
    }
    seen: set[str] = set()
    try:
        for index in range(cycles):
            cycle_path = output / f"cycle-{index}"
            cast(list[str], report["attempted_cycles"]).append(str(cycle_path))
            cycle = run_cycle(cycle_path, repository, reference, digest, seen)
            cast(list[Record], report["cycles"]).append(cycle)
        all_requests = [
            request
            for cycle in cast(list[Record], report["cycles"])
            for request in cast(list[Record], cycle["requests"])
        ]
        report["pcm_equal_across_cycles"] = (
            len({request["pcm_sha256"] for request in all_requests}) == 1
        )
        report["historical_pcm_equal"] = all(
            request["pcm_sha256"] == obj(cast(list[object], reference["samples"])[0])["pcm_sha256"]
            for request in all_requests
        )
        if (
            source_identity(repository)[0] != digest
            or any(
                sha(Path(path).read_bytes()) != digest for path, digest in harness_sources.items()
            )
            or not report["pcm_equal_across_cycles"]
        ):
            raise ValueError("Startup source or PCM drift")
        report["completed"] = True
    except BaseException as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        report["finished_unix_ns"] = time.time_ns()
        (output / "report.json").write_bytes(encoded(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=3)
    args = parser.parse_args()
    result = run(
        cast(Path, args.output_dir).absolute(),
        Path(__file__).resolve().parents[1],
        cycles=cast(int, args.cycles),
    )
    print(
        json.dumps(
            {
                "completed": result["completed"],
                "report": str(cast(Path, args.output_dir) / "report.json"),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
