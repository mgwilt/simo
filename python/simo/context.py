"""Typed Python ownership boundary for the native Flecs context engine."""

from __future__ import annotations

import ctypes
import json
import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast
from uuid import uuid4


class DropPolicy(IntEnum):
    """Behavior when the bounded semantic-event queue is full."""

    DROP_OLDEST = 0
    DROP_NEWEST = 1


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    accepted: bool
    sequence: int


@dataclass(frozen=True, slots=True)
class EngineStats:
    accepted: int
    dropped: int
    processed: int
    structural_observations: int
    queued: int
    retained: int


@dataclass(frozen=True, slots=True)
class KnowledgeConcept:
    okf_id: str
    stable_id: str
    type: str
    title: str
    status: str
    authority: str
    source_path: str
    verified_at: str
    stale_after: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class KnowledgeRefreshStats:
    revision: int
    concepts: int
    links: int
    removed: int


@dataclass(frozen=True, slots=True)
class ContextParticipant:
    participant_id: str
    kind: str
    alias_id: str | None
    display_name: str
    transport_participant_id: str | None = None

    def __post_init__(self) -> None:
        if not self.participant_id.strip():
            raise ValueError("context participant ID must not be empty")
        if self.kind not in {"alias", "human", "external"}:
            raise ValueError("context participant kind must be alias, human, or external")
        if self.kind == "alias" and not self.alias_id:
            raise ValueError("alias context participant requires an alias ID")
        if not self.display_name.strip():
            raise ValueError("context participant display name must not be empty")


@dataclass(frozen=True, slots=True)
class ConversationContextScope:
    alias_id: str
    conversation_id: str
    local_participant_id: str
    participants: tuple[ContextParticipant, ...]

    def __post_init__(self) -> None:
        if not self.alias_id.strip() or not self.conversation_id.strip():
            raise ValueError("context alias and conversation IDs must not be empty")
        participant_ids = [participant.participant_id for participant in self.participants]
        if len(participant_ids) != len(set(participant_ids)):
            raise ValueError("context participant IDs must be unique")
        if self.local_participant_id not in participant_ids:
            raise ValueError("local context participant must be present in participants")
        local = self.participants[participant_ids.index(self.local_participant_id)]
        if local.kind != "alias" or local.alias_id != self.alias_id:
            raise ValueError("local context participant must represent the scoped alias")

    @classmethod
    def ephemeral(cls, mode: str, remote_participant_id: str) -> ConversationContextScope:
        """Create an explicitly non-persisted scope for diagnostic runtimes."""

        selected_mode = mode.strip()
        selected_remote = remote_participant_id.strip()
        if not selected_mode or not selected_remote:
            raise ValueError("ephemeral scope identity must not be empty")
        run_id = str(uuid4())
        alias_id = f"ephemeral:{selected_mode}:{run_id}"
        local_participant_id = f"alias:{run_id}"
        return cls(
            alias_id,
            f"ephemeral:{selected_mode}:{run_id}",
            local_participant_id,
            (
                ContextParticipant(
                    local_participant_id,
                    "alias",
                    alias_id,
                    f"Simo {selected_mode}",
                ),
                ContextParticipant(
                    selected_remote,
                    "external",
                    None,
                    "Remote participant",
                ),
            ),
        )


class _NativeStats(ctypes.Structure):
    _fields_ = [
        ("accepted", ctypes.c_uint64),
        ("dropped", ctypes.c_uint64),
        ("processed", ctypes.c_uint64),
        ("structural_observations", ctypes.c_uint64),
        ("queued", ctypes.c_size_t),
        ("retained", ctypes.c_size_t),
    ]


class _NativeKnowledgeRefreshStats(ctypes.Structure):
    _fields_ = [
        ("revision", ctypes.c_uint64),
        ("concepts", ctypes.c_size_t),
        ("links", ctypes.c_size_t),
        ("removed", ctypes.c_size_t),
    ]


def _library_names() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("libsimo_core.dylib",)
    if sys.platform == "win32":
        return ("simo_core.dll", "libsimo_core.dll")
    return ("libsimo_core.so",)


def find_core_library(
    explicit: str | os.PathLike[str] | None = None,
) -> Path:
    """Locate the native Simo core without loading or mutating it."""
    if explicit is not None:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"Simo core library does not exist: {candidate}")

    configured = os.environ.get("SIMO_CORE_LIBRARY")
    if configured:
        return find_core_library(configured)

    repository = Path(__file__).resolve().parents[2]
    search_roots = (
        repository / ".build" / "simo",
        repository / ".build" / "manual",
        repository / "build",
        repository / "build" / "lib",
        repository / "cmake-build-debug",
    )
    for root in search_roots:
        for name in _library_names():
            candidate = root / name
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        "Simo core library was not found; set SIMO_CORE_LIBRARY or build the simo_core target"
    )


