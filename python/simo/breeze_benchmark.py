"""Opt-in fixed-corpus HTTPS measurements, separate from normal voice requests."""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import wave
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import aclosing
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from starlette.types import Receive, Scope, Send

from simo.breeze import BENCHMARK_PROMPTS, LONG_BENCHMARK_PROMPTS, _percentile, health
from simo.config import RuntimeConfig
from simo.inference import BreezeHTTPSynthesizer
from simo.lan_site import VOICE_PREVIEW_PRESETS

SCHEMA = "simo.breeze.https-benchmark.v1"
MAX_PCM_BYTES = 120 * 48_000
POLICY = "mlx-stream-v1"


def _sha(payload: bytes | bytearray) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identity(payload: dict[str, object]) -> str:
    return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _object(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise TypeError("Expected a JSON object")
    return cast(dict[str, object], payload)


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _request_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"api-[0-9a-f]{32}", value) is None:
        raise ValueError("Invalid benchmark request ID")
    return value


def _completed_metrics(
    current: dict[str, object], runtime: str, request_id: str
) -> dict[str, object]:
    if current.get("runtime_fingerprint") != runtime or current.get("busy") is not False:
        raise ValueError("Benchmark runtime is busy or changed")
    last = _object(current.get("last_request"))
    if last.get("request_id") != request_id or any(
        last.get(key) is not value
        for key, value in (("completed", True), ("eos_reached", True), ("cancelled", False))
    ):
        raise ValueError("Matching completed benchmark request unavailable")
    samples, frames = last.get("audio_samples"), last.get("codec_frames")
    if type(samples) is not int or type(frames) is not int:
        raise TypeError("Invalid producer sample/frame totals")
    if not 0 < samples <= MAX_PCM_BYTES // 2 or frames <= 0 or samples != frames * 1920:
        raise ValueError("Inconsistent producer sample/frame totals")
    if last.get("audio_s") != samples / 24000:
        raise ValueError("Inconsistent producer audio duration")
    return last


class _BenchmarkResponse(Response):
    """Own pre-header pulling and disconnect cleanup on both ASGI 2.3 and 2.4."""

    def __init__(
        self,
        source: AsyncGenerator[bytes, None],
        synth: BreezeHTTPSynthesizer,
        release: Callable[[], None],
        headers: dict[str, str],
    ) -> None:
        super().__init__(media_type="audio/pcm", headers=headers)
        del self.headers["content-length"]
        self.source, self.synth, self.release = source, synth, release

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def stream() -> None:
            try:
                first = await anext(self.source)
                self.headers["X-Breeze-Request-ID"] = _request_id(self.synth.response_request_id)
            except Exception:
                await Response("Benchmark upstream failed before PCM", status_code=502)(
                    scope, receive, send
                )
                return
            await send({"type": "http.response.start", "status": 200, "headers": self.raw_headers})
            await send({"type": "http.response.body", "body": first, "more_body": True})
            async for chunk in self.source:
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        async def disconnected() -> None:
            while (await receive())["type"] != "http.disconnect":
                pass

        try:
            async with anyio.create_task_group() as group:

                async def run(action: Callable[[], Awaitable[None]]) -> None:
                    await action()
                    group.cancel_scope.cancel()

                group.start_soon(run, stream)
                await run(disconnected)
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await self.source.aclose()
                finally:
                    self.release()


