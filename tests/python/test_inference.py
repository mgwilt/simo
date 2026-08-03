from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

from pipecat.frames.frames import ErrorFrame, LLMTextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from simo.adapters.pipecat.inference import (
    LocalSTTProcessor,
    LocalTextInferenceProcessor,
    PCMUtteranceFrame,
)
from simo.adapters.pipecat.semantic_turn import (
    ContextItem,
    SemanticContextSnapshot,
    SemanticTurnFrame,
)
from simo.inference import MLXTextGenerator, ParakeetMLXRecognizer


class FakeStream:
    def __init__(self, text: str) -> None:
        self.result = SimpleNamespace(text=text)
        self.audio: object | None = None

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def add_audio(self, audio: object) -> None:
        self.audio = audio


class FakeParakeetModel:
    def __init__(self, text: str = "hello from parakeet") -> None:
        self.preprocessor_config = SimpleNamespace(sample_rate=16_000)
        self.stream = FakeStream(text)

    def transcribe_stream(self) -> FakeStream:
        return self.stream


class InferenceBoundaryTests(unittest.TestCase):
    def test_parakeet_uses_streaming_session_and_normalizes_pcm(self) -> None:
        model = FakeParakeetModel()
        loads: list[str] = []
        recognizer = ParakeetMLXRecognizer(
            Path("/models/parakeet"),
            model_loader=lambda path: loads.append(path) or model,
            array_factory=lambda values: values.tolist(),
        )
        pcm = b"\x00\x80\x00\x00\xff\x7f"
        text = asyncio.run(recognizer.transcribe(pcm, 16_000))
        self.assertEqual("hello from parakeet", text)
        self.assertEqual(["/models/parakeet"], loads)
        self.assertAlmostEqual(-1.0, model.stream.audio[0])  # type: ignore[index]
        self.assertAlmostEqual(32767 / 32768, model.stream.audio[2])  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "expects 16000"):
            asyncio.run(recognizer.transcribe(pcm, 24_000))

    def test_mlx_text_generator_is_lazy_and_bounded(self) -> None:
        calls: list[dict[str, object]] = []

        def generate(model: object, tokenizer: object, **kwargs: object) -> str:
            calls.append(kwargs)
            return " response "

        generator = MLXTextGenerator(
            Path("/models/qwen"),
            model_loader=lambda path: (f"model:{path}", "tokenizer"),
            generate_function=generate,
        )
        self.assertEqual(
            "response",
            asyncio.run(generator.generate("prompt", max_tokens=32)),
        )
        self.assertEqual(32, calls[0]["max_tokens"])
        self.assertFalse(calls[0]["verbose"])


class FakeRecognizer:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error

    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str:
        if self.error:
            raise self.error
        return "recognized speech"


class FakeGenerator:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, int]] = []

    async def generate(self, prompt: str, *, max_tokens: int) -> str:
        self.prompts.append((prompt, max_tokens))
        return "context-aware reply"


class PipecatInferenceProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_emits_final_transcription_and_bounds_errors(self) -> None:
        frames: list[object] = []
        processor = LocalSTTProcessor(FakeRecognizer())

        async def collect(frame: object, direction: FrameDirection) -> None:
            frames.append(frame)

        processor.push_frame = collect  # type: ignore[method-assign]
        utterance = PCMUtteranceFrame(b"\x00\x00", 16_000, "user-1", "now")
        await processor.process_frame(utterance, FrameDirection.DOWNSTREAM)
        self.assertEqual(1, len(frames))
        self.assertIsInstance(frames[0], TranscriptionFrame)
        self.assertTrue(frames[0].finalized)  # type: ignore[union-attr]

        failed: list[object] = []
        error_processor = LocalSTTProcessor(FakeRecognizer(error=RuntimeError("bad")))

        async def collect_error(frame: object, direction: FrameDirection) -> None:
            failed.append(frame)

        error_processor.push_frame = collect_error  # type: ignore[method-assign]
        await error_processor.process_frame(utterance, FrameDirection.DOWNSTREAM)
        self.assertIsInstance(failed[0], ErrorFrame)

    async def test_text_processor_injects_snapshot_once_and_emits_llm_frames(self) -> None:
        generator = FakeGenerator()
        processor = LocalTextInferenceProcessor(generator, max_tokens=64)
        frames: list[object] = []

        async def collect(frame: object, direction: FrameDirection) -> None:
            frames.append(frame)

        processor.push_frame = collect  # type: ignore[method-assign]
        snapshot = SemanticContextSnapshot(
            1,
            (ContextItem(1, "user", "remember blue", True, 1.0),),
        )
        turn = SemanticTurnFrame("turn-1", "what color?", snapshot, "context-block")
        await processor.process_frame(turn, FrameDirection.DOWNSTREAM)
        self.assertEqual(1, len(generator.prompts))
        prompt, max_tokens = generator.prompts[0]
        self.assertEqual(1, prompt.count("context-block"))
        self.assertIn("Current user: what color?", prompt)
        self.assertEqual(64, max_tokens)
        self.assertEqual(1, sum(isinstance(frame, LLMTextFrame) for frame in frames))


if __name__ == "__main__":
    unittest.main()