def _configure_library(library: ctypes.CDLL) -> None:
    library.simo_context_engine_create.argtypes = [
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_int,
    ]
    library.simo_context_engine_create.restype = ctypes.c_void_p
    library.simo_context_engine_create_scoped.argtypes = [
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    library.simo_context_engine_create_scoped.restype = ctypes.c_void_p
    library.simo_context_engine_destroy.argtypes = [ctypes.c_void_p]
    library.simo_context_engine_destroy.restype = None
    library.simo_context_engine_upsert_participant.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    library.simo_context_engine_upsert_participant.restype = ctypes.c_int
    library.simo_context_engine_enqueue_transcript.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint64),
    ]
    library.simo_context_engine_enqueue_transcript.restype = ctypes.c_int
    library.simo_context_engine_tick.argtypes = [ctypes.c_void_p]
    library.simo_context_engine_tick.restype = ctypes.c_size_t
    library.simo_context_engine_snapshot_json.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    library.simo_context_engine_snapshot_json.restype = ctypes.c_size_t
    library.simo_context_engine_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_NativeStats),
    ]
    library.simo_context_engine_stats.restype = ctypes.c_int
    library.simo_context_engine_begin_knowledge_refresh.argtypes = [ctypes.c_void_p]
    library.simo_context_engine_begin_knowledge_refresh.restype = ctypes.c_int
    library.simo_context_engine_upsert_knowledge_concept.argtypes = [
        ctypes.c_void_p,
        *([ctypes.c_char_p] * 10),
    ]
    library.simo_context_engine_upsert_knowledge_concept.restype = ctypes.c_int
    library.simo_context_engine_add_knowledge_reference.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    library.simo_context_engine_add_knowledge_reference.restype = ctypes.c_int
    library.simo_context_engine_commit_knowledge_refresh.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_NativeKnowledgeRefreshStats),
    ]
    library.simo_context_engine_commit_knowledge_refresh.restype = ctypes.c_int
    library.simo_context_engine_knowledge_snapshot_json.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    library.simo_context_engine_knowledge_snapshot_json.restype = ctypes.c_size_t