def attach_benchmarks(
    app: FastAPI,
    config: RuntimeConfig,
    assets: Path,
    runtime: str,
    *,
    lock: asyncio.Lock,
    check_runtime: Callable[[], Awaitable[str]],
) -> None:
    package = Path(__file__).parent
    source_paths = [
        package / name
        for name in (
            "breeze_benchmark.py",
            "breeze.py",
            "preview_site.py",
            "inference.py",
            "cli.py",
            "config.py",
        )
    ]
    asset_paths = sorted(path for path in assets.rglob("*") if path.is_file())
    sources = {str(path): _sha(path.read_bytes()) for path in source_paths}
    build = {str(path.relative_to(assets)): _sha(path.read_bytes()) for path in asset_paths}
    instructions = {
        "default": config.tts_instruction,
        **{preset.preset_id: preset.instruction for preset in VOICE_PREVIEW_PRESETS},
    }
    suites = {"short": BENCHMARK_PROMPTS, "long": LONG_BENCHMARK_PROMPTS}
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "runtime_fingerprint": runtime,
        "playback_policy": POLICY,
        "cfg_scale": config.tts_cfg_scale,
        "sample_rate": 24000,
        "max_audio_s": 120,
        "suites": suites,
        "instructions": instructions,
        "source_sha256": sources,
        "assets_sha256": build,
    }
    manifest_hash = _identity(manifest)

    async def checked() -> None:
        if await check_runtime() != runtime:
            raise HTTPException(status_code=503, detail="Benchmark runtime changed")
        if any(_sha(Path(path).read_bytes()) != digest for path, digest in sources.items()) or any(
            _sha((assets / path).read_bytes()) != digest for path, digest in build.items()
        ):
            raise HTTPException(status_code=503, detail="Benchmark source/build changed; restart")

    @app.get("/api/benchmarks", include_in_schema=False)
    async def listing() -> dict[str, object]:
        await checked()
        return {**manifest, "manifest_sha256": manifest_hash}

    @app.get("/api/benchmarks/metrics/{request_id}", include_in_schema=False)
    async def metrics(request_id: str) -> dict[str, object]:
        try:
            _request_id(request_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        await checked()
        current = await asyncio.to_thread(health, config)
        try:
            _completed_metrics(current, runtime, request_id)
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"manifest_sha256": manifest_hash, "runtime": current}

    @app.post("/api/benchmarks/{suite}/{index}/stream", include_in_schema=False)
    async def stream(suite: str, index: int, request: Request) -> Response:
        if suite not in suites or not 0 <= index < len(suites[suite]):
            raise HTTPException(status_code=404, detail="Unknown benchmark case")
        if request.headers.get("content-type") != "application/json" or request.query_params:
            raise HTTPException(
                status_code=400, detail="Expected bounded JSON without query fields"
            )
        content_length = request.headers.get("content-length")
        if content_length is not None and (
            len(content_length) > 4
            or not content_length.isascii()
            or not content_length.isdecimal()
            or int(content_length) > 1024
        ):
            raise HTTPException(status_code=413, detail="Invalid or oversized Content-Length")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 1024:
                raise HTTPException(status_code=413, detail="Benchmark body exceeds 1024 bytes")
            body.extend(chunk)
        if content_length is not None and len(body) != int(content_length):
            raise HTTPException(status_code=400, detail="Content-Length does not match body")
        try:
            payload = _object(cast(object, json.loads(body, object_pairs_hook=_unique_keys)))
            if set(payload) != {"seed", "instruction_id"}:
                raise ValueError("Expected only seed and instruction_id")
            seed, instruction_id = payload["seed"], payload["instruction_id"]
            if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
                raise ValueError("Expected a uint32 seed")
            if not isinstance(instruction_id, str) or instruction_id not in instructions:
                raise ValueError("Unknown instruction ID")
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if (
            request.headers.get("X-Simo-Benchmark-Manifest") != manifest_hash
            or request.headers.get("X-Simo-Runtime-Fingerprint") != runtime
        ):
            raise HTTPException(status_code=409, detail="Benchmark manifest/runtime mismatch")
        await checked()
        if lock.locked():
            raise HTTPException(status_code=409, detail="A preview or benchmark is already running")
        synth = BreezeHTTPSynthesizer(
            config.tts_endpoint,
            instruction=instructions[instruction_id],
            cfg_scale=config.tts_cfg_scale,
            seed=seed,
            timeout_s=config.tts_timeout_s,
            expected_runtime=runtime,
            require_request_id=True,
        )

        async def pcm() -> AsyncGenerator[bytes, None]:
            total = 0
            async with aclosing(synth.synthesize(suites[suite][index])) as source:
                async for chunk in source:
                    total += len(chunk.pcm_s16le)
                    if (
                        chunk.sample_rate != 24000
                        or len(chunk.pcm_s16le) % 2
                        or total > MAX_PCM_BYTES
                    ):
                        raise RuntimeError("Benchmark exceeded PCM bounds")
                    if chunk.pcm_s16le:
                        yield chunk.pcm_s16le
            if total == 0:
                raise RuntimeError("Benchmark returned no PCM")

        await lock.acquire()
        return _BenchmarkResponse(
            pcm(),
            synth,
            lock.release,
            {
                "Cache-Control": "no-store",
                "X-Simo-Cache": "BYPASS",
                "X-Simo-Runtime-Fingerprint": runtime,
                "X-Simo-Benchmark-Manifest": manifest_hash,
                "X-Simo-Playback-Policy": POLICY,
                "X-Sample-Rate": "24000",
                "X-Sample-Format": "s16le",
            },
        )


