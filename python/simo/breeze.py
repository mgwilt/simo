"""Operational health and bounded performance proof for the Breeze sidecar."""

from __future__ import annotations

import asyncio
import http.client
import json
import statistics
import time
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True, slots=True)
class BreezeSample:
    prompt: str
    first_audio_s: float
    wall_s: float
    audio_s: float
    rtf: float


def health(config: RuntimeConfig) -> dict[str, object]:
    url = config.tts_endpoint.rsplit("/", 3)[0] + "/health"
    parsed = urlparse(url)
    if parsed.hostname is None:
        raise ValueError("Breeze health URL has no host")
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=2.0)
    try:
        connection.request("GET", parsed.path)
        response = connection.getresponse()
        payload = cast(object, json.loads(response.read(16_384)))
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
) -> dict[str, object]:
    if warmups < 0 or not prompts:
        raise ValueError("Breeze benchmark requires prompts and non-negative warmups")
    synthesizer = BreezeHTTPSynthesizer(
        config.tts_endpoint,
        instruction=config.tts_instruction,
        cfg_scale=config.tts_cfg_scale,
        seed=config.tts_seed,
        timeout_s=config.tts_timeout_s,
    )
    for prompt in prompts[:warmups]:
        _ = [chunk async for chunk in synthesizer.synthesize(prompt)]
    samples: list[BreezeSample] = []
    for prompt in prompts:
        started = time.perf_counter()
        first_audio: float | None = None
        audio_bytes = 0
        sample_rate = 24_000
        async for chunk in synthesizer.synthesize(prompt):
            if first_audio is None:
                first_audio = time.perf_counter() - started
            audio_bytes += len(chunk.pcm_s16le)
            sample_rate = chunk.sample_rate
        wall_s = time.perf_counter() - started
        if first_audio is None or audio_bytes == 0:
            raise RuntimeError("Breeze benchmark produced no audio")
        audio_s = audio_bytes / (sample_rate * 2)
        samples.append(BreezeSample(prompt, first_audio, wall_s, audio_s, wall_s / audio_s))
    first_audio_values = [sample.first_audio_s for sample in samples]
    rtf_values = [sample.rtf for sample in samples]
    first_audio_p50 = statistics.median(first_audio_values)
    first_audio_p95 = _percentile(first_audio_values, 0.95)
    rtf_p50 = statistics.median(rtf_values)
    rtf_p95 = _percentile(rtf_values, 0.95)
    summary: dict[str, object] = {
        "warmups": warmups,
        "samples": [asdict(sample) for sample in samples],
        "first_audio_p50_s": first_audio_p50,
        "first_audio_p95_s": first_audio_p95,
        "rtf_p50": rtf_p50,
        "rtf_p95": rtf_p95,
        "preview_gate": {
            "first_audio_p95_at_most_2s": first_audio_p95 <= 2.0,
            "rtf_p95_at_most_1_5": rtf_p95 <= 1.5,
        },
    }
    return summary


def run_benchmark(config: RuntimeConfig) -> dict[str, object]:
    return asyncio.run(benchmark(config))


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * quantile)))
    return ordered[index]
