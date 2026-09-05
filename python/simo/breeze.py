"""Operational health and bounded performance proof for the Breeze sidecar."""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import math
import socket
import ssl
import statistics
import time
import wave
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from simo.config import RuntimeConfig
from simo.inference import BreezeHTTPSynthesizer

BENCHMARK_PROMPTS = (
    "Good morning. I am ready when you are.",
    "Tell me what you would like to explore today.",
    "That makes sense, and I can help you think it through.",
    "Let us slow down and examine the most important detail.",
    "I remember what you said earlier, including the correction.",
    "A calm voice can make a difficult conversation feel more manageable.",
    "The prototype is running locally and keeping this conversation private.",
    "Please interrupt me if you want to change direction.",
    "We can compare the options and choose one concrete next step.",
    "Thank you. I will keep the answer short and complete.",
)

LONG_BENCHMARK_PROMPTS = (
    "Before we begin, take a moment to settle in. We will compare the options carefully, explain the tradeoffs in plain language, and choose one small next step. There is no need to rush. If something does not make sense, we can pause, return to the important detail, and try a different explanation. The goal is a complete and useful answer, from the first sentence to the last.",
    "The local prototype has several parts working together. Text becomes a sequence of audio codes, those codes become sound, and the browser plays the sound as it arrives. A good test checks the whole journey. It should catch missing words, repeated phrases, unexpected silence, and an ending that stops too soon. This final sentence is here to verify that the entire passage has been spoken.",
)


@dataclass(frozen=True, slots=True)
class BreezeSample:
    prompt: str
    first_audio_s: float
    wall_s: float
    audio_s: float
    rtf: float
    seed: int = 42
    steady_rtf: float | None = None
    max_chunk_gap_s: float = 0.0
    chunks: int = 0


def health(config: RuntimeConfig) -> dict[str, object]:
    url = config.tts_endpoint.rsplit("/", 3)[0] + "/health"
    parsed = urlparse(url)
    if parsed.hostname is None:
        raise ValueError("Breeze health URL has no host")
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=2.0)
    try:
        connection.request("GET", parsed.path)
        response = connection.getresponse()
        payload = cast(object, json.loads(response.read(65_536)))
    finally:
        connection.close()
    if not isinstance(payload, dict):
        raise TypeError("Breeze health response must be an object")
    return {str(key): value for key, value in cast(dict[object, object], payload).items()}


