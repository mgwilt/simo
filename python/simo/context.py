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
from typing import Any, Self


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


class _NativeStats(ctypes.Structure):
    _fields_ = [
        ("accepted", ctypes.c_uint64),
        ("dropped", ctypes.c_uint64),
        ("processed", ctypes.c_uint64),
        ("structural_observations", ctypes.c_uint64),
        ("queued", ctypes.c_size_t),
        ("retained", ctypes.c_size_t),
    ]


def _library_names() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("libsimo_core.dylib",)
    if sys.platform == "win32":
        return ("simo_core.dll", "libsimo_core.dll")
    return ("libsimo_core.so",)


def _find_library(explicit: str | os.PathLike[str] | None) -> Path:
    if explicit is not None:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"Simo core library does not exist: {candidate}")

    configured = os.environ.get("SIMO_CORE_LIBRARY")
    if configured:
        return _find_library(configured)

    repository = Path(__file__).resolve().parents[2]
    search_roots = (
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
    library.simo_context_engine_destroy.argtypes = [ctypes.c_void_p]
    library.simo_context_engine_destroy.restype = None
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


class NativeContextEngine:
    """Own one native context engine and expose snapshot values only."""

    def __init__(
        self,
        *,
        queue_capacity: int = 256,
        max_segments: int = 64,
        drop_policy: DropPolicy = DropPolicy.DROP_OLDEST,
        library_path: str | os.PathLike[str] | None = None,
    ) -> None:
        if queue_capacity <= 0 or max_segments <= 0:
            raise ValueError("queue_capacity and max_segments must be positive")
        self._library = ctypes.CDLL(str(_find_library(library_path)))
        _configure_library(self._library)
        handle = self._library.simo_context_engine_create(
            queue_capacity,
            max_segments,
            int(drop_policy),
        )
        if not handle:
            raise RuntimeError("failed to create native Simo context engine")
        self._handle: int | None = int(handle)

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

    def enqueue_transcript(
        self, speaker: str, text: str, is_final: bool = True
    ) -> EnqueueResult:
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

    def tick(self) -> int:
        return int(self._library.simo_context_engine_tick(self._require_handle()))

    def snapshot(self) -> dict[str, Any]:
        handle = self._require_handle()
        required = int(self._library.simo_context_engine_snapshot_json(handle, None, 0))
        if required <= 1:
            raise RuntimeError(
                "native Simo context engine returned an invalid snapshot size"
            )
        buffer = ctypes.create_string_buffer(required)
        written = int(
            self._library.simo_context_engine_snapshot_json(handle, buffer, len(buffer))
        )
        if written != required:
            raise RuntimeError(
                "native Simo context snapshot changed during serialization"
            )
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
