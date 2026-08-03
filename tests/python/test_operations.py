from __future__ import annotations

import asyncio
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from simo.config import RuntimeConfig
from simo.operations import JsonEventSink, RuntimeMetrics
from simo.runtime import HeadlessRuntime


class FakeEngine:
    instance: FakeEngine | None = None

    def __init__(self, **kwargs: object) -> None:
        self.closed = False
        FakeEngine.instance = self

    def __enter__(self) -> FakeEngine:
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True


class RuntimeMetricsTests(unittest.TestCase):
    def test_metrics_are_aggregate_and_measure_first_output(self) -> None:
        now = [1_000_000_000]
        metrics = RuntimeMetrics(clock_ns=lambda: now[0])
        metrics.transition("starting")
        token = metrics.start_stage("tts")
        now[0] += 25_000_000
        metrics.first_output(token)
        now[0] += 15_000_000
        metrics.finish_stage(token)
        metrics.record_user_speech_start(interruption_signaled=True)
        metrics.record_audio_input_chunk()
        metrics.record_playback_suppressed_chunk()
        metrics.record_vad_confidence(0.25)
        metrics.record_vad_confidence(0.75)
        metrics.update_runtime_state(
            world_revision=3,
            context_queue_depth=1,
            context_queue_dropped=2,
            context_accepted=4,
            context_processed=3,
            context_retained=3,
            observer_mailbox_depth=0,
            observer_mailbox_dropped=1,
        )
        metrics.stop("completed", clean=True)

        snapshot = metrics.snapshot()
        self.assertEqual(3, snapshot["world_revision"])
        self.assertEqual(2, snapshot["context_queue"]["dropped"])
        self.assertEqual(1, snapshot["observer_mailbox"]["dropped"])
        self.assertEqual(1, snapshot["stages"]["tts"]["calls"])
        self.assertEqual(1, snapshot["audio_activity"]["utterances_started"])
        self.assertEqual(1, snapshot["audio_activity"]["interruption_signals"])
        self.assertEqual(1, snapshot["audio_activity"]["input_chunks"])
        self.assertEqual(1, snapshot["audio_activity"]["playback_suppressed_chunks"])
        self.assertEqual(
            {"frames": 2, "mean_confidence": 0.5, "max_confidence": 0.75},
            snapshot["vad_analysis"],
        )
        self.assertEqual(25.0, snapshot["stages"]["tts"]["first_output_ms"])
        self.assertEqual(40.0, snapshot["stages"]["tts"]["last_ms"])
        self.assertTrue(snapshot["clean_shutdown"])

    def test_failure_event_omits_exception_message(self) -> None:
        stream = io.StringIO()
        sink = JsonEventSink(stream)
        sink.failure("live", "stt", RuntimeError("private transcript"))

        event = json.loads(stream.getvalue())
        self.assertEqual("failure", event["event"])
        self.assertEqual("RuntimeError", event["error_type"])
        self.assertNotIn("private transcript", stream.getvalue())


class CancellationLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_closes_engine_and_emits_clean_shutdown(self) -> None:
        entered_pipeline = asyncio.Event()

        async def block_pipeline(*args: object, **kwargs: object) -> object:
            entered_pipeline.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        stream = io.StringIO()
        runtime = HeadlessRuntime(
            RuntimeConfig.from_environment({}),
            events=JsonEventSink(stream),
        )
        knowledge = SimpleNamespace(revision=1, concepts=1, links=0, removed=0)
        with (
            patch("simo.runtime.NativeContextEngine", FakeEngine),
            patch("simo.runtime.refresh_knowledge_graph", return_value=knowledge),
            patch("simo.runtime.run_deterministic_pipeline", new=block_pipeline),
        ):
            task = asyncio.create_task(runtime.run(["private transcript"]))
            await entered_pipeline.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertIsNotNone(FakeEngine.instance)
        self.assertTrue(FakeEngine.instance.closed)  # type: ignore[union-attr]
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        stopped = [event for event in events if event.get("phase") == "stopped"]
        self.assertEqual("cancelled", stopped[-1]["reason"])
        metrics = [event for event in events if event["event"] == "metrics"][-1]
        self.assertTrue(metrics["metrics"]["clean_shutdown"])
        self.assertEqual("cancelled", metrics["metrics"]["shutdown_reason"])
        self.assertNotIn("private transcript", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
