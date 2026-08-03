"""Local durable identity and conversation storage for Simo."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, cast
from uuid import UUID, uuid4

import yaml
from platformdirs import user_data_path

from simo.config import (
    PARAKEET_STT_MODEL,
    PARAKEET_STT_REVISION,
    QWEN_TEXT_MODEL,
    QWEN_TEXT_REVISION,
    QWEN_TTS_MODEL,
    QWEN_TTS_REVISION,
)

SCHEMA_VERSION: Final = 1
ALIAS_EXPORT_SCHEMA: Final = "simo.alias-export.v1"
ALIAS_MANIFEST_SCHEMA: Final = "simo.alias.v1"
MAX_ALIAS_EXPORT_BYTES: Final = 64 * 1024 * 1024


class SimoDataError(RuntimeError):
    """Base error for local identity and conversation persistence."""


class RecordNotFoundError(SimoDataError):
    """Raised when a requested persisted record does not exist."""


class RecordConflictError(SimoDataError):
    """Raised when an operation would overwrite an existing record."""


class ConversationEventType(StrEnum):
    """Version-one persisted conversation event vocabulary."""

    USER_TRANSCRIPT_FINAL = "user.transcript.final"
    ASSISTANT_GENERATED = "assistant.generated"
    ASSISTANT_TTS_SUBMITTED = "assistant.tts.submitted"
    ASSISTANT_SPOKEN = "assistant.spoken"
    TURN_INTERRUPTED = "turn.interrupted"
    CONVERSATION_RESUMED = "conversation.resumed"
    CONVERSATION_COMPLETED = "conversation.completed"


@dataclass(frozen=True, slots=True)
class AliasRecord:
    alias_id: str
    display_name: str
    created_at: str
    updated_at: str
    active_persona_version: int
    active_runtime_profile_version: int
    knowledge_root: str

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class PersonaVersion:
    alias_id: str
    version: int
    created_at: str
    summary: str
    instructions: str
    parent_version: int | None
    source: str

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class RuntimeProfileVersion:
    alias_id: str
    version: int
    created_at: str
    profile: dict[str, object]
    parent_version: int | None
    source: str

    def as_dict(self) -> dict[str, object]:
        result = cast(dict[str, object], asdict(self))
        result["profile"] = dict(self.profile)
        return result


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    raw_audio_retained: bool

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class ParticipantRecord:
    conversation_id: str
    participant_id: str
    kind: str
    alias_id: str | None
    display_name: str
    transport_participant_id: str | None
    joined_at: str

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class ConversationEvent:
    event_id: str
    conversation_id: str
    sequence: int
    participant_id: str | None
    event_type: str
    wall_time: str
    monotonic_ns: int
    text: str | None
    interrupted: bool
    persona_version: int | None
    runtime_profile_version: int | None
    metadata: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        result = cast(dict[str, object], asdict(self))
        result["metadata"] = dict(self.metadata)
        return result


@dataclass(frozen=True, slots=True)
class ConversationDetail:
    conversation: ConversationRecord
    participants: tuple[ParticipantRecord, ...]
    events: tuple[ConversationEvent, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "conversation": self.conversation.as_dict(),
            "participants": [participant.as_dict() for participant in self.participants],
            "events": [event.as_dict() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    sequence: int
    participant_id: str
    display_name: str
    kind: str
    text: str
    wall_time: str
    interrupted: bool
    event_type: str

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


def resolve_data_root(
    explicit: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the local data root without creating it."""

    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    values = os.environ if environ is None else environ
    configured = values.get("SIMO_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return user_data_path("Simo", appauthor=False).resolve()


def default_runtime_profile() -> dict[str, object]:
    """Return the immutable initial Mac-native profile for a new alias."""

    return {
        "schema": "simo.runtime-profile.v1",
        "models": {
            "tts": {"id": QWEN_TTS_MODEL, "revision": QWEN_TTS_REVISION},
            "stt": {"id": PARAKEET_STT_MODEL, "revision": PARAKEET_STT_REVISION},
            "text": {"id": QWEN_TEXT_MODEL, "revision": QWEN_TEXT_REVISION},
        },
        "voice": "Aiden",
        "vad": {
            "confidence": 0.1,
            "start_ms": 32,
            "stop_ms": 320,
            "pre_roll_ms": 200,
            "maximum_utterance_seconds": 30.0,
        },
        "response": {"maximum_tokens": 48},
        "prompt": "Hold a natural, concise, context-aware conversation.",
    }


class SimoStore:
    """Own Simo's versioned local SQLite and alias-bundle storage."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = resolve_data_root(root)
        self.aliases_root = self.root / "aliases"
        self.database_path = self.root / "simo.sqlite3"
        self._writer_lock = threading.RLock()
        self.aliases_root.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def create_alias(
        self,
        display_name: str,
        *,
        persona_summary: str = "A curious, attentive conversational partner.",
        persona_instructions: str = "Speak naturally, listen closely, and preserve continuity.",
        alias_id: str | None = None,
        runtime_profile: Mapping[str, object] | None = None,
    ) -> AliasRecord:
        name = _nonempty(display_name, "display name")
        summary = _nonempty(persona_summary, "persona summary")
        instructions = _nonempty(persona_instructions, "persona instructions")
        selected_id = alias_id or str(uuid4())
        _validate_uuid(selected_id, "alias ID")
        timestamp = _utc_now()
        knowledge_root = f"aliases/{selected_id}/knowledge"
        profile = dict(runtime_profile or default_runtime_profile())
        _ensure_json_value(profile, "runtime profile")
        record = AliasRecord(selected_id, name, timestamp, timestamp, 1, 1, knowledge_root)
        persona = PersonaVersion(
            selected_id,
            1,
            timestamp,
            summary,
            instructions,
            None,
            "initial",
        )
        target = self.aliases_root / selected_id
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM aliases WHERE alias_id = ?", (selected_id,)
            ).fetchone():
                raise RecordConflictError(f"alias already exists: {selected_id}")
            if target.exists():
                raise RecordConflictError(f"alias directory already exists: {target}")
            connection.execute(
                """
                INSERT INTO aliases (
                    alias_id, display_name, created_at, updated_at,
                    active_persona_version, active_runtime_profile_version, knowledge_root
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.alias_id,
                    record.display_name,
                    record.created_at,
                    record.updated_at,
                    record.active_persona_version,
                    record.active_runtime_profile_version,
                    record.knowledge_root,
                ),
            )
            connection.execute(
                """
                INSERT INTO persona_versions (
                    alias_id, version, created_at, summary, instructions, parent_version, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    persona.alias_id,
                    persona.version,
                    persona.created_at,
                    persona.summary,
                    persona.instructions,
                    persona.parent_version,
                    persona.source,
                ),
            )
            connection.execute(
                """
                INSERT INTO runtime_profile_versions (
                    alias_id, version, created_at, profile_json, parent_version, source
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (selected_id, 1, timestamp, _json_dump(profile), None, "initial"),
            )
            try:
                self._write_new_alias_bundle(record, persona)
                connection.commit()
            except BaseException:
                if target.exists():
                    shutil.rmtree(target)
                raise
        return record

    def get_alias(self, alias_id: str) -> AliasRecord:
        with self._connect() as connection:
            row = cast(
                dict[str, object] | None,
                connection.execute(
                    "SELECT * FROM aliases WHERE alias_id = ?", (alias_id,)
                ).fetchone(),
            )
        if row is None:
            raise RecordNotFoundError(f"alias not found: {alias_id}")
        return _alias_from_row(row)

    def list_aliases(self) -> tuple[AliasRecord, ...]:
        with self._connect() as connection:
            rows = cast(
                list[dict[str, object]],
                connection.execute(
                    "SELECT * FROM aliases ORDER BY display_name COLLATE NOCASE, alias_id"
                ).fetchall(),
            )
        return tuple(_alias_from_row(row) for row in rows)

    def list_persona_versions(self, alias_id: str) -> tuple[PersonaVersion, ...]:
        self.get_alias(alias_id)
        with self._connect() as connection:
            rows = cast(
                list[dict[str, object]],
                connection.execute(
                    "SELECT * FROM persona_versions WHERE alias_id = ? ORDER BY version",
                    (alias_id,),
                ).fetchall(),
            )
        return tuple(_persona_from_row(row) for row in rows)

    def list_runtime_profile_versions(self, alias_id: str) -> tuple[RuntimeProfileVersion, ...]:
        self.get_alias(alias_id)
        with self._connect() as connection:
            rows = cast(
                list[dict[str, object]],
                connection.execute(
                    "SELECT * FROM runtime_profile_versions WHERE alias_id = ? ORDER BY version",
                    (alias_id,),
                ).fetchall(),
            )
        return tuple(_profile_from_row(row) for row in rows)

    def revise_persona(
        self,
        alias_id: str,
        summary: str,
        instructions: str,
        *,
        source: str = "operator",
    ) -> PersonaVersion:
        selected_summary = _nonempty(summary, "persona summary")
        selected_instructions = _nonempty(instructions, "persona instructions")
        timestamp = _utc_now()
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            alias = self._get_alias_in(connection, alias_id)
            version = alias.active_persona_version + 1
            persona = PersonaVersion(
                alias_id,
                version,
                timestamp,
                selected_summary,
                selected_instructions,
                alias.active_persona_version,
                _nonempty(source, "persona source"),
            )
            connection.execute(
                """
                INSERT INTO persona_versions (
                    alias_id, version, created_at, summary, instructions, parent_version, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alias_id,
                    version,
                    timestamp,
                    persona.summary,
                    persona.instructions,
                    persona.parent_version,
                    persona.source,
                ),
            )
            connection.execute(
                """
                UPDATE aliases
                SET active_persona_version = ?, updated_at = ?
                WHERE alias_id = ?
                """,
                (version, timestamp, alias_id),
            )
            updated = self._get_alias_in(connection, alias_id)
            self._write_persona_concept(updated, persona)
            self._write_persona_index(alias_id, self._personas_in(connection, alias_id))
            self._write_manifest(updated)
            connection.commit()
        return persona

    def revise_runtime_profile(
        self,
        alias_id: str,
        profile: Mapping[str, object],
        *,
        source: str = "operator",
    ) -> RuntimeProfileVersion:
        selected = dict(profile)
        _ensure_json_value(selected, "runtime profile")
        timestamp = _utc_now()
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            alias = self._get_alias_in(connection, alias_id)
            version = alias.active_runtime_profile_version + 1
            result = RuntimeProfileVersion(
                alias_id,
                version,
                timestamp,
                selected,
                alias.active_runtime_profile_version,
                _nonempty(source, "runtime profile source"),
            )
            connection.execute(
                """
                INSERT INTO runtime_profile_versions (
                    alias_id, version, created_at, profile_json, parent_version, source
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alias_id,
                    version,
                    timestamp,
                    _json_dump(selected),
                    result.parent_version,
                    result.source,
                ),
            )
            connection.execute(
                """
                UPDATE aliases
                SET active_runtime_profile_version = ?, updated_at = ?
                WHERE alias_id = ?
                """,
                (version, timestamp, alias_id),
            )
            self._write_manifest(self._get_alias_in(connection, alias_id))
            connection.commit()
        return result

    def create_conversation(
        self,
        alias_id: str,
        *,
        title: str | None = None,
        conversation_id: str | None = None,
    ) -> ConversationDetail:
        alias = self.get_alias(alias_id)
        selected_id = conversation_id or str(uuid4())
        _validate_uuid(selected_id, "conversation ID")
        timestamp = _utc_now()
        selected_title = title.strip() if title else f"Conversation with {alias.display_name}"
        if not selected_title:
            raise ValueError("conversation title must not be empty")
        conversation = ConversationRecord(
            selected_id,
            selected_title,
            timestamp,
            timestamp,
            "active",
            False,
        )
        participant = ParticipantRecord(
            selected_id,
            f"alias:{alias_id}",
            "alias",
            alias_id,
            alias.display_name,
            None,
            timestamp,
        )
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO conversations (
                    conversation_id, title, created_at, updated_at, status, raw_audio_retained
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.conversation_id,
                    conversation.title,
                    conversation.created_at,
                    conversation.updated_at,
                    conversation.status,
                    int(conversation.raw_audio_retained),
                ),
            )
            connection.execute(
                """
                INSERT INTO participants (
                    conversation_id, participant_id, kind, alias_id, display_name,
                    transport_participant_id, joined_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant.conversation_id,
                    participant.participant_id,
                    participant.kind,
                    participant.alias_id,
                    participant.display_name,
                    participant.transport_participant_id,
                    participant.joined_at,
                ),
            )
            connection.commit()
        return ConversationDetail(conversation, (participant,), ())

    def add_participant(
        self,
        conversation_id: str,
        participant_id: str,
        *,
        kind: str,
        display_name: str,
        alias_id: str | None = None,
        transport_participant_id: str | None = None,
    ) -> ParticipantRecord:
        selected_id = _nonempty(participant_id, "participant ID")
        selected_kind = _nonempty(kind, "participant kind")
        if selected_kind not in {"alias", "human", "external"}:
            raise ValueError("participant kind must be alias, human, or external")
        selected_name = _nonempty(display_name, "participant display name")
        if selected_kind == "alias" and alias_id is None:
            raise ValueError("alias participant requires an alias ID")
        if alias_id is not None:
            self.get_alias(alias_id)
        timestamp = _utc_now()
        participant = ParticipantRecord(
            conversation_id,
            selected_id,
            selected_kind,
            alias_id,
            selected_name,
            transport_participant_id,
            timestamp,
        )
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id = ?", (conversation_id,)
            ).fetchone():
                raise RecordNotFoundError(f"conversation not found: {conversation_id}")
            existing = cast(
                dict[str, object] | None,
                connection.execute(
                    """
                    SELECT * FROM participants
                    WHERE conversation_id = ? AND participant_id = ?
                    """,
                    (conversation_id, selected_id),
                ).fetchone(),
            )
            if existing is not None:
                current = _participant_from_row(existing)
                comparable = (
                    current.kind,
                    current.alias_id,
                    current.display_name,
                    current.transport_participant_id,
                )
                requested = (
                    participant.kind,
                    participant.alias_id,
                    participant.display_name,
                    participant.transport_participant_id,
                )
                if comparable != requested:
                    raise RecordConflictError(
                        f"participant already exists with different identity: {selected_id}"
                    )
                return current
            connection.execute(
                """
                INSERT INTO participants (
                    conversation_id, participant_id, kind, alias_id, display_name,
                    transport_participant_id, joined_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant.conversation_id,
                    participant.participant_id,
                    participant.kind,
                    participant.alias_id,
                    participant.display_name,
                    participant.transport_participant_id,
                    participant.joined_at,
                ),
            )
            connection.commit()
        return participant

    def append_event(
        self,
        conversation_id: str,
        event_type: ConversationEventType | str,
        *,
        participant_id: str | None = None,
        text: str | None = None,
        interrupted: bool = False,
        persona_version: int | None = None,
        runtime_profile_version: int | None = None,
        metadata: Mapping[str, object] | None = None,
        monotonic_ns: int | None = None,
        event_id: str | None = None,
    ) -> ConversationEvent:
        selected_type = ConversationEventType(event_type)
        if text is not None and not text.strip():
            raise ValueError("conversation event text must not be empty")
        selected_metadata = dict(metadata or {})
        _ensure_json_value(selected_metadata, "conversation event metadata")
        selected_event_id = event_id or str(uuid4())
        _validate_uuid(selected_event_id, "event ID")
        wall_time = _utc_now()
        selected_monotonic = time.monotonic_ns() if monotonic_ns is None else monotonic_ns
        if selected_monotonic < 0:
            raise ValueError("event monotonic timestamp must not be negative")
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            conversation = cast(
                dict[str, object] | None,
                connection.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone(),
            )
            if conversation is None:
                raise RecordNotFoundError(f"conversation not found: {conversation_id}")
            if (
                participant_id is not None
                and not connection.execute(
                    """
                SELECT 1 FROM participants
                WHERE conversation_id = ? AND participant_id = ?
                """,
                    (conversation_id, participant_id),
                ).fetchone()
            ):
                raise RecordNotFoundError(
                    f"participant not found in conversation: {participant_id}"
                )
            sequence_row = cast(
                dict[str, object],
                connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) AS maximum_sequence
                    FROM conversation_events WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone(),
            )
            sequence = _required_int(sequence_row, "maximum_sequence") + 1
            event = ConversationEvent(
                selected_event_id,
                conversation_id,
                sequence,
                participant_id,
                selected_type.value,
                wall_time,
                selected_monotonic,
                text.strip() if text is not None else None,
                interrupted,
                persona_version,
                runtime_profile_version,
                selected_metadata,
            )
            connection.execute(
                """
                INSERT INTO conversation_events (
                    event_id, conversation_id, sequence, participant_id, event_type,
                    wall_time, monotonic_ns, text, interrupted, persona_version,
                    runtime_profile_version, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.conversation_id,
                    event.sequence,
                    event.participant_id,
                    event.event_type,
                    event.wall_time,
                    event.monotonic_ns,
                    event.text,
                    int(event.interrupted),
                    event.persona_version,
                    event.runtime_profile_version,
                    _json_dump(event.metadata),
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (wall_time, conversation_id),
            )
            connection.commit()
        return event

    def resume_conversation(
        self, conversation_id: str, *, alias_id: str | None = None
    ) -> ConversationDetail:
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id = ?", (conversation_id,)
            ).fetchone():
                raise RecordNotFoundError(f"conversation not found: {conversation_id}")
            if (
                alias_id is not None
                and not connection.execute(
                    """
                SELECT 1 FROM participants
                WHERE conversation_id = ? AND alias_id = ?
                """,
                    (conversation_id, alias_id),
                ).fetchone()
            ):
                raise RecordConflictError(
                    f"conversation {conversation_id} does not contain alias {alias_id}"
                )
            timestamp = _utc_now()
            connection.execute(
                """
                UPDATE conversations SET status = 'active', updated_at = ?
                WHERE conversation_id = ?
                """,
                (timestamp, conversation_id),
            )
            connection.commit()
        self.append_event(
            conversation_id,
            ConversationEventType.CONVERSATION_RESUMED,
            metadata={"alias_id": alias_id} if alias_id is not None else {},
        )
        return self.get_conversation(conversation_id)

    def complete_conversation(self, conversation_id: str) -> ConversationDetail:
        self.append_event(conversation_id, ConversationEventType.CONVERSATION_COMPLETED)
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamp = _utc_now()
            cursor = connection.execute(
                """
                UPDATE conversations SET status = 'completed', updated_at = ?
                WHERE conversation_id = ?
                """,
                (timestamp, conversation_id),
            )
            if cursor.rowcount == 0:
                raise RecordNotFoundError(f"conversation not found: {conversation_id}")
            connection.commit()
        return self.get_conversation(conversation_id)

    def transcript(self, conversation_id: str) -> tuple[TranscriptTurn, ...]:
        detail = self.get_conversation(conversation_id)
        participants = {item.participant_id: item for item in detail.participants}
        selected: list[TranscriptTurn] = []
        primary_types = {
            ConversationEventType.USER_TRANSCRIPT_FINAL.value,
            ConversationEventType.ASSISTANT_SPOKEN.value,
        }
        for event in detail.events:
            if event.event_type not in primary_types or event.text is None:
                continue
            if event.participant_id is None or event.participant_id not in participants:
                raise SimoDataError(
                    f"transcript event {event.event_id} has no attributed participant"
                )
            participant = participants[event.participant_id]
            selected.append(
                TranscriptTurn(
                    event.sequence,
                    participant.participant_id,
                    participant.display_name,
                    participant.kind,
                    event.text,
                    event.wall_time,
                    event.interrupted,
                    event.event_type,
                )
            )
        return tuple(selected)

    def export_conversation(self, conversation_id: str, destination: Path | str) -> Path:
        detail = self.get_conversation(conversation_id)
        target = Path(destination).expanduser().resolve()
        if target.exists():
            raise RecordConflictError(f"export destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "schema": "simo.conversation-export.v1",
            **detail.as_dict(),
            "transcript": [item.as_dict() for item in self.transcript(conversation_id)],
        }
        _atomic_text(target, f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n")
        return target

    def list_conversations(self, alias_id: str | None = None) -> tuple[ConversationRecord, ...]:
        parameters: tuple[object, ...] = ()
        sql = "SELECT DISTINCT c.* FROM conversations c"
        if alias_id is not None:
            self.get_alias(alias_id)
            sql += " JOIN participants p ON p.conversation_id = c.conversation_id"
            sql += " WHERE p.alias_id = ?"
            parameters = (alias_id,)
        sql += " ORDER BY c.updated_at DESC, c.conversation_id"
        with self._connect() as connection:
            rows = cast(list[dict[str, object]], connection.execute(sql, parameters).fetchall())
        return tuple(_conversation_from_row(row) for row in rows)

    def get_conversation(self, conversation_id: str) -> ConversationDetail:
        with self._connect() as connection:
            row = cast(
                dict[str, object] | None,
                connection.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)
                ).fetchone(),
            )
            if row is None:
                raise RecordNotFoundError(f"conversation not found: {conversation_id}")
            participant_rows = cast(
                list[dict[str, object]],
                connection.execute(
                    "SELECT * FROM participants WHERE conversation_id = ? ORDER BY joined_at, participant_id",
                    (conversation_id,),
                ).fetchall(),
            )
            event_rows = cast(
                list[dict[str, object]],
                connection.execute(
                    "SELECT * FROM conversation_events WHERE conversation_id = ? ORDER BY sequence",
                    (conversation_id,),
                ).fetchall(),
            )
        return ConversationDetail(
            _conversation_from_row(row),
            tuple(_participant_from_row(item) for item in participant_rows),
            tuple(_event_from_row(item) for item in event_rows),
        )

    def delete_conversation(self, conversation_id: str) -> None:
        with self._writer_lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,)
            )
            if cursor.rowcount == 0:
                raise RecordNotFoundError(f"conversation not found: {conversation_id}")
            connection.commit()

    def export_alias(self, alias_id: str, destination: Path | str) -> Path:
        alias = self.get_alias(alias_id)
        personas = self.list_persona_versions(alias_id)
        profiles = self.list_runtime_profile_versions(alias_id)
        target = Path(destination).expanduser().resolve()
        if target.exists():
            raise RecordConflictError(f"export destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source_root = self.aliases_root / alias_id
        payload: dict[str, object] = {
            "schema": ALIAS_EXPORT_SCHEMA,
            "alias": alias.as_dict(),
            "personas": [item.as_dict() for item in personas],
            "runtime_profiles": [item.as_dict() for item in profiles],
        }
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("records.json", _json_dump(payload))
            for path in sorted(source_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(source_root).as_posix())
        return target

    def import_alias(self, source: Path | str) -> AliasRecord:
        archive_path = Path(source).expanduser().resolve()
        if not archive_path.is_file():
            raise RecordNotFoundError(f"alias export not found: {archive_path}")
        with tempfile.TemporaryDirectory(prefix="simo-import-", dir=self.root) as temporary:
            extracted = Path(temporary) / "alias"
            extracted.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()
                if sum(item.file_size for item in members) > MAX_ALIAS_EXPORT_BYTES:
                    raise SimoDataError("alias export exceeds the configured size bound")
                for member in members:
                    relative = PurePosixPath(member.filename)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise SimoDataError(f"unsafe alias export member: {member.filename}")
                    if relative.parts[:1] not in {
                        ("records.json",),
                        ("alias.yaml",),
                        ("knowledge",),
                    }:
                        raise SimoDataError(f"unexpected alias export member: {member.filename}")
                    if member.is_dir():
                        continue
                    destination = extracted.joinpath(*relative.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as input_file:
                        destination.write_bytes(input_file.read())
            records_path = extracted / "records.json"
            manifest_path = extracted / "alias.yaml"
            knowledge_path = extracted / "knowledge" / "index.md"
            if (
                not records_path.is_file()
                or not manifest_path.is_file()
                or not knowledge_path.is_file()
            ):
                raise SimoDataError("alias export is missing records, manifest, or OKF root")
            records = _json_object(records_path.read_text(encoding="utf-8"))
            if _required_str(records, "schema") != ALIAS_EXPORT_SCHEMA:
                raise SimoDataError("unsupported alias export schema")
            alias = _alias_from_mapping(_required_object(records, "alias"))
            _validate_uuid(alias.alias_id, "alias ID")
            manifest = _yaml_object(manifest_path.read_text(encoding="utf-8"))
            if _required_str(manifest, "schema") != ALIAS_MANIFEST_SCHEMA:
                raise SimoDataError("unsupported alias manifest schema")
            if _required_str(manifest, "alias_id") != alias.alias_id:
                raise SimoDataError("alias manifest and records disagree")
            personas = tuple(
                _persona_from_mapping(item) for item in _required_object_list(records, "personas")
            )
            profiles = tuple(
                _profile_from_mapping(item)
                for item in _required_object_list(records, "runtime_profiles")
            )
            self._validate_import_versions(alias, personas, profiles)
            target = self.aliases_root / alias.alias_id
            with self._writer_lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if (
                    connection.execute(
                        "SELECT 1 FROM aliases WHERE alias_id = ?", (alias.alias_id,)
                    ).fetchone()
                    or target.exists()
                ):
                    raise RecordConflictError(f"alias already exists: {alias.alias_id}")
                self._insert_import(connection, alias, personas, profiles)
                extracted.replace(target)
                connection.commit()
        return alias

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            version_row = cast(
                dict[str, object] | None,
                connection.execute("PRAGMA user_version").fetchone(),
            )
            if version_row is None:
                raise SimoDataError("could not read the Simo data schema version")
            version = _required_int(version_row, "user_version")
            if version not in {0, SCHEMA_VERSION}:
                raise SimoDataError(
                    f"unsupported Simo data schema {version}; expected {SCHEMA_VERSION}"
                )
            connection.executescript(_SCHEMA_SQL)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = _mapping_row_factory
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _get_alias_in(self, connection: sqlite3.Connection, alias_id: str) -> AliasRecord:
        row = cast(
            dict[str, object] | None,
            connection.execute("SELECT * FROM aliases WHERE alias_id = ?", (alias_id,)).fetchone(),
        )
        if row is None:
            raise RecordNotFoundError(f"alias not found: {alias_id}")
        return _alias_from_row(row)

    def _personas_in(
        self, connection: sqlite3.Connection, alias_id: str
    ) -> tuple[PersonaVersion, ...]:
        rows = cast(
            list[dict[str, object]],
            connection.execute(
                "SELECT * FROM persona_versions WHERE alias_id = ? ORDER BY version", (alias_id,)
            ).fetchall(),
        )
        return tuple(_persona_from_row(row) for row in rows)

    def _write_new_alias_bundle(self, alias: AliasRecord, persona: PersonaVersion) -> None:
        alias_root = self.aliases_root / alias.alias_id
        (alias_root / "knowledge" / "personas").mkdir(parents=True)
        _atomic_text(
            alias_root / "knowledge" / "index.md",
            '---\nokf_version: "0.2"\n---\n# Alias knowledge\n\n'
            "- [Personas](personas/) - Versioned identity and speaking-style concepts.\n",
        )
        self._write_persona_concept(alias, persona)
        self._write_persona_index(alias.alias_id, (persona,))
        self._write_manifest(alias)

    def _write_manifest(self, alias: AliasRecord) -> None:
        manifest: dict[str, object] = {
            "schema": ALIAS_MANIFEST_SCHEMA,
            "alias_id": alias.alias_id,
            "display_name": alias.display_name,
            "created_at": alias.created_at,
            "updated_at": alias.updated_at,
            "active_persona_version": alias.active_persona_version,
            "active_runtime_profile_version": alias.active_runtime_profile_version,
            "knowledge_bundle": "knowledge",
        }
        _atomic_text(
            self.aliases_root / alias.alias_id / "alias.yaml",
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        )

    def _write_persona_concept(self, alias: AliasRecord, persona: PersonaVersion) -> None:
        metadata: dict[str, object] = {
            "type": "Persona",
            "title": f"{alias.display_name} persona v{persona.version}",
            "description": persona.summary,
            "tags": ["alias", "persona"],
            "status": "draft",
            "generated": {"by": "process:simo", "at": persona.created_at},
            "simo": {
                "profile_version": 1,
                "alias_id": alias.alias_id,
                "persona_version": persona.version,
                "parent_version": persona.parent_version,
                "source": persona.source,
            },
        }
        frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
        body = (
            f"---\n{frontmatter}\n---\n# Persona\n\n{persona.summary}\n\n"
            f"## Instructions\n\n{persona.instructions}\n"
        )
        _atomic_text(
            self.aliases_root
            / alias.alias_id
            / "knowledge"
            / "personas"
            / f"v{persona.version:04d}.md",
            body,
        )

    def _write_persona_index(self, alias_id: str, personas: tuple[PersonaVersion, ...]) -> None:
        lines = ["# Personas", ""]
        lines.extend(
            f"- [Version {item.version}](v{item.version:04d}.md) - {item.summary}"
            for item in personas
        )
        lines.append("")
        _atomic_text(
            self.aliases_root / alias_id / "knowledge" / "personas" / "index.md",
            "\n".join(lines),
        )

    def _validate_import_versions(
        self,
        alias: AliasRecord,
        personas: tuple[PersonaVersion, ...],
        profiles: tuple[RuntimeProfileVersion, ...],
    ) -> None:
        if not personas or not profiles:
            raise SimoDataError("alias export requires persona and runtime profile versions")
        if any(item.alias_id != alias.alias_id for item in (*personas, *profiles)):
            raise SimoDataError("alias export contains a version owned by another alias")
        if {item.version for item in personas} != set(range(1, len(personas) + 1)):
            raise SimoDataError("persona versions must be contiguous from 1")
        if {item.version for item in profiles} != set(range(1, len(profiles) + 1)):
            raise SimoDataError("runtime profile versions must be contiguous from 1")
        if alias.active_persona_version not in {item.version for item in personas}:
            raise SimoDataError("active persona version is missing")
        if alias.active_runtime_profile_version not in {item.version for item in profiles}:
            raise SimoDataError("active runtime profile version is missing")

    def _insert_import(
        self,
        connection: sqlite3.Connection,
        alias: AliasRecord,
        personas: tuple[PersonaVersion, ...],
        profiles: tuple[RuntimeProfileVersion, ...],
    ) -> None:
        connection.execute(
            """
            INSERT INTO aliases (
                alias_id, display_name, created_at, updated_at,
                active_persona_version, active_runtime_profile_version, knowledge_root
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alias.alias_id,
                alias.display_name,
                alias.created_at,
                alias.updated_at,
                alias.active_persona_version,
                alias.active_runtime_profile_version,
                alias.knowledge_root,
            ),
        )
        connection.executemany(
            """
            INSERT INTO persona_versions (
                alias_id, version, created_at, summary, instructions, parent_version, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.alias_id,
                    item.version,
                    item.created_at,
                    item.summary,
                    item.instructions,
                    item.parent_version,
                    item.source,
                )
                for item in personas
            ],
        )
        connection.executemany(
            """
            INSERT INTO runtime_profile_versions (
                alias_id, version, created_at, profile_json, parent_version, source
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.alias_id,
                    item.version,
                    item.created_at,
                    _json_dump(item.profile),
                    item.parent_version,
                    item.source,
                )
                for item in profiles
            ],
        )


