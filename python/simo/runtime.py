"""Process lifecycle owners for deterministic and live Simo modes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from pipecat.frames.frames import LLMTextFrame, TTSAudioRawFrame

from simo.adapters.pipecat.deterministic import run_deterministic_pipeline
from simo.config import RuntimeConfig
from simo.context import NativeContextEngine
from simo.knowledge import refresh_knowledge_graph


@dataclass(frozen=True, slots=True)
class HeadlessResult:
    snapshot: dict[str, object]
    stats: dict[str, int]
    pipeline: dict[str, int]
    knowledge: dict[str, int]


class HeadlessRuntime:
    """Own the native world for one deterministic no-model execution."""

    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config

    async def run(self, transcripts: Iterable[str]) -> HeadlessResult:
        selected = [text for text in transcripts if text.strip()]
        with NativeContextEngine(
            queue_capacity=self._config.queue_capacity,
            max_segments=self._config.max_segments,
            library_path=self._config.core_library,
        ) as engine:
            knowledge = refresh_knowledge_graph(engine, self._config.repository)
            result = await run_deterministic_pipeline(
                engine,
                selected,
                max_prompt_chars=self._config.context_max_chars,
                max_context_age_ms=self._config.context_max_age_ms,
            )
            return HeadlessResult(
                snapshot=engine.snapshot(),
                stats=asdict(engine.stats()),
                pipeline={
                    "context_injections": result.injection_count,
                    "observation_accepted": result.observation_accepted,
                    "observation_duplicates": result.observation_duplicates,
                    "observation_mailbox_dropped": result.observer_mailbox_dropped,
                    "observation_mailbox_queued": result.observer_mailbox_queued,
                    "llm_text_frames": sum(
                        isinstance(frame, LLMTextFrame) for frame in result.frames
                    ),
                    "tts_audio_frames": sum(
                        isinstance(frame, TTSAudioRawFrame) for frame in result.frames
                    ),
                },
                knowledge={
                    "revision": knowledge.revision,
                    "concepts": knowledge.concepts,
                    "links": knowledge.links,
                    "removed": knowledge.removed,
                },
            )