async def benchmark(
    config: RuntimeConfig,
    *,
    warmups: int = 3,
    prompts: tuple[str, ...] = BENCHMARK_PROMPTS,
    seeds: tuple[int, ...] | None = None,
    audio_dir: Path | None = None,
) -> dict[str, object]:
    if warmups < 0 or not prompts:
        raise ValueError("Breeze benchmark requires prompts and non-negative warmups")
    before = await asyncio.to_thread(health, config)
    fingerprint = before.get("runtime_fingerprint")
    expected = fingerprint if isinstance(fingerprint, str) else None
    selected_seeds = seeds or (config.tts_seed,)
    if audio_dir is not None:
        audio_dir.mkdir(parents=True, exist_ok=True)

    def create_synthesizer(seed: int) -> BreezeHTTPSynthesizer:
        return BreezeHTTPSynthesizer(
            config.tts_endpoint,
            instruction=config.tts_instruction,
            cfg_scale=config.tts_cfg_scale,
            seed=seed,
            timeout_s=config.tts_timeout_s,
            expected_runtime=expected,
        )

    synthesizer = create_synthesizer(selected_seeds[0])
    warmup_samples: list[dict[str, object]] = []
    for index in range(warmups):
        started = time.perf_counter()
        first = None
        byte_count = 0
        async for chunk in synthesizer.synthesize(prompts[index % len(prompts)]):
            first = first if first is not None else time.perf_counter() - started
            byte_count += len(chunk.pcm_s16le)
        warmup_samples.append(
            {
                "first_pcm_s": first,
                "wall_s": time.perf_counter() - started,
                "audio_s": byte_count / 48000,
            }
        )
    samples: list[BreezeSample] = []
    service_samples: list[object] = []
    chunk_samples: list[list[dict[str, float]]] = []
    audio_artifacts: list[dict[str, str]] = []
    for index in range(len(prompts) * len(selected_seeds)):
        prompt = prompts[index // len(selected_seeds)]
        seed = selected_seeds[index % len(selected_seeds)]
        synthesizer = create_synthesizer(seed)
        started = time.perf_counter()
        first_audio: float | None = None
        audio_bytes = 0
        sample_rate = 24_000
        arrivals: list[dict[str, float]] = []
        pcm = bytearray()
        async for chunk in synthesizer.synthesize(prompt):
            elapsed = time.perf_counter() - started
            if first_audio is None:
                first_audio = elapsed
            audio_bytes += len(chunk.pcm_s16le)
            sample_rate = chunk.sample_rate
            arrivals.append({"at_s": elapsed, "audio_s": audio_bytes / (sample_rate * 2)})
            if audio_dir is not None:
                pcm.extend(chunk.pcm_s16le)
        wall_s = time.perf_counter() - started
        if first_audio is None or audio_bytes == 0:
            raise RuntimeError("Breeze benchmark produced no audio")
        audio_s = audio_bytes / (sample_rate * 2)
        remaining_audio = audio_s - arrivals[0]["audio_s"]
        steady_rtf = (
            (arrivals[-1]["at_s"] - first_audio) / remaining_audio if remaining_audio > 0 else None
        )
        max_gap = max(
            (right["at_s"] - left["at_s"] for left, right in pairwise(arrivals)),
            default=0.0,
        )
        samples.append(
            BreezeSample(
                prompt,
                first_audio,
                wall_s,
                audio_s,
                wall_s / audio_s,
                seed,
                steady_rtf,
                max_gap,
                len(arrivals),
            )
        )
        chunk_samples.append(arrivals)
        if audio_dir is not None:
            path = audio_dir / f"prompt-{index // len(selected_seeds) + 1:02d}-seed-{seed}.wav"
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite listening artifact: {path}")
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(sample_rate)
                output.writeframes(pcm)
            audio_artifacts.append(
                {"path": str(path.resolve()), "pcm_sha256": hashlib.sha256(pcm).hexdigest()}
            )
        after = await asyncio.to_thread(health, config)
        if expected is not None and after.get("runtime_fingerprint") != expected:
            raise RuntimeError("Breeze runtime changed during benchmark")
        service_samples.append(after.get("last_request"))
    first_audio_values = [sample.first_audio_s for sample in samples]
    rtf_values = [sample.rtf for sample in samples]
    first_audio_p50 = statistics.median(first_audio_values)
    first_audio_p95 = _percentile(first_audio_values, 0.95)
    rtf_p50 = statistics.median(rtf_values)
    rtf_p95 = _percentile(rtf_values, 0.95)
    summary: dict[str, object] = {
        "schema_version": 2,
        "recorded_at": datetime.now(UTC).isoformat(),
        "runtime": before,
        "instruction": config.tts_instruction,
        "cfg_scale": config.tts_cfg_scale,
        "seeds": selected_seeds,
        "warmups": warmups,
        "warmup_samples": warmup_samples,
        "service_previously_used": bool(before.get("last_request")),
        "audio_artifacts": audio_artifacts,
        "samples": [asdict(sample) for sample in samples],
        "chunk_arrivals": chunk_samples,
        "service_samples": service_samples,
        "first_audio_p50_s": first_audio_p50,
        "first_audio_p95_s": first_audio_p95,
        "rtf_p50": rtf_p50,
        "rtf_p95": rtf_p95,
        "steady_rtf_p95": _percentile(
            [sample.steady_rtf for sample in samples if sample.steady_rtf is not None], 0.95
        )
        if all(sample.steady_rtf is not None for sample in samples)
        else None,
        "model_screen": {
            "first_audio_p95_at_most_2s": first_audio_p95 <= 2.0,
            "rtf_p95_at_most_0_8": rtf_p95 <= 0.8,
        },
        "release_gate": {
            "browser_playback": "not_measured",
            "underruns": "not_measured",
            "listening": "not_measured",
            "accepted": False,
        },
    }
    return summary


def run_benchmark(
    config: RuntimeConfig,
    *,
    warmups: int = 3,
    limit: int = 10,
    seeds: tuple[int, ...] | None = None,
    suite: str = "short",
    audio_dir: Path | None = None,
) -> dict[str, object]:
    if not 1 <= limit <= len(BENCHMARK_PROMPTS):
        raise ValueError("Benchmark limit must be between 1 and 10")
    if suite not in ("short", "long"):
        raise ValueError("Unknown benchmark suite")
    prompts = BENCHMARK_PROMPTS if suite == "short" else LONG_BENCHMARK_PROMPTS
    return asyncio.run(
        benchmark(
            config, warmups=warmups, prompts=prompts[:limit], seeds=seeds, audio_dir=audio_dir
        )
    )


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]