def _mapping_row_factory(
    cursor: sqlite3.Cursor, row: sqlite3.Row | tuple[object, ...]
) -> dict[str, object]:
    description = cursor.description
    if description is None:
        return {}
    values = cast(tuple[object, ...], row)
    return {str(column[0]): value for column, value in zip(description, values, strict=True)}


def _alias_from_row(row: Mapping[str, object]) -> AliasRecord:
    return AliasRecord(
        _required_str(row, "alias_id"),
        _required_str(row, "display_name"),
        _required_str(row, "created_at"),
        _required_str(row, "updated_at"),
        _required_int(row, "active_persona_version"),
        _required_int(row, "active_runtime_profile_version"),
        _required_str(row, "knowledge_root"),
    )


def _persona_from_row(row: Mapping[str, object]) -> PersonaVersion:
    return PersonaVersion(
        _required_str(row, "alias_id"),
        _required_int(row, "version"),
        _required_str(row, "created_at"),
        _required_str(row, "summary"),
        _required_str(row, "instructions"),
        _optional_int(row, "parent_version"),
        _required_str(row, "source"),
    )


def _profile_from_row(row: Mapping[str, object]) -> RuntimeProfileVersion:
    return RuntimeProfileVersion(
        _required_str(row, "alias_id"),
        _required_int(row, "version"),
        _required_str(row, "created_at"),
        _json_object(_required_str(row, "profile_json")),
        _optional_int(row, "parent_version"),
        _required_str(row, "source"),
    )


