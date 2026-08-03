"""Pipecat TTS service for Simo's Qwen3-TTS MLX-Audio boundary."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame
from pipecat.services.tts_service import TTSService

from simo.inference import SpeechSynthesizer
from simo.operations import RuntimeMetrics


class QwenMLXTTSService(TTSService):
    def __init__(
        self,
        synthesizer: SpeechSynthesizer,
        *,
        metrics: RuntimeMetrics | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._synthesizer = synthesizer
        self._runtime_metrics = metrics

    async def run_tts(
        self,
        text: str,
        context_id: str,
    ) -> AsyncGenerator[Frame, None]:
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
                if token and not first_output:
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
            if token:
                metrics.finish_stage(token, error=failed)
