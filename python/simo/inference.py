"""Replaceable local inference contracts and lazy MLX implementations."""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Protocol


class SpeechRecognizer(Protocol):
    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str: ...


class TextGenerator(Protocol):
    async def generate(self, prompt: str, *, max_tokens: int) -> str: ...


@dataclass(frozen=True, slots=True)
class AudioChunk:
    pcm_s16le: bytes
    sample_rate: int


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str) -> AsyncIterator[AudioChunk]: ...


class ParakeetMLXRecognizer:
    """Lazy Parakeet-MLX streaming-session adapter for one PCM utterance."""

    def __init__(
        self,
        model_path: Path,
        *,
        model_loader: Callable[[str], Any] | None = None,
        array_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        self._model_path = model_path
        self._model_loader = model_loader
        self._array_factory = array_factory
        self._model: Any | None = None

    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str:
        if not pcm_s16le or len(pcm_s16le) % 2:
            raise ValueError("Parakeet input must be non-empty 16-bit PCM")
        return await asyncio.to_thread(self._transcribe_sync, pcm_s16le, sample_rate)

    def _transcribe_sync(self, pcm_s16le: bytes, sample_rate: int) -> str:
        import numpy as np

        model = self._load_model()
        required_rate = int(model.preprocessor_config.sample_rate)
        if sample_rate != required_rate:
            raise ValueError(
                f"Parakeet expects {required_rate} Hz PCM, received {sample_rate} Hz"
            )
        samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32) / 32768.0
        array_factory = self._array_factory
        if array_factory is None:
            import mlx.core as mx

            array_factory = mx.array
        with model.transcribe_stream() as stream:
            stream.add_audio(array_factory(samples))
            text = str(stream.result.text).strip()
        return text

    def _load_model(self) -> Any:
        if self._model is None:
            loader = self._model_loader
            if loader is None:
                from parakeet_mlx import from_pretrained

                loader = from_pretrained
            self._model = loader(str(self._model_path))
        return self._model


class MLXTextGenerator:
    """Lazy MLX-LM text generation behind Simo's provider-neutral contract."""

    def __init__(
        self,
        model_path: Path,
        *,
        model_loader: Callable[[str], tuple[Any, Any]] | None = None,
        generate_function: Callable[..., str] | None = None,
    ) -> None:
        self._model_path = model_path
        self._model_loader = model_loader
        self._generate_function = generate_function
        self._loaded: tuple[Any, Any] | None = None

    async def generate(self, prompt: str, *, max_tokens: int) -> str:
        if not prompt.strip():
            raise ValueError("text inference prompt must not be empty")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        return await asyncio.to_thread(self._generate_sync, prompt, max_tokens)

    def _generate_sync(self, prompt: str, max_tokens: int) -> str:
        if self._loaded is None:
            loader = self._model_loader
            if loader is None:
                from mlx_lm import load

                loader = load
            loaded = loader(str(self._model_path))
            self._loaded = (loaded[0], loaded[1])
        generate_function = self._generate_function
        if generate_function is None:
            from mlx_lm import generate

            generate_function = generate
        model, tokenizer = self._loaded
        formatted_prompt = _format_chat_prompt(tokenizer, prompt)
        return str(
            generate_function(
                model,
                tokenizer,
                prompt=formatted_prompt,
                max_tokens=max_tokens,
                verbose=False,
            )
        ).strip()


class MLXAudioSynthesizer:
    """Lazy Qwen3-TTS streaming adapter with bounded cross-thread delivery."""

    _END = object()

    def __init__(
        self,
        model_path: Path,
        *,
        voice: str = "Aiden",
        streaming_interval_s: float = 0.32,
        max_tokens: int = 1_200,
        queue_capacity: int = 4,
        model_loader: Callable[[str], Any] | None = None,
        audio_converter: Callable[[Any], bytes] | None = None,
    ) -> None:
        if not voice.strip():
            raise ValueError("voice must not be empty")
        if streaming_interval_s <= 0 or max_tokens <= 0 or queue_capacity <= 0:
            raise ValueError("TTS bounds must be positive")
        self._model_path = model_path
        self._voice = voice
        self._streaming_interval_s = streaming_interval_s
        self._max_tokens = max_tokens
        self._queue_capacity = queue_capacity
        self._model_loader = model_loader
        self._audio_converter = audio_converter
        self._model: Any | None = None

    async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
        if not text.strip():
            raise ValueError("TTS text must not be empty")
        chunks: queue.Queue[AudioChunk | Exception | object] = queue.Queue(
            self._queue_capacity
        )
        cancelled = threading.Event()
        producer = asyncio.create_task(
            asyncio.to_thread(self._produce, text, chunks, cancelled)
        )
        try:
            while True:
                item = await asyncio.to_thread(chunks.get)
                if item is self._END:
                    break
                if isinstance(item, Exception):
                    raise item
                if not isinstance(item, AudioChunk):
                    raise TypeError("invalid MLX-Audio chunk")
                yield item
        finally:
            cancelled.set()
            try:
                await asyncio.wait_for(producer, timeout=5.0)
            except TimeoutError:
                producer.cancel()

    def _produce(
        self,
        text: str,
        chunks: queue.Queue[AudioChunk | Exception | object],
        cancelled: threading.Event,
    ) -> None:
        try:
            model = self._load_model()
            results = model.generate(
                text=text,
                voice=self._voice,
                stream=True,
                streaming_interval=self._streaming_interval_s,
                max_tokens=self._max_tokens,
                verbose=False,
            )
            for result in results:
                if cancelled.is_set():
                    break
                converter = self._audio_converter or _float_audio_to_pcm_s16le
                chunk = AudioChunk(converter(result.audio), int(result.sample_rate))
                if chunk.pcm_s16le and not self._bounded_put(chunks, chunk, cancelled):
                    break
        except Exception as error:
            self._bounded_put(chunks, error, cancelled)
        finally:
            self._bounded_put(chunks, self._END, cancelled, final=True)

    def _load_model(self) -> Any:
        if self._model is None:
            loader = self._model_loader
            if loader is None:
                from mlx_audio.tts.utils import load_model

                self._model = load_model(self._model_path)
            else:
                self._model = loader(str(self._model_path))
        return self._model

    @staticmethod
    def _bounded_put(
        chunks: queue.Queue[AudioChunk | Exception | object],
        value: AudioChunk | Exception | object,
        cancelled: threading.Event,
        *,
        final: bool = False,
    ) -> bool:
        while final or not cancelled.is_set():
            try:
                chunks.put(value, timeout=0.05)
                return True
            except queue.Full:
                if final and cancelled.is_set():
                    try:
                        chunks.get_nowait()
                    except queue.Empty:
                        pass
        return False


def _float_audio_to_pcm_s16le(audio: Any) -> bytes:
    import numpy as np

    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def _format_chat_prompt(tokenizer: Any, prompt: str) -> Any:
    """Use a model's chat template while keeping raw-tokenizer compatibility."""

    apply_template = getattr(tokenizer, "apply_chat_template", None)
    if not callable(apply_template):
        return prompt
    messages = [{"role": "user", "content": prompt}]
    try:
        return apply_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
            enable_thinking=False,
        )
    except TypeError:
        return apply_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
        )