def verify_preview_site(
    config: RuntimeConfig,
    *,
    url: str,
    ca_file: Path | None = None,
    connect_address: str | None = None,
) -> dict[str, object]:
    """Scripted LAN proof; never equates HTTP arrivals with audible playout."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Preview proof requires an HTTPS site origin")
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
    hostname = parsed.hostname
    initial_runtime = health(config)
    expected_runtime = initial_runtime.get("runtime_fingerprint")
    if (
        initial_runtime.get("status") != "ready"
        or not isinstance(expected_runtime, str)
        or len(expected_runtime) != 64
        or any(character not in "0123456789abcdef" for character in expected_runtime)
    ):
        raise RuntimeError("Preview proof requires a ready fingerprinted Breeze runtime")

    def matched_health() -> dict[str, object]:
        current = health(config)
        if current.get("runtime_fingerprint") != expected_runtime:
            raise RuntimeError("Breeze runtime changed during preview proof")
        return current

    def require_identity(response: http.client.HTTPResponse) -> None:
        if response.getheader("X-Simo-Runtime-Fingerprint") != expected_runtime:
            raise RuntimeError("Preview response runtime fingerprint does not match Breeze")

    def connect() -> http.client.HTTPSConnection:
        connection = http.client.HTTPSConnection(
            hostname, parsed.port or 443, timeout=180, context=context
        )
        if connect_address:
            # Explicit routing preserves TLS hostname verification/SNI.
            raw = socket.create_connection((connect_address, parsed.port or 443), timeout=180)
            try:
                connection.sock = context.wrap_socket(raw, server_hostname=hostname)
            except BaseException:
                raw.close()
                raise
        return connection

    def request(
        method: str, path: str
    ) -> tuple[http.client.HTTPSConnection, http.client.HTTPResponse]:
        connection = connect()
        try:
            connection.request(method, path)
            return connection, connection.getresponse()
        except BaseException:
            connection.close()
            raise

    def listing() -> list[dict[str, object]]:
        connection, response = request("GET", "/api/previews")
        try:
            if response.status != 200:
                raise RuntimeError(f"Preview list HTTP {response.status}")
            payload = cast(dict[str, object], json.loads(response.read(65536)))
            return cast(list[dict[str, object]], payload["presets"])
        finally:
            connection.close()

    presets = listing()
    target = next((item for item in presets if not item["cached"]), None)
    if target is None:
        raise RuntimeError(
            "All previews are cached; use a fresh runtime fingerprint for uncached proof"
        )
    path = f"/api/previews/{target['id']}"
    started = time.perf_counter()
    connection, response = request("POST", path + "/stream")
    try:
        if response.status != 200 or response.getheader("X-Simo-Cache") != "MISS":
            raise RuntimeError(f"Uncached preview HTTP {response.status}")
        require_identity(response)
        first = response.read1(3840)
        first_pcm = time.perf_counter() - started
        if (
            not first
            or response.getheader("X-Sample-Rate") != "24000"
            or response.getheader("X-Sample-Format") != "s16le"
        ):
            raise RuntimeError("Invalid first preview PCM")
        busy_before_cancel = matched_health().get("busy")
        if connection.sock is not None:
            connection.sock.shutdown(socket.SHUT_RDWR)
    finally:
        response.close()
        connection.close()
    released = False
    for _ in range(100):
        if not matched_health().get("busy"):
            released = True
            break
        time.sleep(0.05)
    if not released or next(item for item in listing() if item["id"] == target["id"])["cached"]:
        raise RuntimeError("Cancellation failed to release inference or committed partial audio")
    samples: list[dict[str, object]] = []
    for preset in presets:
        path = f"/api/previews/{preset['id']}"
        started = time.perf_counter()
        connection, response = request("POST", path + "/stream")
        try:
            if response.status != 200:
                raise RuntimeError(f"Immediate retry HTTP {response.status}")
            require_identity(response)
            if (
                response.getheader("X-Sample-Rate") != "24000"
                or response.getheader("X-Sample-Format") != "s16le"
            ):
                raise RuntimeError("Invalid completed preview PCM metadata")
            cache = response.getheader("X-Simo-Cache")
            first = response.read1(3840)
            elapsed_first = time.perf_counter() - started
            pcm = first + response.read(120 * 48000 + 1)
            if not pcm or len(pcm) % 2 or len(pcm) > 120 * 48000:
                raise RuntimeError("Invalid completed preview")
            stream_wall = time.perf_counter() - started
        finally:
            response.close()
            connection.close()
        connection, response = request("POST", path)
        try:
            require_identity(response)
            wav_bytes = response.read(120 * 48000 + 1024)
            if response.status != 200 or response.getheader("X-Simo-Cache") != "HIT":
                raise RuntimeError("Completed preview did not populate legacy WAV cache")
        finally:
            connection.close()
        import io

        with wave.open(io.BytesIO(wav_bytes), "rb") as cached:
            if (cached.getnchannels(), cached.getsampwidth(), cached.getframerate()) != (
                1,
                2,
                24000,
            ):
                raise RuntimeError("Invalid cached WAV format")
            if cached.readframes(cached.getnframes()) != pcm:
                raise RuntimeError("Cached WAV differs from streamed PCM")
        samples.append(
            {
                "preset": preset["id"],
                "instruction": preset["instruction"],
                "cache": cache,
                "first_pcm_s": elapsed_first,
                "wall_s": stream_wall,
                "audio_s": len(pcm) / 48000,
                "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                "cache_exact": True,
                "runtime_fingerprint": expected_runtime,
            }
        )
    return {
        "schema_version": 2,
        "url": url,
        "tls_verified": True,
        "response_runtime_verified": True,
        "expected_runtime_fingerprint": expected_runtime,
        "first_pcm_before_cancel_s": first_pcm,
        "generation_busy_at_first_pcm": busy_before_cancel,
        "cancellation_released": True,
        "partial_cache_absent": True,
        "samples": samples,
        "runtime": matched_health(),
        "browser_playback": "not_measured",
        "listening": "not_measured",
    }