class BenchmarkConnection:
    """Verified HTTPS to a private/loopback destination; never an inference allowlist change."""

    def __init__(self, url: str, ca_file: Path | None, connect_address: str | None) -> None:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or any((parsed.username, parsed.password, parsed.query, parsed.fragment))
            or parsed.path not in ("", "/")
        ):
            raise ValueError("Benchmark URL must be an HTTPS origin")
        self.hostname, self.port = parsed.hostname, parsed.port or 443
        self.context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
        self.address = connect_address or self.hostname

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[http.client.HTTPSConnection, http.client.HTTPResponse]:
        addresses = socket.getaddrinfo(self.address, self.port, type=socket.SOCK_STREAM)
        if not addresses:
            raise ValueError("No benchmark address")
        for _, _, _, _, address in addresses:
            ip = ipaddress.ip_address(address[0])
            if not ip.is_private or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
                raise ValueError("Benchmark destination must be private or loopback")
        connection = http.client.HTTPSConnection(
            self.hostname, self.port, timeout=180, context=self.context
        )
        raw: socket.socket | None = None
        try:
            # Use the already validated numeric address, retaining URL hostname verification/SNI.
            raw = socket.create_connection((str(addresses[0][4][0]), self.port), timeout=5)
            connection.sock = self.context.wrap_socket(raw, server_hostname=self.hostname)
            connection.sock.settimeout(180)
            connection.request(method, path, body=body, headers=headers or {})
            return connection, connection.getresponse()
        except BaseException:
            if raw is not None:
                raw.close()
            connection.close()
            raise

    def json(self, path: str) -> dict[str, object]:
        connection, response = self.request("GET", path)
        try:
            data = response.read(65537)
            if response.status != 200 or len(data) > 65536:
                raise RuntimeError(f"Benchmark metadata HTTP {response.status} or oversized body")
            return _object(cast(object, json.loads(data, object_pairs_hook=_unique_keys)))
        finally:
            connection.close()


