"""Bounded, framework-neutral observation filtering."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from simo.context import EnqueueResult


class TranscriptSink(Protocol):
    def enqueue_transcript(
        self, speaker: str, text: str, is_final: bool = True
    ) -> EnqueueResult: ...


@dataclass(frozen=True, slots=True)
class ObservationStats:
    accepted: int
    duplicate: int
    filtered: int
    rejected: int


class FinalTranscriptObservationBridge:
    """Deduplicate frame observations and perform one bounded sink call."""

    def __init__(self, sink: TranscriptSink, *, dedupe_capacity: int = 2_048) -> None:
        if dedupe_capacity <= 0:
            raise ValueError("dedupe_capacity must be positive")
        self._sink = sink
        self._dedupe_capacity = dedupe_capacity
        self._seen_order: deque[str] = deque()
        self._seen: set[str] = set()
        self._lock = Lock()
        self._accepted = 0
        self._duplicate = 0
        self._filtered = 0
        self._rejected = 0

    def observe(
        self,
        *,
        frame_key: str,
        speaker: str,
        text: str,
        is_final: bool,
    ) -> EnqueueResult | None:
        if not is_final or not text.strip():
            with self._lock:
                self._filtered += 1
            return None

        with self._lock:
            if frame_key in self._seen:
                self._duplicate += 1
                return None
            self._seen.add(frame_key)
            self._seen_order.append(frame_key)
            if len(self._seen_order) > self._dedupe_capacity:
                self._seen.remove(self._seen_order.popleft())

        result = self._sink.enqueue_transcript(speaker, text, True)
        with self._lock:
            if result.accepted:
                self._accepted += 1
            else:
                self._rejected += 1
        return result

    def stats(self) -> ObservationStats:
        with self._lock:
            return ObservationStats(
                accepted=self._accepted,
                duplicate=self._duplicate,
                filtered=self._filtered,
                rejected=self._rejected,
            )