def _conversation_from_row(row: Mapping[str, object]) -> ConversationRecord:
    return ConversationRecord(
        _required_str(row, "conversation_id"),
        _required_str(row, "title"),
        _required_str(row, "created_at"),
        _required_str(row, "updated_at"),
        _required_str(row, "status"),
        bool(_required_int(row, "raw_audio_retained")),
    )


def _participant_from_row(row: Mapping[str, object]) -> ParticipantRecord:
    return ParticipantRecord(
        _required_str(row, "conversation_id"),
        _required_str(row, "participant_id"),
        _required_str(row, "kind"),
        _optional_str(row, "alias_id"),
        _required_str(row, "display_name"),
        _optional_str(row, "transport_participant_id"),
        _required_str(row, "joined_at"),
    )


def _event_from_row(row: Mapping[str, object]) -> ConversationEvent:
    return ConversationEvent(
        _required_str(row, "event_id"),
        _required_str(row, "conversation_id"),
        _required_int(row, "sequence"),
        _optional_str(row, "participant_id"),
        _required_str(row, "event_type"),
        _required_str(row, "wall_time"),
        _required_int(row, "monotonic_ns"),
        _optional_str(row, "text"),
        bool(_required_int(row, "interrupted")),
        _optional_int(row, "persona_version"),
        _optional_int(row, "runtime_profile_version"),
        _json_object(_required_str(row, "metadata_json")),
    )


