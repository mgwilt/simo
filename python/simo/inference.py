"""Replaceable local inference contracts and lazy MLX implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

class SpeechRecognizer(Protocol):
    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str: ...


class TextGenerator(Protocol):
    async def generate(self, prompt: str, *, max_tokens: int) -> str: ...


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
            self._loaded = loader(str(self._model_path))
        generate_function = self._generate_function
        if generate_function is None:
            from mlx_lm import generate

            generate_function = generate
        model, tokenizer = self._loaded
        return str(
            generate_function(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                verbose=False,
            )
        ).strip()
