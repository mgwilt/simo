"""Bounded, framework-neutral observation filtering."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from simo.context import DropPolicy, EnqueueResult


class TranscriptSink(Protocol):
    def enqueue_transcript(
        self, speaker: str, text: str, is_final: bool = True
    ) -> EnqueueResult: ...


class TranscriptObservationSink(Protocol):
    def enqueue_observation(
        self,
        frame_key: str,
        speaker: str,
        text: str,
        is_final: bool = True,
    ) -> EnqueueResult: ...


@dataclass(frozen=True, slots=True)
class ObservedTranscript:
    frame_key: str
    speaker: str
    text: str
    is_final: bool
    sequence: int


@dataclass(frozen=True, slots=True)
class ObservationMailboxStats:
    accepted: int
    dropped: int
    queued: int


class BoundedTranscriptMailbox:
    """Bound observer run-ahead without granting it Flecs mutation authority."""

    def __init__(
        self,
        *,
        capacity: int = 256,
        drop_policy: DropPolicy = DropPolicy.DROP_OLDEST,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._drop_policy = drop_policy
        self._events: OrderedDict[str, ObservedTranscript] = OrderedDict()
        self._lock = Lock()
        self._sequence = 0
        self._accepted = 0
        self._dropped = 0

    def enqueue_observation(
        self,
        frame_key: str,
        speaker: str,
        text: str,
        is_final: bool = True,
    ) -> EnqueueResult:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            if len(self._events) >= self._capacity:
                self._dropped += 1
                if self._drop_policy is DropPolicy.DROP_NEWEST:
                    return EnqueueResult(False, sequence)
                self._events.popitem(last=False)
            self._events[frame_key] = ObservedTranscript(
                frame_key,
                speaker,
                text,
                is_final,
                sequence,
            )
            self._accepted += 1
            return EnqueueResult(True, sequence)

    def pop(self, frame_key: str) -> ObservedTranscript | None:
        with self._lock:
            return self._events.pop(frame_key, None)

    def stats(self) -> ObservationMailboxStats:
        with self._lock:
            return ObservationMailboxStats(
                accepted=self._accepted,
                dropped=self._dropped,
                queued=len(self._events),
            )


@dataclass(frozen=True, slots=True)
class ObservationStats:
    accepted: int
    duplicate: int
    filtered: int
    rejected: int


class FinalTranscriptObservationBridge:
    """Deduplicate frame observations and perform one bounded sink call."""

    def __init__(
        self,
        sink: TranscriptSink | TranscriptObservationSink,
        *,
        dedupe_capacity: int = 2_048,
    ) -> None:
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

        enqueue_observation = getattr(self._sink, "enqueue_observation", None)
        if enqueue_observation is not None:
            result = enqueue_observation(frame_key, speaker, text, True)
        else:
            result = self._sink.enqueue_transcript(speaker, text, True)  # type: ignore[union-attr]
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
