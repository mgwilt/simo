"""Bounded LiveKit Agents event projection into Simo persistence and Flecs."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

from livekit.agents import llm
from livekit.agents.voice import AgentSession
from livekit.agents.voice.events import (
    ConversationItemAddedEvent,
    UserInputTranscribedEvent,
)

from simo.context import NativeContextEngine
from simo.memory import SafeMemoryLearner, refresh_memory_graph
from simo.persistence import ConversationEventType, SimoDataError, SimoStore

_Stage = Literal["generated", "tts_submitted", "committed_user", "spoken"]


@dataclass(frozen=True, slots=True)
class _QueuedSessionEvent:
    stage: _Stage
    text: str
    participant_id: str
    interrupted: bool
    item_id: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class SessionEventStats:
    accepted: int
    dropped: int
    processed: int
    failed: int
    queued: int


class LiveKitSessionEventBridge:
    """Keep LiveKit callbacks non-blocking while serializing durable state changes."""

    def __init__(
        self,
        store: SimoStore,
        engine: NativeContextEngine,
        *,
        alias_id: str,
        conversation_id: str,
        alias_participant_id: str,
        remote_participant_id: str,
        remote_transport_id: str,
        participant_ids: set[str],
        capacity: int = 256,
        enable_learning: bool = True,
    ) -> None:
        if capacity <= 0:
            raise ValueError("session event capacity must be positive")
        alias = store.get_alias(alias_id)
        self._store = store
        self._engine = engine
        self._learner = SafeMemoryLearner(store) if enable_learning else None
        self._alias_id = alias_id
        self._conversation_id = conversation_id
        self._alias_participant_id = alias_participant_id
        self._remote_participant_id = remote_participant_id
        self._remote_transport_id = remote_transport_id
        self._participant_ids = set(participant_ids)
        self._persona_version = alias.active_persona_version
        self._runtime_profile_version = alias.active_runtime_profile_version
        self._queue: asyncio.Queue[_QueuedSessionEvent | None] = asyncio.Queue(capacity)
        self._transcript_speakers: OrderedDict[str, str] = OrderedDict()
        self._worker: asyncio.Task[None] | None = None
        self._attached_session: AgentSession[object] | None = None
        self._accepted = 0
        self._dropped = 0
        self._processed = 0
        self._failed = 0
        self._last_error: Exception | None = None

    def start(self) -> None:
        if self._worker is not None:
            raise RuntimeError("LiveKit session event bridge already started")
        self._worker = asyncio.create_task(self._run(), name="simo-livekit-session-events")

    def attach(self, session: AgentSession[object]) -> None:
        if self._attached_session is not None:
            raise RuntimeError("LiveKit session event bridge already attached")
        session.on(  # pyright: ignore[reportUnknownMemberType]
            "user_input_transcribed", self.observe_user_transcription
        )
        session.on(  # pyright: ignore[reportUnknownMemberType]
            "conversation_item_added", self.observe_conversation_item
        )
        self._attached_session = session

    def detach(self) -> None:
        session = self._attached_session
        if session is None:
            return
        session.off(  # pyright: ignore[reportUnknownMemberType]
            "user_input_transcribed", self.observe_user_transcription
        )
        session.off(  # pyright: ignore[reportUnknownMemberType]
            "conversation_item_added", self.observe_conversation_item
        )
        self._attached_session = None

    def observe_user_transcription(self, event: UserInputTranscribedEvent) -> None:
        """Remember transport attribution; committed chat items own transcript truth."""

        if not event.is_final or not event.transcript.strip():
            return
        item_id = event.item_id or event.transcript.strip()
        self._transcript_speakers[item_id] = event.speaker_id or self._remote_transport_id
        self._transcript_speakers.move_to_end(item_id)
        while len(self._transcript_speakers) > 256:
            self._transcript_speakers.popitem(last=False)

    def observe_conversation_item(self, event: ConversationItemAddedEvent) -> None:
        item = event.item
        if not isinstance(item, llm.ChatMessage):
            return
        text = item.text_content
        if not text:
            return
        if item.role == "user":
            transport_speaker = self._transcript_speakers.pop(
                item.id,
                self._transcript_speakers.pop(text, self._remote_transport_id),
            )
            self._enqueue(
                _QueuedSessionEvent(
                    "committed_user",
                    text,
                    self._remote_participant_id,
                    item.interrupted,
                    item.id,
                    {
                        "source": "livekit-agents",
                        "transport_participant_id": transport_speaker,
                    },
                )
            )
        elif item.role == "assistant":
            self._enqueue(
                _QueuedSessionEvent(
                    "spoken",
                    text,
                    self._alias_participant_id,
                    item.interrupted,
                    item.id,
                    {"source": "livekit-agents", "chat_item_id": item.id},
                )
            )

    def assistant_generated(self, text: str, request_id: str) -> None:
        if text.strip():
            self._enqueue(
                _QueuedSessionEvent(
                    "generated",
                    text,
                    self._alias_participant_id,
                    False,
                    request_id,
                    {"source": "livekit-agents", "llm_request_id": request_id},
                )
            )

    def tts_submitted(self, text: str, request_id: str) -> None:
        if text.strip():
            self._enqueue(
                _QueuedSessionEvent(
                    "tts_submitted",
                    text,
                    self._alias_participant_id,
                    False,
                    request_id,
                    {"source": "livekit-agents", "tts_request_id": request_id},
                )
            )

    def _enqueue(self, event: _QueuedSessionEvent) -> None:
        if self._queue.full():
            try:
                _ = self._queue.get_nowait()
                self._queue.task_done()
                self._dropped += 1
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(event)
        self._accepted += 1

    async def drain(self) -> None:
        await self._queue.join()
        if self._last_error is not None:
            raise SimoDataError("LiveKit session event persistence failed") from self._last_error

    async def aclose(self) -> None:
        self.detach()
        worker = self._worker
        if worker is None:
            return
        await self.drain()
        self._queue.put_nowait(None)
        await worker
        self._worker = None

    def stats(self) -> SessionEventStats:
        return SessionEventStats(
            self._accepted,
            self._dropped,
            self._processed,
            self._failed,
            self._queue.qsize(),
        )

    async def _run(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                if event is None:
                    return
                self._persist(event)
                self._processed += 1
            except Exception as error:
                self._failed += 1
                self._last_error = error
            finally:
                self._queue.task_done()

    def _persist(self, event: _QueuedSessionEvent) -> None:
        event_type = {
            "generated": ConversationEventType.ASSISTANT_GENERATED,
            "tts_submitted": ConversationEventType.ASSISTANT_TTS_SUBMITTED,
            "committed_user": ConversationEventType.USER_TRANSCRIPT_FINAL,
            "spoken": ConversationEventType.ASSISTANT_SPOKEN,
        }[event.stage]
        versions = event.stage != "committed_user"
        persisted = self._store.append_event(
            self._conversation_id,
            event_type,
            participant_id=event.participant_id,
            text=event.text,
            interrupted=event.interrupted,
            persona_version=self._persona_version if versions else None,
            runtime_profile_version=self._runtime_profile_version if versions else None,
            metadata={**event.metadata, "source_item_id": event.item_id},
        )
        if event.stage not in {"committed_user", "spoken"}:
            return
        self._engine.enqueue_transcript(event.participant_id, event.text, True)
        self._engine.tick()
        if event.stage == "committed_user" and self._learner is not None:
            self._learner.learn_event(self._alias_id, event.participant_id, persisted)
            refresh_memory_graph(
                self._engine,
                self._store,
                self._alias_id,
                self._participant_ids,
            )
