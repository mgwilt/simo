"""Framework-neutral immutable semantic context snapshots for inference turns."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import cast

from simo.context import ContextMemoryClaim, ContextParticipant


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
    alias_id: str = "ephemeral:unscoped"
    conversation_id: str = "ephemeral:unscoped"
    local_participant_id: str = "alias:unscoped"
    participants: tuple[ContextParticipant, ...] = ()
    memory_revision: int = 0
    memories: tuple[ContextMemoryClaim, ...] = ()
    captured_monotonic_ns: int = field(default_factory=time.monotonic_ns)

    @classmethod
    def from_native(cls, value: dict[str, object]) -> SemanticContextSnapshot:
        typed_value = value
        alias_id = _native_string(typed_value, "alias_id")
        conversation_id = _native_string(typed_value, "conversation_id")
        local_participant_id = _native_string(typed_value, "local_participant_id")
        raw_participants = typed_value.get("participants")
        if not isinstance(raw_participants, list):
            raise TypeError("native semantic participants must be a list")
        participants: list[ContextParticipant] = []
        for raw_participant in cast("list[object]", raw_participants):
            if not isinstance(raw_participant, dict):
                raise TypeError("native semantic participant must be an object")
            participant = cast("dict[str, object]", raw_participant)
            participant_alias = _native_string(participant, "alias_id", allow_empty=True)
            transport_id = _native_string(
                participant,
                "transport_participant_id",
                allow_empty=True,
            )
            participants.append(
                ContextParticipant(
                    participant_id=_native_string(participant, "participant_id"),
                    kind=_native_string(participant, "kind"),
                    alias_id=participant_alias or None,
                    display_name=_native_string(participant, "display_name"),
                    transport_participant_id=transport_id or None,
                )
            )
        memory_revision_value = typed_value.get("memory_revision")
        if not isinstance(memory_revision_value, int):
            raise TypeError("native semantic memory_revision must be an integer")
        raw_memories = typed_value.get("memories")
        if not isinstance(raw_memories, list):
            raise TypeError("native semantic memories must be a list")
        memories: list[ContextMemoryClaim] = []
        for raw_memory in cast("list[object]", raw_memories):
            if not isinstance(raw_memory, dict):
                raise TypeError("native semantic memory must be an object")
            memory = cast("dict[str, object]", raw_memory)
            confidence = memory.get("confidence")
            if not isinstance(confidence, int | float):
                raise TypeError("native semantic memory confidence must be numeric")
            memories.append(
                ContextMemoryClaim(
                    _native_string(memory, "claim_id"),
                    _native_string(memory, "subject_id"),
                    _native_string(memory, "claim_key"),
                    _native_string(memory, "claim_class"),
                    _native_string(memory, "content"),
                    _native_string(memory, "source_conversation_id", allow_empty=True),
                    _native_string(memory, "source_event_id", allow_empty=True),
                    _native_string(memory, "stale_after", allow_empty=True),
                    float(confidence),
                )
            )
        revision = typed_value.get("revision")
        if not isinstance(revision, int):
            raise TypeError("native semantic revision must be an integer")
        raw_items = typed_value.get("items")
        if not isinstance(raw_items, list):
            raise TypeError("native semantic items must be a list")
        items: list[ContextItem] = []
        for raw_item in cast("list[object]", raw_items):
            if not isinstance(raw_item, dict):
                raise TypeError("native semantic item must be an object")
            item = cast("dict[str, object]", raw_item)
            sequence = item.get("sequence")
            speaker = item.get("speaker")
            text = item.get("text")
            is_final = item.get("is_final")
            salience = item.get("salience")
            if not isinstance(sequence, int):
                raise TypeError("native semantic item sequence must be an integer")
            if not isinstance(speaker, str) or not isinstance(text, str):
                raise TypeError("native semantic item speaker and text must be strings")
            if not isinstance(is_final, bool):
                raise TypeError("native semantic item is_final must be boolean")
            if not isinstance(salience, int | float):
                raise TypeError("native semantic item salience must be numeric")
            items.append(ContextItem(sequence, speaker, text, is_final, float(salience)))
        return cls(
            revision=revision,
            items=tuple(items),
            alias_id=alias_id,
            conversation_id=conversation_id,
            local_participant_id=local_participant_id,
            participants=tuple(participants),
            memory_revision=memory_revision_value,
            memories=tuple(memories),
        )

    def require_fresh(self, max_age_ms: int) -> None:
        if max_age_ms <= 0:
            raise ValueError("max_age_ms must be positive")
        age_ns = time.monotonic_ns() - self.captured_monotonic_ns
        if age_ns > max_age_ms * 1_000_000:
            raise ValueError(f"semantic context snapshot exceeds {max_age_ms} ms")


def _native_string(
    value: dict[str, object],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    selected = value.get(key)
    if not isinstance(selected, str) or (not allow_empty and not selected):
        raise TypeError(f"native semantic {key} must be a string")
    return selected


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
    for memory in snapshot.memories:
        line = f"- [memory {memory.claim_key}] {memory.subject_id}: {memory.content}"
        added = len(line) + 1
        if used + added > max_chars:
            break
        selected.append(line)
        used += added
    recent: list[str] = []
    for item in reversed(snapshot.items):
        line = f"- [{item.sequence}] {item.speaker}: {item.text}"
        added = len(line) + 1
        if used + added > max_chars:
            break
        recent.append(line)
        used += added
    selected.extend(reversed(recent))
    return "\n".join((header, *selected))
