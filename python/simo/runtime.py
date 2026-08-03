"""Process lifecycle owners for deterministic and live Simo modes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from simo.config import RuntimeConfig
from simo.context import NativeContextEngine


@dataclass(frozen=True, slots=True)
class HeadlessResult:
    snapshot: dict[str, object]
    stats: dict[str, int]


class HeadlessRuntime:
    """Own the native world for one deterministic no-model execution."""

    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config

    def run(self, transcripts: Iterable[str]) -> HeadlessResult:
        with NativeContextEngine(
            queue_capacity=self._config.queue_capacity,
            max_segments=self._config.max_segments,
            library_path=self._config.core_library,
        ) as engine:
            for text in transcripts:
                if text.strip():
                    engine.enqueue_transcript("user", text, True)
            engine.tick()
            return HeadlessResult(
                snapshot=engine.snapshot(),
                stats=asdict(engine.stats()),
            )