class NativeContextEngine:
    """Own one native context engine and expose snapshot values only."""

    def __init__(
        self,
        *,
        queue_capacity: int = 256,
        max_segments: int = 64,
        drop_policy: DropPolicy = DropPolicy.DROP_OLDEST,
        scope: ConversationContextScope | None = None,
        library_path: str | os.PathLike[str] | None = None,
    ) -> None:
        if queue_capacity <= 0 or max_segments <= 0:
            raise ValueError("queue_capacity and max_segments must be positive")
        self._library = ctypes.CDLL(str(find_core_library(library_path)))
        _configure_library(self._library)
        handle_value = cast(
            object,
            self._library.simo_context_engine_create(
                queue_capacity,
                max_segments,
                int(drop_policy),
            )
            if scope is None
            else self._library.simo_context_engine_create_scoped(
                queue_capacity,
                max_segments,
                int(drop_policy),
                scope.alias_id.encode("utf-8"),
                scope.conversation_id.encode("utf-8"),
                scope.local_participant_id.encode("utf-8"),
            ),
        )
        if not isinstance(handle_value, int) or handle_value == 0:
            raise RuntimeError("failed to create native Simo context engine")
        self._handle: int | None = handle_value
        self._participant_ids: set[str] | None = set() if scope is not None else None
        if scope is not None:
            try:
                for participant in scope.participants:
                    self.upsert_participant(participant)
            except Exception:
                self.close()
                raise

    def close(self) -> None:
        if self._handle is not None:
            self._library.simo_context_engine_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        handle = getattr(self, "_handle", None)
        library = getattr(self, "_library", None)
        if handle is not None and library is not None:
            library.simo_context_engine_destroy(handle)
            self._handle = None

    def _require_handle(self) -> int:
        if self._handle is None:
            raise RuntimeError("native Simo context engine is closed")
        return self._handle

    def enqueue_transcript(self, speaker: str, text: str, is_final: bool = True) -> EnqueueResult:
        if self._participant_ids is not None and speaker not in self._participant_ids:
            raise ValueError(f"transcript speaker is outside the context scope: {speaker}")
        sequence = ctypes.c_uint64()
        result = self._library.simo_context_engine_enqueue_transcript(
            self._require_handle(),
            speaker.encode("utf-8"),
            text.encode("utf-8"),
            int(is_final),
            ctypes.byref(sequence),
        )
        if result < 0:
            raise RuntimeError("native Simo context engine rejected invalid input")
        return EnqueueResult(bool(result), sequence.value)

    def upsert_participant(self, participant: ContextParticipant) -> None:
        result_value = cast(
            object,
            self._library.simo_context_engine_upsert_participant(
                self._require_handle(),
                participant.participant_id.encode("utf-8"),
                participant.kind.encode("utf-8"),
                (participant.alias_id or "").encode("utf-8"),
                participant.display_name.encode("utf-8"),
                (participant.transport_participant_id or "").encode("utf-8"),
            ),
        )
        if result_value != 0:
            raise RuntimeError("native Simo context engine rejected participant identity")
        if self._participant_ids is not None:
            self._participant_ids.add(participant.participant_id)

    def tick(self) -> int:
        return int(self._library.simo_context_engine_tick(self._require_handle()))

    def snapshot(self) -> dict[str, Any]:
        handle = self._require_handle()
        required = int(self._library.simo_context_engine_snapshot_json(handle, None, 0))
        if required <= 1:
            raise RuntimeError("native Simo context engine returned an invalid snapshot size")
        buffer = ctypes.create_string_buffer(required)
        written = int(self._library.simo_context_engine_snapshot_json(handle, buffer, len(buffer)))
        if written != required:
            raise RuntimeError("native Simo context snapshot changed during serialization")
        value = json.loads(buffer.value.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("native Simo context snapshot is not an object")
        return value

    def stats(self) -> EngineStats:
        native = _NativeStats()
        result = self._library.simo_context_engine_stats(
            self._require_handle(), ctypes.byref(native)
        )
        if result != 0:
            raise RuntimeError("failed to read native Simo context statistics")
        return EngineStats(
            accepted=native.accepted,
            dropped=native.dropped,
            processed=native.processed,
            structural_observations=native.structural_observations,
            queued=native.queued,
            retained=native.retained,
        )

    def begin_knowledge_refresh(self) -> None:
        result = self._library.simo_context_engine_begin_knowledge_refresh(self._require_handle())
        if result != 0:
            raise RuntimeError("failed to begin native knowledge refresh")

    def upsert_knowledge_concept(self, concept: KnowledgeConcept) -> None:
        values = (
            concept.okf_id,
            concept.stable_id,
            concept.type,
            concept.title,
            concept.status,
            concept.authority,
            concept.source_path,
            concept.verified_at,
            concept.stale_after,
            concept.content_hash,
        )
        result = self._library.simo_context_engine_upsert_knowledge_concept(
            self._require_handle(),
            *(value.encode("utf-8") for value in values),
        )
        if result != 0:
            raise RuntimeError(f"failed to project knowledge concept {concept.okf_id}")

    def add_knowledge_reference(self, source_okf_id: str, target_okf_id: str) -> None:
        result = self._library.simo_context_engine_add_knowledge_reference(
            self._require_handle(),
            source_okf_id.encode("utf-8"),
            target_okf_id.encode("utf-8"),
        )
        if result != 0:
            raise RuntimeError(
                f"failed to project knowledge reference {source_okf_id} -> {target_okf_id}"
            )

    def commit_knowledge_refresh(self) -> KnowledgeRefreshStats:
        native = _NativeKnowledgeRefreshStats()
        result = self._library.simo_context_engine_commit_knowledge_refresh(
            self._require_handle(), ctypes.byref(native)
        )
        if result != 0:
            raise RuntimeError("failed to commit native knowledge refresh")
        return KnowledgeRefreshStats(
            revision=native.revision,
            concepts=native.concepts,
            links=native.links,
            removed=native.removed,
        )

    def knowledge_snapshot(self) -> dict[str, Any]:
        handle = self._require_handle()
        function = self._library.simo_context_engine_knowledge_snapshot_json
        required = int(function(handle, None, 0))
        if required <= 1:
            raise RuntimeError("native knowledge graph returned an invalid snapshot size")
        buffer = ctypes.create_string_buffer(required)
        written = int(function(handle, buffer, len(buffer)))
        if written != required:
            raise RuntimeError("native knowledge graph changed during serialization")
        value = json.loads(buffer.value.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("native knowledge snapshot is not an object")
        return value
