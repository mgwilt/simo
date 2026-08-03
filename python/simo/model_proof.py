"""Executable no-device proofs for Simo's selected local MLX models."""

from __future__ import annotations

import re
import time
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

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

if TYPE_CHECKING:
    from pipecat.frames.frames import InputAudioRawFrame

TEXT_PROOF_RESPONSE = "SIMO TEXT READY"
SPEECH_PROOF_PHRASE = "The blue door is open."
SYNTHETIC_PROOF_TURNS = 3


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
    vad_result = await prove_synthetic_vad(config, stt_pcm, cold_audio)
    stt_cold, stt_cold_ms = await _timed_transcribe(recognizer, stt_pcm)
    stt_warm, stt_warm_ms = await _timed_transcribe(recognizer, stt_pcm)
    expected_words = _normalize_words(SPEECH_PROOF_PHRASE)
    if _normalize_words(stt_cold) != expected_words:
        raise RuntimeError("STT cold proof did not reproduce the synthetic phrase")
    if _normalize_words(stt_warm) != expected_words:
        raise RuntimeError("STT warm proof did not reproduce the synthetic phrase")

    duration_s = len(cold_audio) / 2 / 24_000
    result = {
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
        "vad": vad_result,
    }
    result["pipeline"] = await prove_real_model_pipeline(
        config,
        stt_pcm,
        generator=generator,
        synthesizer=synthesizer,
        recognizer=recognizer,
    )
    return result


async def prove_synthetic_vad(
    config: RuntimeConfig,
    speech_pcm_s16le: bytes,
    playback_pcm_s16le: bytes,
) -> dict[str, Any]:
    """Prove real Silero turn detection and echo suppression without audio devices."""

    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.frames.frames import EndFrame
    from pipecat.processors.frame_processor import FrameDirection

    from simo.adapters.pipecat.inference import PCMUtteranceFrame
    from simo.adapters.pipecat.local_audio import (
        ObservedSileroVADAnalyzer,
        PlaybackState,
        SileroUtteranceProcessor,
    )
    from simo.operations import RuntimeMetrics

    if not speech_pcm_s16le or len(speech_pcm_s16le) % 2:
        raise ValueError("synthetic VAD proof requires non-empty 16-bit speech PCM")
    if not playback_pcm_s16le or len(playback_pcm_s16le) % 2:
        raise ValueError("synthetic VAD proof requires non-empty 16-bit playback PCM")

    metrics = RuntimeMetrics()
    playback_state = PlaybackState()
    analyzer = ObservedSileroVADAnalyzer(
        runtime_metrics=metrics,
        sample_rate=16_000,
        params=VADParams(
            confidence=config.vad_confidence,
            start_secs=config.vad_start_ms / 1_000,
            stop_secs=config.vad_stop_ms / 1_000,
            min_volume=0.0,
        ),
    )
    segmenter = SileroUtteranceProcessor(
        analyzer,
        pre_roll_ms=config.vad_pre_roll_ms,
        max_utterance_s=config.max_utterance_s,
        runtime_metrics=metrics,
        playback_state=playback_state,
        user_id="synthetic-proof",
    )
    emitted: list[object] = []

    async def collect(  # noqa: RUF029 - Pipecat push_frame is asynchronous.
        frame: object,
        direction: FrameDirection,
    ) -> None:
        del direction
        emitted.append(frame)

    segmenter.push_frame = collect  # type: ignore[method-assign]
    try:
        silence = b"\x00\x00" * 320
        for _ in range(10):
            await segmenter.process_frame(
                _input_audio_frame(silence, sample_rate=16_000),
                FrameDirection.DOWNSTREAM,
            )
        for _turn in range(SYNTHETIC_PROOF_TURNS):
            for chunk in _pcm_chunks(speech_pcm_s16le, frames_per_chunk=320):
                await segmenter.process_frame(
                    _input_audio_frame(chunk, sample_rate=16_000),
                    FrameDirection.DOWNSTREAM,
                )
            for _ in range(30):
                await segmenter.process_frame(
                    _input_audio_frame(silence, sample_rate=16_000),
                    FrameDirection.DOWNSTREAM,
                )
        await segmenter.process_frame(EndFrame(), FrameDirection.DOWNSTREAM)

        utterances = sum(isinstance(frame, PCMUtteranceFrame) for frame in emitted)
        if utterances != SYNTHETIC_PROOF_TURNS:
            raise RuntimeError(
                "synthetic Silero proof expected "
                f"{SYNTHETIC_PROOF_TURNS} utterances, observed {utterances}"
            )

        activity_before_echo = cast(
            "dict[str, int]",
            metrics.snapshot()["audio_activity"],
        )
        starts_before_echo = activity_before_echo["utterances_started"]
        interruptions = activity_before_echo["interruption_signals"]
        if interruptions != SYNTHETIC_PROOF_TURNS:
            raise RuntimeError(
                "synthetic Silero proof expected "
                f"{SYNTHETIC_PROOF_TURNS} interruptions, observed {interruptions}"
            )
        playback_state.begin_context()
        playback_state.reserve(len(playback_pcm_s16le) / 2 / 24_000)
        echo_chunks = 0
        for chunk in _pcm_chunks(speech_pcm_s16le, frames_per_chunk=320):
            echo_chunks += 1
            await segmenter.process_frame(
                _input_audio_frame(chunk, sample_rate=16_000),
                FrameDirection.DOWNSTREAM,
            )
        playback_state.end_context()

        snapshot = metrics.snapshot()
        activity = cast("dict[str, int]", snapshot["audio_activity"])
        echo_turns = activity["utterances_started"] - starts_before_echo
        suppressed = activity["playback_suppressed_chunks"]
        if echo_turns != 0 or suppressed != echo_chunks:
            raise RuntimeError(
                "synthetic playback echo was not fully suppressed: "
                f"echo_turns={echo_turns}, suppressed={suppressed}, chunks={echo_chunks}"
            )
        return {
            "speech_utterances": utterances,
            "interruption_signals": interruptions,
            "playback_echo_turns": echo_turns,
            "playback_suppressed_chunks": suppressed,
            "confidence": cast("dict[str, int | float]", snapshot["vad_analysis"]),
        }
    finally:
        await segmenter.cleanup()