def _alias_from_mapping(value: Mapping[str, object]) -> AliasRecord:
    return AliasRecord(
        _required_str(value, "alias_id"),
        _required_str(value, "display_name"),
        _required_str(value, "created_at"),
        _required_str(value, "updated_at"),
        _required_int(value, "active_persona_version"),
        _required_int(value, "active_runtime_profile_version"),
        _required_str(value, "knowledge_root"),
    )


def _persona_from_mapping(value: Mapping[str, object]) -> PersonaVersion:
    return PersonaVersion(
        _required_str(value, "alias_id"),
        _required_int(value, "version"),
        _required_str(value, "created_at"),
        _required_str(value, "summary"),
        _required_str(value, "instructions"),
        _optional_int(value, "parent_version"),
        _required_str(value, "source"),
    )


def _profile_from_mapping(value: Mapping[str, object]) -> RuntimeProfileVersion:
    return RuntimeProfileVersion(
        _required_str(value, "alias_id"),
        _required_int(value, "version"),
        _required_str(value, "created_at"),
        dict(_required_object(value, "profile")),
        _optional_int(value, "parent_version"),
        _required_str(value, "source"),
    )


def _json_dump(value: object) -> str:
    _ensure_json_value(value, "value")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_object(text: str) -> dict[str, object]:
    try:
        value = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise SimoDataError("invalid JSON data") from error
    if not isinstance(value, dict):
        raise SimoDataError("JSON data must be an object")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise SimoDataError("JSON object keys must be strings")
    return {cast(str, key): item for key, item in mapping.items()}


