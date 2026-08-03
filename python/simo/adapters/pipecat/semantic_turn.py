"""Pipecat processors for immutable Flecs context injection per user turn."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pipecat.frames.frames import (
    DataFrame,
    Frame,
    InterimTranscriptionFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from simo.context import NativeContextEngine
from simo.observation import BoundedTranscriptMailbox, FinalTranscriptObservationBridge


@dataclass(frozen=True, slots=True)
class ContextItem:
    sequence: int
    speaker: str
    text: str
    is_final: bool
    salience: float


@dataclass(frozen=True, slots=True)
class SemanticContextSnapshot:
    revision: int
    items: tuple[ContextItem, ...]
    captured_monotonic_ns: int = field(default_factory=time.monotonic_ns)

    @classmethod
    def from_native(cls, value: dict[str, Any]) -> "SemanticContextSnapshot":
        return cls(
            revision=int(value["revision"]),
            items=tuple(
                ContextItem(
                    sequence=int(item["sequence"]),
                    speaker=str(item["speaker"]),
                    text=str(item["text"]),
                    is_final=bool(item["is_final"]),
                    salience=float(item["salience"]),
                )
                for item in value["items"]
            ),
        )

    def require_fresh(self, max_age_ms: int) -> None:
        if max_age_ms <= 0:
            raise ValueError("max_age_ms must be positive")
        age_ns = time.monotonic_ns() - self.captured_monotonic_ns
        if age_ns > max_age_ms * 1_000_000:
            raise ValueError(f"semantic context snapshot exceeds {max_age_ms} ms")


@dataclass
class SemanticTurnFrame(DataFrame):
    """One immutable context value selected for one inference turn."""

    turn_id: str
    user_text: str
    context: SemanticContextSnapshot
    prompt: str


class SemanticTurnProcessor(FrameProcessor):
    """Advance Flecs and inject exactly one bounded snapshot per final transcript."""

    def __init__(
        self,
        engine: NativeContextEngine,
        bridge: FinalTranscriptObservationBridge,
        mailbox: BoundedTranscriptMailbox,
        *,
        max_prompt_chars: int = 8_000,
    ) -> None:
        if max_prompt_chars <= 0:
            raise ValueError("max_prompt_chars must be positive")
        super().__init__(enable_direct_mode=True)
        self._engine = engine
        self._bridge = bridge
        self._mailbox = mailbox
        self._max_prompt_chars = max_prompt_chars
        self._injected_turns: set[str] = set()

    @property
    def injection_count(self) -> int:
        return len(self._injected_turns)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if direction is not FrameDirection.DOWNSTREAM:
            return
        if isinstance(frame, InterimTranscriptionFrame):
            return
        if not isinstance(frame, TranscriptionFrame):
            return

        turn_id = str(frame.id)
        if turn_id in self._injected_turns:
            return
        self._bridge.observe(
            frame_key=turn_id,
            speaker=frame.user_id,
            text=frame.text,
            is_final=True,
        )
        observed = self._mailbox.pop(turn_id)
        if observed is None:
            speaker = frame.user_id
            text = frame.text
        else:
            speaker = observed.speaker
            text = observed.text
        self._engine.enqueue_transcript(speaker, text, True)
        self._engine.tick()
        snapshot = SemanticContextSnapshot.from_native(self._engine.snapshot())
        prompt = format_semantic_context(snapshot, max_chars=self._max_prompt_chars)
        self._injected_turns.add(turn_id)
        await self.push_frame(
            SemanticTurnFrame(
                turn_id=turn_id,
                user_text=frame.text,
                context=snapshot,
                prompt=prompt,
            ),
            direction,
        )


def format_semantic_context(
    snapshot: SemanticContextSnapshot,
    *,
    max_chars: int,
) -> str:
    """Format recent items deterministically without mutating the snapshot."""

    header = f"Simo semantic context (revision {snapshot.revision}):"
    if len(header) >= max_chars:
        return header[:max_chars]
    selected: list[str] = []
    used = len(header)
    for item in reversed(snapshot.items):
        line = f"- [{item.sequence}] {item.speaker}: {item.text}"
        added = len(line) + 1
        if used + added > max_chars:
            break
        selected.append(line)
        used += added
    selected.reverse()
    return "\n".join((header, *selected))
