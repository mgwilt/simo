"""Privacy-safe runtime metrics and structured operational events."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, TextIO

_STAGES = ("knowledge", "pipeline", "stt", "text_inference", "tts")


@dataclass(slots=True)
class _MutableStageMetrics:
    calls: int = 0
    errors: int = 0
    total_ms: float = 0.0
    last_ms: float = 0.0
    first_output_ms: float | None = None


@dataclass(frozen=True, slots=True)
class StageToken:
    stage: str
    started_ns: int


class RuntimeMetrics:
    """Collect bounded aggregate metrics without retaining media or transcript data."""

    def __init__(self, *, clock_ns: Callable[[], int] = time.perf_counter_ns) -> None:
        self._clock_ns = clock_ns
        self._started_ns = clock_ns()
        self._lock = threading.Lock()
        self._phase = "created"
        self._shutdown_reason: str | None = None
        self._clean_shutdown = False
        self._errors_total = 0
        self._world_revision = 0
        self._audio_activity: dict[str, int] = {
            "input_chunks": 0,
            "playback_suppressed_chunks": 0,
            "utterances_started": 0,
            "interruption_signals": 0,
        }
        self._vad_frames = 0
        self._vad_confidence_total = 0.0
        self._vad_max_confidence = 0.0
        self._context_queue: dict[str, int] = {
            "depth": 0,
            "dropped": 0,
            "accepted": 0,
            "processed": 0,
            "retained": 0,
        }
        self._observer_mailbox: dict[str, int] = {"depth": 0, "dropped": 0}
        self._stages = {stage: _MutableStageMetrics() for stage in _STAGES}

    def transition(self, phase: str) -> None:
        if phase not in {"starting", "ready", "stopping", "stopped"}:
            raise ValueError(f"unsupported lifecycle phase: {phase}")
        with self._lock:
            self._phase = phase

    def stop(self, reason: str, *, clean: bool) -> None:
        if reason not in {"completed", "cancelled", "failed", "interrupted"}:
            raise ValueError(f"unsupported shutdown reason: {reason}")
        with self._lock:
            self._phase = "stopped"
            self._shutdown_reason = reason
            self._clean_shutdown = clean

    def start_stage(self, stage: str) -> StageToken:
        self._require_stage(stage)
        return StageToken(stage, self._clock_ns())

    def first_output(self, token: StageToken) -> None:
        elapsed = self._elapsed_ms(token.started_ns)
        with self._lock:
            metrics = self._stages[token.stage]
            if metrics.first_output_ms is None:
                metrics.first_output_ms = elapsed

    def finish_stage(self, token: StageToken, *, error: bool = False) -> None:
        elapsed = self._elapsed_ms(token.started_ns)
        with self._lock:
            metrics = self._stages[token.stage]
            metrics.calls += 1
            metrics.total_ms += elapsed
            metrics.last_ms = elapsed
            if error:
                metrics.errors += 1
                self._errors_total += 1

    def record_error(self) -> None:
        with self._lock:
            self._errors_total += 1

    def record_user_speech_start(self, *, interruption_signaled: bool) -> None:
        with self._lock:
            self._audio_activity["utterances_started"] += 1
            if interruption_signaled:
                self._audio_activity["interruption_signals"] += 1

    def record_audio_input_chunk(self) -> None:
        with self._lock:
            self._audio_activity["input_chunks"] += 1

    def record_playback_suppressed_chunk(self) -> None:
        with self._lock:
            self._audio_activity["playback_suppressed_chunks"] += 1

    def record_vad_confidence(self, confidence: float) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("VAD confidence must be between zero and one")
        with self._lock:
            self._vad_frames += 1
            self._vad_confidence_total += confidence
            self._vad_max_confidence = max(self._vad_max_confidence, confidence)

    def update_runtime_state(
        self,
        *,
        world_revision: int,
        context_queue_depth: int,
        context_queue_dropped: int,
        context_accepted: int,
        context_processed: int,
        context_retained: int,
        observer_mailbox_depth: int,
        observer_mailbox_dropped: int,
    ) -> None:
        values = (
            world_revision,
            context_queue_depth,
            context_queue_dropped,
            context_accepted,
            context_processed,
            context_retained,
            observer_mailbox_depth,
            observer_mailbox_dropped,
        )
        if any(value < 0 for value in values):
            raise ValueError("runtime counters must not be negative")
        with self._lock:
            self._world_revision = world_revision
            self._context_queue = {
                "depth": context_queue_depth,
                "dropped": context_queue_dropped,
                "accepted": context_accepted,
                "processed": context_processed,
                "retained": context_retained,
            }
            self._observer_mailbox = {
                "depth": observer_mailbox_depth,
                "dropped": observer_mailbox_dropped,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": 1,
                "phase": self._phase,
                "shutdown_reason": self._shutdown_reason,
                "clean_shutdown": self._clean_shutdown,
                "uptime_ms": self._elapsed_ms(self._started_ns),
                "errors_total": self._errors_total,
                "world_revision": self._world_revision,
                "audio_activity": dict(self._audio_activity),
                "vad_analysis": {
                    "frames": self._vad_frames,
                    "mean_confidence": round(self._vad_confidence_total / self._vad_frames, 6)
                    if self._vad_frames
                    else 0.0,
                    "max_confidence": round(self._vad_max_confidence, 6),
                },
                "context_queue": dict(self._context_queue),
                "observer_mailbox": dict(self._observer_mailbox),
                "stages": {name: asdict(metrics) for name, metrics in self._stages.items()},
            }

    def _elapsed_ms(self, started_ns: int) -> float:
        return round(max(0, self._clock_ns() - started_ns) / 1_000_000, 3)

    def _require_stage(self, stage: str) -> None:
        if stage not in self._stages:
            raise ValueError(f"unsupported metric stage: {stage}")


class OperationalEventSink(Protocol):
    def lifecycle(self, mode: str, phase: str, *, reason: str | None = None) -> None: ...

    def failure(self, mode: str, stage: str, error: BaseException) -> None: ...

    def metrics(self, mode: str, snapshot: dict[str, Any]) -> None: ...


class NullEventSink:
    def lifecycle(self, mode: str, phase: str, *, reason: str | None = None) -> None:
        return None

    def failure(self, mode: str, stage: str, error: BaseException) -> None:
        return None

    def metrics(self, mode: str, snapshot: dict[str, Any]) -> None:
        return None


class JsonEventSink:
    """Write a fixed-schema JSONL event stream that excludes content and audio."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def lifecycle(self, mode: str, phase: str, *, reason: str | None = None) -> None:
        payload: dict[str, Any] = {"mode": mode, "phase": phase}
        if reason is not None:
            payload["reason"] = reason
        self._write("lifecycle", payload)

    def failure(self, mode: str, stage: str, error: BaseException) -> None:
        self._write(
            "failure",
            {"mode": mode, "stage": stage, "error_type": type(error).__name__},
        )

    def metrics(self, mode: str, snapshot: dict[str, Any]) -> None:
        self._write("metrics", {"mode": mode, "metrics": snapshot})

    def _write(self, event: str, fields: dict[str, Any]) -> None:
        payload = {
            "schema": "simo.event.v1",
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **fields,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._lock:
            self._stream.write(encoded + "\n")
            self._stream.flush()
