"""Persisted deterministic conversation runtime for Simo aliases."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import cast

from pipecat.frames.frames import LLMTextFrame, TTSTextFrame

from simo.adapters.pipecat.deterministic import run_deterministic_pipeline
from simo.config import RuntimeConfig
from simo.context import ContextParticipant, ConversationContextScope, NativeContextEngine
from simo.knowledge import refresh_knowledge_graph
from simo.memory import SafeMemoryLearner, refresh_memory_graph
from simo.persistence import (
    ConversationEventType,
    SimoDataError,
    SimoStore,
    TranscriptTurn,
)


@dataclass(frozen=True, slots=True)
class PersistedConversationResult:
    conversation_id: str
    turns_written: int
    event_count: int
    transcript: tuple[TranscriptTurn, ...]
    world_revision: int

    def as_dict(self) -> dict[str, object]:
        result = cast(dict[str, object], asdict(self))
        result["transcript"] = [item.as_dict() for item in self.transcript]
        return result


class PersistedConversationRuntime:
    """Run synthetic turns through Pipecat/Flecs and persist speech-stage truth."""

    def __init__(self, store: SimoStore, config: RuntimeConfig) -> None:
        self._store = store
        self._config = config

    async def run(
        self,
        alias_id: str,
        user_turns: list[str],
        *,
        conversation_id: str | None = None,
        complete: bool = False,
    ) -> PersistedConversationResult:
        selected = [turn.strip() for turn in user_turns if turn.strip()]
        if not selected:
            raise ValueError("talk requires at least one non-empty turn")
        alias = self._store.get_alias(alias_id)
        if conversation_id is None:
            detail = self._store.create_conversation(alias_id)
        else:
            detail = self._store.resume_conversation(conversation_id, alias_id=alias_id)
        selected_conversation_id = detail.conversation.conversation_id
        human = self._store.add_participant(
            selected_conversation_id,
            "human:local",
            kind="human",
            display_name="Local user",
        )
        alias_participant_id = f"alias:{alias_id}"
        alias_participant = self._store.add_participant(
            selected_conversation_id,
            alias_participant_id,
            kind="alias",
            alias_id=alias_id,
            display_name=alias.display_name,
        )
        current_detail = self._store.get_conversation(selected_conversation_id)
        scope = ConversationContextScope(
            alias_id,
            selected_conversation_id,
            alias_participant.participant_id,
            tuple(
                ContextParticipant(
                    participant.participant_id,
                    participant.kind,
                    participant.alias_id,
                    participant.display_name,
                    participant.transport_participant_id,
                )
                for participant in current_detail.participants
            ),
        )
        transcript_before = self._store.transcript(selected_conversation_id)
        learner = SafeMemoryLearner(self._store)
        participant_ids = {participant.participant_id for participant in scope.participants}

        with NativeContextEngine(
            queue_capacity=self._config.queue_capacity,
            max_segments=self._config.max_segments,
            scope=scope,
            library_path=self._config.core_library,
        ) as engine:
            refresh_knowledge_graph(engine, self._config.repository)
            refresh_memory_graph(engine, self._store, alias_id, participant_ids)
            for turn in transcript_before:
                engine.enqueue_transcript(turn.participant_id, turn.text, True)
                engine.tick()

            for user_text in selected:
                user_event = self._store.append_event(
                    selected_conversation_id,
                    ConversationEventType.USER_TRANSCRIPT_FINAL,
                    participant_id=human.participant_id,
                    text=user_text,
                    metadata={"source": "synthetic-cli"},
                )
                learner.learn_event(alias_id, human.participant_id, user_event)
                refresh_memory_graph(engine, self._store, alias_id, participant_ids)
                result = await run_deterministic_pipeline(
                    engine,
                    [user_text],
                    speaker_id=human.participant_id,
                    max_prompt_chars=self._config.context_max_chars,
                    max_context_age_ms=self._config.context_max_age_ms,
                )
                generated_frames = [
                    frame for frame in result.frames if isinstance(frame, LLMTextFrame)
                ]
                spoken_frames = [
                    frame for frame in result.frames if isinstance(frame, TTSTextFrame)
                ]
                if len(generated_frames) != 1 or len(spoken_frames) != 1:
                    raise SimoDataError(
                        "deterministic conversation requires one generated and spoken frame"
                    )
                generated = generated_frames[0]
                spoken = spoken_frames[0]
                version_metadata: dict[str, object] = {
                    "llm_frame_id": generated.id,
                    "tts_context_id": spoken.context_id,
                }
                self._store.append_event(
                    selected_conversation_id,
                    ConversationEventType.ASSISTANT_GENERATED,
                    participant_id=alias_participant_id,
                    text=generated.text,
                    persona_version=alias.active_persona_version,
                    runtime_profile_version=alias.active_runtime_profile_version,
                    metadata=version_metadata,
                )
                self._store.append_event(
                    selected_conversation_id,
                    ConversationEventType.ASSISTANT_TTS_SUBMITTED,
                    participant_id=alias_participant_id,
                    text=generated.text,
                    persona_version=alias.active_persona_version,
                    runtime_profile_version=alias.active_runtime_profile_version,
                    metadata=version_metadata,
                )
                self._store.append_event(
                    selected_conversation_id,
                    ConversationEventType.ASSISTANT_SPOKEN,
                    participant_id=alias_participant_id,
                    text=spoken.text,
                    persona_version=alias.active_persona_version,
                    runtime_profile_version=alias.active_runtime_profile_version,
                    metadata={**version_metadata, "will_be_spoken": spoken.will_be_spoken},
                )
                engine.enqueue_transcript(alias_participant_id, spoken.text, True)
                engine.tick()

            revision_value = cast(object, engine.snapshot()["revision"])
            if not isinstance(revision_value, int):
                raise SimoDataError("native context revision must be an integer")
            world_revision = revision_value

        if complete:
            self._store.complete_conversation(selected_conversation_id)
        persisted = self._store.get_conversation(selected_conversation_id)
        transcript = self._store.transcript(selected_conversation_id)
        return PersistedConversationResult(
            selected_conversation_id,
            len(selected),
            len(persisted.events),
            transcript,
            world_revision,
        )