def run_https_benchmark(
    config: RuntimeConfig,
    *,
    url: str,
    ca_file: Path | None = None,
    connect_address: str | None = None,
    warmups: int = 3,
    limit: int = 10,
    suite: str = "short",
    seeds: tuple[int, ...] = (17, 29, 42),
    instruction_id: str = "default",
    audio_dir: Path,
) -> dict[str, object]:
    if (
        not 0 <= warmups <= 10
        or not 1 <= limit <= 10
        or not 1 <= len(seeds) <= 10
        or len(set(seeds)) != len(seeds)
        or any(type(seed) is not int or not 0 <= seed <= 2**32 - 1 for seed in seeds)
    ):
        raise ValueError("Invalid bounded benchmark warmups/limit/seeds")
    if suite not in ("short", "long"):
        raise ValueError("Unknown suite")
    client = BenchmarkConnection(url, ca_file, connect_address)
    manifest = client.json("/api/benchmarks")
    manifest_hash = manifest.pop("manifest_sha256", None)
    if (
        manifest_hash != _identity(manifest)
        or manifest.get("schema") != SCHEMA
        or manifest.get("playback_policy") != POLICY
    ):
        raise ValueError("Invalid benchmark manifest")
    runtime = manifest.get("runtime_fingerprint")
    if not isinstance(runtime, str) or re.fullmatch(r"[0-9a-f]{64}", runtime) is None:
        raise ValueError("Invalid benchmark runtime fingerprint")
    if manifest.get("cfg_scale") != config.tts_cfg_scale or manifest.get("sample_rate") != 24000:
        raise ValueError("Benchmark settings differ from operator configuration")
    suites = _object(manifest["suites"])
    prompts = suites[suite]
    expected_prompts = BENCHMARK_PROMPTS if suite == "short" else LONG_BENCHMARK_PROMPTS
    if prompts != list(expected_prompts):
        raise ValueError("Benchmark corpus differs from this CLI")
    instructions = _object(manifest["instructions"])
    expected_instructions = {
        "default": config.tts_instruction,
        **{p.preset_id: p.instruction for p in VOICE_PREVIEW_PRESETS},
    }
    if instructions != expected_instructions or instruction_id not in instructions:
        raise ValueError("Benchmark instructions differ from this CLI")
    # Every attempt gets a new directory; no old evidence or preview cache is overwritten.
    audio_dir.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    headers = {
        "Content-Type": "application/json",
        "X-Simo-Runtime-Fingerprint": runtime,
        "X-Simo-Benchmark-Manifest": str(manifest_hash),
    }
    samples: list[dict[str, object]] = []
    chunks: list[list[dict[str, float]]] = []
    artifacts: list[dict[str, str]] = []
    metrics: list[dict[str, object]] = []
    warmup_samples: list[dict[str, object]] = []
    report: dict[str, object] = {
        "schema_version": 3,
        "recorded_at": datetime.now(UTC).isoformat(),
        "url": url,
        "manifest": {**manifest, "manifest_sha256": manifest_hash},
        "runtime": {"runtime_fingerprint": runtime},
        "suite": suite,
        "limit": limit,
        "timed_case_count": min(limit, len(expected_prompts)) * len(seeds),
        "instruction_id": instruction_id,
        "instruction": instructions[instruction_id],
        "cfg_scale": config.tts_cfg_scale,
        "seeds": seeds,
        "warmups": warmups,
        "warmup_samples": warmup_samples,
        "samples": samples,
        "chunk_arrivals": chunks,
        "audio_artifacts": artifacts,
        "service_samples": metrics,
        "completed": False,
        "release_gate": {
            "browser_playback": "not_measured",
            "underruns": "not_measured",
            "listening": "not_measured",
            "accepted": False,
        },
        "proof": "Unpaced verified HTTPS to a private address, cache BYPASS, request-bound producer metrics. Same-host LAN IP is not remote Wi-Fi or audible playback proof.",
    }
    started_ns = time.time_ns()
    report["started_unix_ns"] = started_ns
    schedule = [(True, 0, seeds[0]) for _ in range(warmups)] + [
        (False, index, seed) for index in range(min(limit, len(expected_prompts))) for seed in seeds
    ]
    current_case: dict[str, object] = {}
    pcm = bytearray()
    arrivals: list[dict[str, float]] = []
    try:
        for is_warmup, index, seed in schedule:
            current_case = {
                "warmup": is_warmup,
                "index": index,
                "seed": seed,
                "instruction_id": instruction_id,
            }
            pcm, arrivals = bytearray(), []
            started = time.perf_counter()
            connection, response = client.request(
                "POST",
                f"/api/benchmarks/{suite}/{index}/stream",
                body=json.dumps({"seed": seed, "instruction_id": instruction_id}).encode(),
                headers=headers,
            )
            try:
                expected = {
                    "X-Simo-Runtime-Fingerprint": runtime,
                    "X-Simo-Benchmark-Manifest": str(manifest_hash),
                    "X-Simo-Playback-Policy": POLICY,
                    "X-Simo-Cache": "BYPASS",
                    "X-Sample-Rate": "24000",
                    "X-Sample-Format": "s16le",
                }
                if response.status != 200 or any(
                    response.getheader(k) != v for k, v in expected.items()
                ):
                    raise RuntimeError("Benchmark response status or identity mismatch")
                request_id = _request_id(response.getheader("X-Breeze-Request-ID"))
                if request_id in seen:
                    raise RuntimeError("Benchmark reused a request ID")
                seen.add(request_id)
                current_case["request_id"] = request_id
                while payload := response.read1(4800):
                    at_s = time.perf_counter() - started
                    if len(pcm) + len(payload) > MAX_PCM_BYTES:
                        raise RuntimeError("Benchmark response exceeds audio cap")
                    pcm.extend(payload)
                    aligned_bytes = len(pcm) - len(pcm) % 2
                    if aligned_bytes > (round(arrivals[-1]["audio_s"] * 48000) if arrivals else 0):
                        arrivals.append({"at_s": at_s, "audio_s": aligned_bytes / 48000})
                wall = time.perf_counter() - started
                if not pcm or len(pcm) % 2:
                    raise RuntimeError("Benchmark returned empty or misaligned PCM")
            finally:
                response.close()
                connection.close()
            # EOF may precede the sidecar's final cleanup; bounded polling never accepts another ID.
            completed_metrics: dict[str, object] | None = None
            for _ in range(40):
                try:
                    completed_metrics = client.json(f"/api/benchmarks/metrics/{request_id}")
                    break
                except RuntimeError:
                    time.sleep(0.05)
            if (
                completed_metrics is None
                or completed_metrics.get("manifest_sha256") != manifest_hash
            ):
                raise RuntimeError("No matching completed benchmark metrics")
            measured_runtime = _object(completed_metrics["runtime"])
            last = _completed_metrics(measured_runtime, runtime, request_id)
            if last.get("audio_samples") != len(pcm) // 2:
                raise RuntimeError("Benchmark producer metrics do not match completed response")
            report["runtime"] = measured_runtime
            audio_s = len(pcm) / 48000
            remaining = audio_s - arrivals[0]["audio_s"]
            sample: dict[str, object] = {
                **current_case,
                "prompt": expected_prompts[index],
                "first_audio_s": arrivals[0]["at_s"],
                "wall_s": wall,
                "audio_s": audio_s,
                "frames": len(pcm) // 2,
                "rtf": wall / audio_s,
                "steady_rtf": (arrivals[-1]["at_s"] - arrivals[0]["at_s"]) / remaining
                if remaining > 0
                else None,
                "cache": "BYPASS",
                "pcm_sha256": _sha(pcm),
                "metrics": last,
            }
            if is_warmup:
                warmup_samples.append(sample)
            else:
                path = audio_dir / f"prompt-{index + 1:02d}-seed-{seed}.wav"
                with path.open("xb") as file, wave.open(file, "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(24000)
                    output.writeframes(pcm)
                samples.append(sample)
                chunks.append(arrivals)
                metrics.append(last)
                artifacts.append({"path": str(path.resolve()), "pcm_sha256": _sha(pcm)})
        report["first_audio_p95_s"] = _percentile(
            [float(str(s["first_audio_s"])) for s in samples], 0.95
        )
        report["rtf_p95"] = _percentile([float(str(s["rtf"])) for s in samples], 0.95)
        steady = [float(str(s["steady_rtf"])) for s in samples if s["steady_rtf"] is not None]
        report["steady_rtf_p95"] = (
            _percentile(steady, 0.95) if len(steady) == len(samples) else None
        )
        report["completed"] = True
    except Exception as error:
        report["failure"] = {
            "case": current_case,
            "type": type(error).__name__,
            "message": str(error),
            "partial_bytes": len(pcm),
            "partial_pcm_sha256": _sha(pcm),
            "arrivals": arrivals,
        }
        if pcm:
            with (audio_dir / "failed-partial.pcm").open("xb") as partial:
                partial.write(pcm)
    finally:
        report["finished_unix_ns"] = time.time_ns()
        with (audio_dir / "report.json").open("x") as file:
            json.dump(report, file, indent=2)
    return report
