"""Persisted alias runtime using LiveKit Agents as the realtime session owner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import cast

from livekit import rtc
from livekit.agents import llm, vad
from livekit.agents.voice.events import CloseEvent, ConversationItemAddedEvent

from simo.adapters.livekit import (
    LiveKitSessionEventBridge,
    build_livekit_agent_session,
)
from simo.config import RuntimeConfig
from simo.context import ContextParticipant, ConversationContextScope, NativeContextEngine
from simo.inference import (
    MLXAudioSynthesizer,
    MLXTextGenerator,
    ParakeetMLXRecognizer,
    SpeechRecognizer,
    SpeechSynthesizer,
    TextGenerator,
)
from simo.knowledge import refresh_knowledge_graph
from simo.livekit_room import LiveKitRoomConfig
from simo.memory import refresh_memory_graph
from simo.persistence import SimoStore, TranscriptTurn


@dataclass(frozen=True, slots=True)
class LiveKitAliasRunRequest:
    alias_id: str
    remote_participant_id: str
    remote_display_name: str
    remote_transport_identity: str
    remote_alias_id: str | None = None
    conversation_id: str | None = None
    opening_instructions: str | None = None
    max_spoken_turns: int | None = None
    max_duration_s: float | None = None
    complete_on_close: bool = True

    def __post_init__(self) -> None:
        required = {
            "alias ID": self.alias_id,
            "remote participant ID": self.remote_participant_id,
            "remote display name": self.remote_display_name,
            "remote transport identity": self.remote_transport_identity,
        }
        for label, value in required.items():
            if not value.strip():
                raise ValueError(f"{label} must not be empty")
        if self.max_spoken_turns is not None and self.max_spoken_turns <= 0:
            raise ValueError("max spoken turns must be positive")
        if self.max_duration_s is not None and self.max_duration_s <= 0:
            raise ValueError("max duration must be positive")


@dataclass(frozen=True, slots=True)
class LiveKitAliasRunResult:
    alias_id: str
    conversation_id: str
    local_transport_identity: str
    local_participant_sid: str
    remote_transport_identity: str
    event_count: int
    transcript_turns: int
    spoken_turns: int
    world_revision: int
    close_reason: str
    raw_audio_retained: bool
    session_events: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


RecognizerFactory = Callable[[RuntimeConfig], SpeechRecognizer]
GeneratorFactory = Callable[[RuntimeConfig], TextGenerator]
SynthesizerFactory = Callable[[RuntimeConfig], SpeechSynthesizer]
RoomFactory = Callable[[], rtc.Room]


class LiveKitAliasRuntime:
    """Own one persisted alias conversation, isolated Flecs world, and AgentSession."""

    def __init__(
        self,
        store: SimoStore,
        config: RuntimeConfig,
        room_config: LiveKitRoomConfig,
        *,
        recognizer_factory: RecognizerFactory | None = None,
        generator_factory: GeneratorFactory | None = None,
        synthesizer_factory: SynthesizerFactory | None = None,
        room_factory: RoomFactory | None = None,
        loaded_vad: vad.VAD | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._room_config = room_config
        self._recognizer_factory = recognizer_factory or _create_recognizer
        self._generator_factory = generator_factory or _create_generator
        self._synthesizer_factory = synthesizer_factory or _create_synthesizer
        self._room_factory = room_factory or rtc.Room
        self._loaded_vad = loaded_vad

    async def run(self, request: LiveKitAliasRunRequest) -> LiveKitAliasRunResult:
        self._validate_room_scope(request)
        alias = self._store.get_alias(request.alias_id)
        persona = next(
            item
            for item in self._store.list_persona_versions(request.alias_id)
            if item.version == alias.active_persona_version
        )
        detail = (
            self._store.create_conversation(request.alias_id)
            if request.conversation_id is None
            else self._store.resume_conversation(
                request.conversation_id,
                alias_id=request.alias_id,
            )
        )
        conversation_id = detail.conversation.conversation_id
        alias_participant_id = f"alias:{request.alias_id}"
        self._store.bind_participant_transport(
            conversation_id,
            alias_participant_id,
            self._room_config.participant_identity,
        )
        remote_kind = "alias" if request.remote_alias_id is not None else "external"
        self._store.add_participant(
            conversation_id,
            request.remote_participant_id,
            kind=remote_kind,
            alias_id=request.remote_alias_id,
            display_name=request.remote_display_name,
            transport_participant_id=request.remote_transport_identity,
        )
        current = self._store.get_conversation(conversation_id)
        scope = ConversationContextScope(
            request.alias_id,
            conversation_id,
            alias_participant_id,
            tuple(
                ContextParticipant(
                    participant.participant_id,
                    participant.kind,
                    participant.alias_id,
                    participant.display_name,
                    participant.transport_participant_id,
                )
                for participant in current.participants
            ),
        )
        participant_ids = {participant.participant_id for participant in scope.participants}
        room = self._room_factory()
        bridge: LiveKitSessionEventBridge | None = None
        session_started = False
        close_reason = "unknown"
        termination_reason: str | None = None
        spoken_turns = 0
        local_sid = ""
        close_task: asyncio.Task[None] | None = None

        with NativeContextEngine(
            queue_capacity=self._config.queue_capacity,
            max_segments=self._config.max_segments,
            scope=scope,
            library_path=self._config.core_library,
        ) as engine:
            refresh_knowledge_graph(engine, self._config.repository)
            refresh_memory_graph(engine, self._store, request.alias_id, participant_ids)
            transcript = self._store.transcript(conversation_id)
            for turn in transcript:
                engine.enqueue_transcript(turn.participant_id, turn.text, True)
                engine.tick()
            bridge = LiveKitSessionEventBridge(
                self._store,
                engine,
                alias_id=request.alias_id,
                conversation_id=conversation_id,
                alias_participant_id=alias_participant_id,
                remote_participant_id=request.remote_participant_id,
                remote_transport_id=request.remote_transport_identity,
                participant_ids=participant_ids,
                capacity=self._config.queue_capacity,
            )
            components = build_livekit_agent_session(
                self._config,
                engine,
                persona_instructions=persona.instructions,
                remote_transport_identity=request.remote_transport_identity,
                recognizer=self._recognizer_factory(self._config),
                generator=self._generator_factory(self._config),
                synthesizer=self._synthesizer_factory(self._config),
                event_sink=bridge,
                chat_context=build_livekit_history(transcript, alias_participant_id),
                loaded_vad=self._loaded_vad,
            )
            closed = asyncio.Event()
            close_error: list[object] = []

            def on_close(event: CloseEvent) -> None:
                nonlocal close_reason
                close_reason = termination_reason or event.reason.value
                if event.error is not None:
                    close_error.append(event.error)
                closed.set()

            def on_conversation_item(event: ConversationItemAddedEvent) -> None:
                nonlocal close_task, spoken_turns, termination_reason
                item = event.item
                if not isinstance(item, llm.ChatMessage) or item.role != "assistant":
                    return
                spoken_turns += 1
                if (
                    request.max_spoken_turns is not None
                    and spoken_turns >= request.max_spoken_turns
                ):
                    termination_reason = "max_spoken_turns"
                    close_task = asyncio.create_task(
                        components.session.aclose(),
                        name="simo-livekit-max-turn-close",
                    )

            components.session.on(  # pyright: ignore[reportUnknownMemberType]
                "close", on_close
            )
            components.session.on(  # pyright: ignore[reportUnknownMemberType]
                "conversation_item_added", on_conversation_item
            )
            bridge.start()
            bridge.attach(components.session)
            try:
                await room.connect(
                    self._room_config.server_url,
                    self._room_config.issue_join_token(),
                    options=rtc.RoomOptions(auto_subscribe=True),
                )
                local_sid = room.local_participant.sid
                session_started = True
                await components.session.start(  # pyright: ignore[reportUnknownMemberType]
                    components.agent,
                    room=room,
                    room_options=components.room_options,
                    record=False,
                )
                if request.opening_instructions:
                    components.session.generate_reply(
                        instructions=request.opening_instructions,
                    )
                if request.max_duration_s is None:
                    await closed.wait()
                else:
                    try:
                        await asyncio.wait_for(closed.wait(), timeout=request.max_duration_s)
                    except TimeoutError:
                        termination_reason = "duration_limit"
                        await components.session.aclose()
                if close_error:
                    raise RuntimeError("LiveKit AgentSession closed with a model or media error")
            finally:
                if session_started and not closed.is_set():
                    await components.session.aclose()
                if close_task is not None:
                    await close_task
                await bridge.aclose()
                if room.isconnected():
                    await room.disconnect()
            snapshot = engine.snapshot()
            revision = snapshot.get("revision")
            if not isinstance(revision, int):
                raise TypeError("LiveKit alias context revision must be an integer")
            world_revision = revision

        if request.complete_on_close:
            self._store.complete_conversation(conversation_id)
        persisted = self._store.get_conversation(conversation_id)
        final_transcript = self._store.transcript(conversation_id)
        if not local_sid:
            raise RuntimeError("LiveKit local participant SID was unavailable")
        event_stats = bridge.stats()
        return LiveKitAliasRunResult(
            request.alias_id,
            conversation_id,
            self._room_config.participant_identity,
            local_sid,
            request.remote_transport_identity,
            len(persisted.events),
            len(final_transcript),
            spoken_turns,
            world_revision,
            close_reason,
            persisted.conversation.raw_audio_retained,
            cast(dict[str, int], asdict(event_stats)),
        )

    def _validate_room_scope(self, request: LiveKitAliasRunRequest) -> None:
        if self._room_config.allowed_remote_identities != frozenset(
            {request.remote_transport_identity}
        ):
            raise ValueError("LiveKit alias runtime requires exactly one declared remote identity")


def build_livekit_history(
    transcript: tuple[TranscriptTurn, ...],
    local_participant_id: str,
) -> llm.ChatContext:
    """Rehydrate only final user and actually spoken assistant turns."""

    context = llm.ChatContext.empty()
    for turn in transcript:
        context.add_message(
            role="assistant" if turn.participant_id == local_participant_id else "user",
            content=turn.text,
            interrupted=turn.interrupted,
        )
    return context


def _create_recognizer(config: RuntimeConfig) -> SpeechRecognizer:
    return ParakeetMLXRecognizer(config.stt.local_path)


def _create_generator(config: RuntimeConfig) -> TextGenerator:
    return MLXTextGenerator(config.text.local_path)


def _create_synthesizer(config: RuntimeConfig) -> SpeechSynthesizer:
    return MLXAudioSynthesizer(
        config.tts.local_path,
        voice=config.tts_voice,
        streaming_interval_s=config.tts_streaming_interval_s,
    )