def _input_audio_frame(audio: bytes, *, sample_rate: int) -> InputAudioRawFrame:
    from pipecat.frames.frames import InputAudioRawFrame

    return InputAudioRawFrame(
        audio=audio,
        sample_rate=sample_rate,
        num_channels=1,
    )


def _pcm_chunks(pcm_s16le: bytes, *, frames_per_chunk: int) -> list[bytes]:
    chunk_bytes = frames_per_chunk * 2
    return [
        pcm_s16le[offset : offset + chunk_bytes]
        for offset in range(0, len(pcm_s16le), chunk_bytes)
        if len(pcm_s16le[offset : offset + chunk_bytes]) == chunk_bytes
    ]


async def prove_real_model_pipeline(
    config: RuntimeConfig,
    pcm_s16le: bytes,
    *,
    generator: TextGenerator,
    synthesizer: SpeechSynthesizer,
    recognizer: SpeechRecognizer,
) -> dict[str, object]:
    """Execute real providers through Pipecat and one Flecs semantic turn."""

    from pipecat.frames.frames import (
        EndFrame,
        ErrorFrame,
        LLMTextFrame,
        TranscriptionFrame,
        TTSAudioRawFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.utils.asyncio.task_manager import TaskManager
    from pipecat.workers.base_worker import WorkerParams

    from simo.adapters.pipecat.deterministic import FrameCollector
    from simo.adapters.pipecat.inference import (
        LocalSTTProcessor,
        LocalTextInferenceProcessor,
        PCMUtteranceFrame,
    )
    from simo.adapters.pipecat.observer import PipecatSemanticObserver
    from simo.adapters.pipecat.qwen_tts import QwenMLXTTSService
    from simo.adapters.pipecat.semantic_turn import SemanticTurnProcessor
    from simo.context import NativeContextEngine
    from simo.knowledge import refresh_knowledge_graph
    from simo.observation import (
        BoundedTranscriptMailbox,
        FinalTranscriptObservationBridge,
    )
    from simo.operations import RuntimeMetrics

    metrics = RuntimeMetrics()
    with NativeContextEngine(
        queue_capacity=config.queue_capacity,
        max_segments=config.max_segments,
        library_path=config.core_library,
    ) as engine:
        knowledge = refresh_knowledge_graph(engine, config.repository)
        mailbox = BoundedTranscriptMailbox(capacity=config.queue_capacity)
        bridge = FinalTranscriptObservationBridge(mailbox)
        semantic = SemanticTurnProcessor(
            engine,
            bridge,
            mailbox,
            max_prompt_chars=config.context_max_chars,
        )
        semantic_collector = FrameCollector()
        audio_collector = FrameCollector()
        pipeline = Pipeline(
            [
                LocalSTTProcessor(recognizer, metrics=metrics),
                semantic,
                LocalTextInferenceProcessor(generator, max_tokens=48, metrics=metrics),
                semantic_collector,
                QwenMLXTTSService(
                    synthesizer,
                    metrics=metrics,
                    model=config.tts.model_id,
                    voice=config.tts_voice,
                    sample_rate=24_000,
                ),
                audio_collector,
            ]
        )
        worker = PipelineWorker(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16_000,
                audio_out_sample_rate=24_000,
            ),
            observers=[PipecatSemanticObserver(bridge=bridge)],
            enable_rtvi=False,
            enable_turn_tracking=False,
            idle_timeout_secs=None,
        )
        await worker.queue_frames(
            [
                PCMUtteranceFrame(
                    audio=pcm_s16le,
                    sample_rate=16_000,
                    user_id="synthetic-proof",
                    timestamp=f"synthetic-proof-turn-{turn}",
                )
                for turn in range(SYNTHETIC_PROOF_TURNS)
            ]
            + [
                EndFrame(),
            ]
        )
        await worker.run(WorkerParams(task_manager=TaskManager()))

        frames = (*semantic_collector.frames, *audio_collector.frames)
        errors = [frame for frame in frames if isinstance(frame, ErrorFrame)]
        if errors:
            raise RuntimeError(f"real model pipeline emitted {len(errors)} error frame(s)")
        counts = {
            "transcriptions": sum(isinstance(frame, TranscriptionFrame) for frame in frames),
            "semantic_turns": semantic.injection_count,
            "text_frames": sum(isinstance(frame, LLMTextFrame) for frame in frames),
            "audio_frames": sum(isinstance(frame, TTSAudioRawFrame) for frame in frames),
        }
        if (
            counts["transcriptions"] < SYNTHETIC_PROOF_TURNS
            or counts["semantic_turns"] != SYNTHETIC_PROOF_TURNS
            or counts["text_frames"] < SYNTHETIC_PROOF_TURNS
            or counts["audio_frames"] < SYNTHETIC_PROOF_TURNS
            or semantic.injection_count != SYNTHETIC_PROOF_TURNS
        ):
            raise RuntimeError(
                "real model pipeline did not complete one semantic turn: "
                f"counts={counts}, injections={semantic.injection_count}, "
                f"semantic_frames={[type(frame).__name__ for frame in semantic_collector.frames]}, "
                f"audio_frames={[type(frame).__name__ for frame in audio_collector.frames]}"
            )
        audio_bytes = sum(
            len(frame.audio) for frame in frames if isinstance(frame, TTSAudioRawFrame)
        )
        snapshot = engine.snapshot()
        observer = bridge.stats()
        mailbox_stats = mailbox.stats()

    return {
        **counts,
        "turns": SYNTHETIC_PROOF_TURNS,
        "tts_audio_bytes": audio_bytes,
        "context_injections": semantic.injection_count,
        "world_revision": int(snapshot["revision"]),
        "knowledge_concepts": knowledge.concepts,
        "knowledge_links": knowledge.links,
        "observer_accepted": observer.accepted,
        "observer_duplicates": observer.duplicate,
        "observer_mailbox_dropped": mailbox_stats.dropped,
        "metrics": cast(object, metrics.snapshot()["stages"]),
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
