"""Pipecat TTS service for Simo's Qwen3-TTS MLX-Audio boundary."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

from simo.inference import SpeechSynthesizer
from simo.operations import RuntimeMetrics


class QwenMLXTTSService(TTSService):
    def __init__(
        self,
        synthesizer: SpeechSynthesizer,
        *,
        metrics: RuntimeMetrics | None = None,
        model: str = "qwen3-tts",
        voice: str | None = None,
        settings: TTSSettings | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("push_start_frame", True)
        kwargs.setdefault("push_stop_frames", True)
        kwargs.setdefault("stop_frame_timeout_s", 0.75)
        super().__init__(
            settings=settings or TTSSettings(model=model, voice=voice, language=None),
            **kwargs,
        )
        self._synthesizer = synthesizer
        self._runtime_metrics = metrics

    async def run_tts(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        text: str,
        context_id: str,
    ) -> AsyncGenerator[Frame | None, None]:
        metrics = self._runtime_metrics
        token = metrics.start_stage("tts") if metrics else None
        first_output = False
        failed = False
        try:
            async for chunk in self._synthesizer.synthesize(text):
                if not chunk.pcm_s16le or len(chunk.pcm_s16le) % 2:
                    raise ValueError("MLX-Audio returned invalid 16-bit PCM")
                if chunk.sample_rate <= 0:
                    raise ValueError("MLX-Audio returned an invalid sample rate")
                if metrics is not None and token is not None and not first_output:
                    metrics.first_output(token)
                    first_output = True
                yield TTSAudioRawFrame(
                    audio=chunk.pcm_s16le,
                    sample_rate=chunk.sample_rate,
                    num_channels=1,
                    context_id=context_id,
                )
        except Exception as error:
            failed = True
            yield ErrorFrame(error=f"Qwen MLX TTS failed: {error}", exception=error)
        finally:
            if metrics is not None and token is not None:
                metrics.finish_stage(token, error=failed)
