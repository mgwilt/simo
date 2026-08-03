from __future__ import annotations

import asyncio
import io
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from pipecat.frames.frames import EndFrame, Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.workers.runner import WorkerRunner

from simo.config import RunMode, RuntimeConfig
from simo.operations import JsonEventSink
from simo.runtime import LiveRuntime


class Endpoint(FrameProcessor):
    def __init__(self, name: str) -> None:
        super().__init__(name=name, enable_direct_mode=True)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)


class FakeTransport:
    def __init__(self) -> None:
        self.input_processor = Endpoint("FakeMic")
        self.output_processor = Endpoint("FakeSpeaker")
        self.closed = False

    def input(self) -> FrameProcessor:
        return self.input_processor

    def output(self) -> FrameProcessor:
        return self.output_processor

    async def close(self) -> None:
        self.closed = True


class RecordingRunner:
    def __init__(self, *, block: bool = False) -> None:
        self.workers: list[object] = []
        self.entered = asyncio.Event()
        self.block = block

    async def add_workers(self, *workers: object) -> None:
        self.workers.extend(workers)

    async def run(self) -> None:
        self.entered.set()
        if self.block:
            await asyncio.Event().wait()


class OneShotRunner(RecordingRunner):
    async def run(self) -> None:
        actual = WorkerRunner(handle_sigint=False)
        await actual.add_workers(*self.workers)  # type: ignore[arg-type]

        async def end_pipeline() -> None:
            await asyncio.sleep(0.01)
            await self.workers[0].queue_frames([EndFrame()])  # type: ignore[union-attr]

        await asyncio.gather(actual.run(), end_pipeline())


class LiveRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def make_runtime(
        self,
        transport: FakeTransport,
        runner: RecordingRunner,
        events: io.StringIO,
    ) -> LiveRuntime:
        config = RuntimeConfig.from_environment({}, mode=RunMode.LIVE)
        return LiveRuntime(
            config,
            events=JsonEventSink(events),
            transport_factory=lambda selected: transport,
            recognizer_factory=lambda selected: object(),
            generator_factory=lambda selected: object(),
            synthesizer_factory=lambda selected: object(),
            runner_factory=lambda: runner,
        )

    async def test_builds_ordered_live_pipeline_without_loading_models(self) -> None:
        transport = FakeTransport()
        runner = OneShotRunner()
        events = io.StringIO()
        runtime = self.make_runtime(transport, runner, events)

        result = await runtime.run()

        self.assertTrue(transport.closed)
        self.assertEqual(1, len(runner.workers))
        worker = runner.workers[0]
        self.assertEqual(16_000, worker.params.audio_in_sample_rate)  # type: ignore[union-attr]
        self.assertEqual(24_000, worker.params.audio_out_sample_rate)  # type: ignore[union-attr]
        user_pipeline = worker.pipeline.processors[1]  # type: ignore[union-attr]
        names = [
            type(processor).__name__ for processor in user_pipeline.processors[1:-1]
        ]
        self.assertEqual(
            [
                "Endpoint",
                "SileroUtteranceProcessor",
                "LocalSTTProcessor",
                "SemanticTurnProcessor",
                "LocalTextInferenceProcessor",
                "QwenMLXTTSService",
                "Endpoint",
            ],
            names,
        )
        segmenter = next(
            processor
            for processor in user_pipeline.processors
            if type(processor).__name__ == "SileroUtteranceProcessor"
        )
        self.assertEqual(0.5, segmenter._analyzer.params.confidence)
        self.assertEqual(0.0, segmenter._analyzer.params.min_volume)
        self.assertTrue(result.operations["clean_shutdown"])
        self.assertEqual("completed", result.operations["shutdown_reason"])

    async def test_cancellation_closes_transport_and_emits_terminal_metrics(
        self,
    ) -> None:
        transport = FakeTransport()
        runner = RecordingRunner(block=True)
        events = io.StringIO()
        runtime = self.make_runtime(transport, runner, events)
        task = asyncio.create_task(runtime.run())
        await runner.entered.wait()

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(transport.closed)
        parsed = [json.loads(line) for line in events.getvalue().splitlines()]
        terminal = [event for event in parsed if event["event"] == "metrics"][-1]
        self.assertEqual("cancelled", terminal["metrics"]["shutdown_reason"])
        self.assertTrue(terminal["metrics"]["clean_shutdown"])


if __name__ == "__main__":
    unittest.main()
