"""Executable no-device proofs for Simo's selected local MLX models."""

from __future__ import annotations

import re
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from simo.config import RuntimeConfig
from simo.inference import (
    MLXAudioSynthesizer,
    MLXTextGenerator,
    ParakeetMLXRecognizer,
    SpeechRecognizer,
    SpeechSynthesizer,
    TextGenerator,
)

TEXT_PROOF_RESPONSE = "SIMO TEXT READY"
SPEECH_PROOF_PHRASE = "The blue door is open."


async def prove_models(
    config: RuntimeConfig,
    artifact_dir: Path,
    *,
    generator: TextGenerator | None = None,
    synthesizer: SpeechSynthesizer | None = None,
    recognizer: SpeechRecognizer | None = None,
) -> dict[str, Any]:
    """Load and execute text, TTS, and STT adapters without audio devices."""

    generator = generator or MLXTextGenerator(config.text.local_path)
    synthesizer = synthesizer or MLXAudioSynthesizer(
        config.tts.local_path,
        voice=config.tts_voice,
        streaming_interval_s=config.tts_streaming_interval_s,
    )
    recognizer = recognizer or ParakeetMLXRecognizer(config.stt.local_path)

    text_prompt = f"Reply with exactly: {TEXT_PROOF_RESPONSE}"
    text_cold, text_cold_ms = await _timed_generate(generator, text_prompt)
    text_warm, text_warm_ms = await _timed_generate(generator, text_prompt)
    if text_cold != TEXT_PROOF_RESPONSE or text_warm != TEXT_PROOF_RESPONSE:
        raise RuntimeError("text model did not produce the bounded proof response")

    cold_audio, tts_cold_first_ms, tts_cold_total_ms = await _timed_synthesis(
        synthesizer,
        SPEECH_PROOF_PHRASE,
    )
    _, tts_warm_first_ms, tts_warm_total_ms = await _timed_synthesis(
        synthesizer,
        SPEECH_PROOF_PHRASE,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    wav_path = artifact_dir / "tts.wav"
    _write_wav(wav_path, cold_audio, 24_000)

    stt_pcm = resample_pcm_s16le(cold_audio, 24_000, 16_000)
    stt_cold, stt_cold_ms = await _timed_transcribe(recognizer, stt_pcm)
    stt_warm, stt_warm_ms = await _timed_transcribe(recognizer, stt_pcm)
    expected_words = _normalize_words(SPEECH_PROOF_PHRASE)
    if _normalize_words(stt_cold) != expected_words:
        raise RuntimeError("STT cold proof did not reproduce the synthetic phrase")
    if _normalize_words(stt_warm) != expected_words:
        raise RuntimeError("STT warm proof did not reproduce the synthetic phrase")

    duration_s = len(cold_audio) / 2 / 24_000
    return {
        "schema_version": 1,
        "artifact": str(wav_path),
        "text": {
            "model_id": config.text.model_id,
            "revision": config.text.revision,
            "cold_ms": round(text_cold_ms, 2),
            "warm_ms": round(text_warm_ms, 2),
            "response": text_warm,
        },
        "tts": {
            "model_id": config.tts.model_id,
            "revision": config.tts.revision,
            "voice": config.tts_voice,
            "pcm_bytes": len(cold_audio),
            "duration_s": round(duration_s, 3),
            "cold_first_chunk_ms": round(tts_cold_first_ms, 2),
            "cold_total_ms": round(tts_cold_total_ms, 2),
            "warm_first_chunk_ms": round(tts_warm_first_ms, 2),
            "warm_total_ms": round(tts_warm_total_ms, 2),
        },
        "stt": {
            "model_id": config.stt.model_id,
            "revision": config.stt.revision,
            "input_duration_s": round(duration_s, 3),
            "cold_ms": round(stt_cold_ms, 2),
            "cold_realtime_factor": round(stt_cold_ms / (duration_s * 1_000), 3),
            "warm_ms": round(stt_warm_ms, 2),
            "warm_realtime_factor": round(stt_warm_ms / (duration_s * 1_000), 3),
            "transcript": stt_warm,
        },
    }


async def _timed_generate(
    generator: TextGenerator,
    prompt: str,
) -> tuple[str, float]:
    started = time.perf_counter()
    result = await generator.generate(prompt, max_tokens=32)
    return result, (time.perf_counter() - started) * 1_000


async def _timed_synthesis(
    synthesizer: SpeechSynthesizer,
    text: str,
) -> tuple[bytes, float, float]:
    started = time.perf_counter()
    first_ms: float | None = None
    chunks: list[bytes] = []
    async for chunk in synthesizer.synthesize(text):
        if chunk.sample_rate != 24_000:
            raise RuntimeError(f"TTS proof expected 24000 Hz, got {chunk.sample_rate}")
        if first_ms is None:
            first_ms = (time.perf_counter() - started) * 1_000
        chunks.append(chunk.pcm_s16le)
    pcm = b"".join(chunks)
    if first_ms is None or not pcm:
        raise RuntimeError("TTS proof produced no audio")
    return pcm, first_ms, (time.perf_counter() - started) * 1_000


async def _timed_transcribe(
    recognizer: SpeechRecognizer,
    pcm_s16le: bytes,
) -> tuple[str, float]:
    started = time.perf_counter()
    result = await recognizer.transcribe(pcm_s16le, 16_000)
    return result, (time.perf_counter() - started) * 1_000


def resample_pcm_s16le(
    pcm_s16le: bytes,
    source_rate: int,
    target_rate: int,
) -> bytes:
    """Linearly resample mono signed 16-bit PCM for the synthetic proof."""

    if not pcm_s16le or len(pcm_s16le) % 2:
        raise ValueError("resampling requires non-empty 16-bit PCM")
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("sample rates must be positive")
    samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32)
    target_count = round(len(samples) * target_rate / source_rate)
    positions = np.linspace(0, len(samples) - 1, target_count)
    resampled = np.interp(positions, np.arange(len(samples)), samples)
    return np.clip(resampled, -32768, 32767).astype("<i2").tobytes()


def _write_wav(path: Path, pcm_s16le: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm_s16le)


def _normalize_words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