def _yaml_object(text: str) -> dict[str, object]:
    try:
        value = cast(object, yaml.safe_load(text))
    except yaml.YAMLError as error:
        raise SimoDataError("invalid alias manifest YAML") from error
    if not isinstance(value, dict):
        raise SimoDataError("alias manifest must be a mapping")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise SimoDataError("alias manifest keys must be strings")
    return {cast(str, key): item for key, item in mapping.items()}


def _required_object(value: Mapping[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise SimoDataError(f"{key} must be an object")
    mapping = cast(dict[object, object], item)
    if any(not isinstance(name, str) for name in mapping):
        raise SimoDataError(f"{key} object keys must be strings")
    return {cast(str, name): child for name, child in mapping.items()}


def _required_object_list(value: Mapping[str, object], key: str) -> tuple[dict[str, object], ...]:
    item = value.get(key)
    if not isinstance(item, list):
        raise SimoDataError(f"{key} must be a list")
    result: list[dict[str, object]] = []
    for child in cast(list[object], item):
        if not isinstance(child, dict):
            raise SimoDataError(f"{key} entries must be objects")
        mapping = cast(dict[object, object], child)
        if any(not isinstance(name, str) for name in mapping):
            raise SimoDataError(f"{key} entry keys must be strings")
        result.append({cast(str, name): nested for name, nested in mapping.items()})
    return tuple(result)


def _required_str(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise SimoDataError(f"{key} must be a non-empty string")
    return item


def _required_int(value: Mapping[str, object], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise SimoDataError(f"{key} must be an integer")
    return item


def _optional_int(value: Mapping[str, object], key: str) -> int | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, int) or isinstance(item, bool):
        raise SimoDataError(f"{key} must be an integer or null")
    return item


def _optional_str(value: Mapping[str, object], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str):
        raise SimoDataError(f"{key} must be a string or null")
    return item


def _ensure_json_value(value: object, name: str) -> None:
    if value is None or isinstance(value, str | int | float | bool):
        return
    if isinstance(value, list | tuple):
        for item in cast(list[object] | tuple[object, ...], value):
            _ensure_json_value(item, name)
        return
    if isinstance(value, Mapping):
        for key, item in cast(Mapping[object, object], value).items():
            if not isinstance(key, str):
                raise TypeError(f"{name} keys must be strings")
            _ensure_json_value(item, name)
        return
    raise ValueError(f"{name} contains a non-JSON value: {type(value).__name__}")


def _nonempty(value: str, name: str) -> str:
    selected = value.strip()
    if not selected:
        raise ValueError(f"{name} must not be empty")
    return selected


def _validate_uuid(value: str, name: str) -> None:
    try:
        UUID(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a UUID") from error


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS aliases (
    alias_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    active_persona_version INTEGER NOT NULL,
    active_runtime_profile_version INTEGER NOT NULL,
    knowledge_root TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS persona_versions (
    alias_id TEXT NOT NULL REFERENCES aliases(alias_id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    instructions TEXT NOT NULL,
    parent_version INTEGER,
    source TEXT NOT NULL,
    PRIMARY KEY (alias_id, version)
);

CREATE TABLE IF NOT EXISTS runtime_profile_versions (
    alias_id TEXT NOT NULL REFERENCES aliases(alias_id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    parent_version INTEGER,
    source TEXT NOT NULL,
    PRIMARY KEY (alias_id, version)
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'cancelled')),
    raw_audio_retained INTEGER NOT NULL DEFAULT 0 CHECK (raw_audio_retained IN (0, 1))
);

CREATE TABLE IF NOT EXISTS participants (
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    participant_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('alias', 'human', 'external')),
    alias_id TEXT REFERENCES aliases(alias_id) ON DELETE RESTRICT,
    display_name TEXT NOT NULL,
    transport_participant_id TEXT,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (conversation_id, participant_id)
);

CREATE TABLE IF NOT EXISTS conversation_events (
    event_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    participant_id TEXT,
    event_type TEXT NOT NULL,
    wall_time TEXT NOT NULL,
    monotonic_ns INTEGER NOT NULL CHECK (monotonic_ns >= 0),
    text TEXT,
    interrupted INTEGER NOT NULL DEFAULT 0 CHECK (interrupted IN (0, 1)),
    persona_version INTEGER,
    runtime_profile_version INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (conversation_id, sequence),
    FOREIGN KEY (conversation_id, participant_id)
        REFERENCES participants(conversation_id, participant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memory_claims (
    claim_id TEXT PRIMARY KEY,
    owner_alias_id TEXT NOT NULL REFERENCES aliases(alias_id) ON DELETE CASCADE,
    subject_alias_id TEXT REFERENCES aliases(alias_id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    source_conversation_id TEXT REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    source_event_id TEXT REFERENCES conversation_events(event_id) ON DELETE CASCADE,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    sensitivity TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'superseded', 'forgotten', 'rejected')),
    supersedes_claim_id TEXT REFERENCES memory_claims(claim_id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    stale_after TEXT
);

CREATE TABLE IF NOT EXISTS experiment_profiles (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    run_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES experiment_profiles(profile_id) ON DELETE RESTRICT,
    incumbent_alias_id TEXT NOT NULL REFERENCES aliases(alias_id) ON DELETE CASCADE,
    candidate_alias_id TEXT NOT NULL REFERENCES aliases(alias_id) ON DELETE CASCADE,
    seed INTEGER NOT NULL,
    held_out INTEGER NOT NULL CHECK (held_out IN (0, 1)),
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES experiment_runs(run_id) ON DELETE CASCADE,
    objective_score REAL NOT NULL,
    floors_passed INTEGER NOT NULL CHECK (floors_passed IN (0, 1)),
    metrics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promotions (
    promotion_id TEXT PRIMARY KEY,
    alias_id TEXT NOT NULL REFERENCES aliases(alias_id) ON DELETE CASCADE,
    from_profile_version INTEGER NOT NULL,
    to_profile_version INTEGER NOT NULL,
    experiment_run_id TEXT REFERENCES experiment_runs(run_id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('promoted', 'rolled_back')),
    created_at TEXT NOT NULL,
    rolled_back_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_participants_alias ON participants(alias_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_events_conversation ON conversation_events(conversation_id, sequence);
CREATE INDEX IF NOT EXISTS idx_claims_owner_status ON memory_claims(owner_alias_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_profile ON experiment_runs(profile_id, held_out, status);
"""
