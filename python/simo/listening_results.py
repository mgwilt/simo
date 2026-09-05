"""Local, revisioned listener reports. Stored telemetry is not release attestation."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import stat
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request

from simo.breeze_listening import (
    RATING_FIELDS,
    SCHEMA,
    ListeningDeck,
    Record,
    obj,
    rows,
    sha,
    unique,
)

MAX_SNAPSHOT = 256 * 1024
MAX_REVISIONS = 2000
MAX_SESSIONS = 32
MAX_STORAGE = 48 * 1024 * 1024
STORE_SCHEMA = "simo.breeze.listening.saved.v1"


def encode_snapshot(snapshot: Record) -> bytes:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def text(value: object, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("Invalid or oversized listening text")
    return value


def opaque(value: object) -> str:
    value = text(value, 32)
    if re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise ValueError("Invalid listening session ID")
    return value


def timestamp(value: object) -> None:
    parsed = datetime.fromisoformat(text(value, 40).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Listening timestamps need a timezone")


def validate_snapshot(snapshot: Record, deck: ListeningDeck) -> None:
    required = {
        "schema",
        "deck_sha256",
        "started",
        "exported",
        "conditions",
        "browser",
        "player",
        "manifest",
        "ratings",
        "preferences",
        "attempts",
        "quality_accepted",
        "acoustic_onset",
        "limits",
    }
    if set(snapshot) not in (required, required | {"view"}):
        raise ValueError("Invalid listening snapshot fields")
    if (
        snapshot["schema"] != SCHEMA
        or snapshot["deck_sha256"] != deck.digest
        or snapshot["quality_accepted"] is not False
        or snapshot["acoustic_onset"] != "unmeasured"
        or snapshot["player"] != "preview-player/listening-v1"
    ):
        raise ValueError("Invalid or changed listening snapshot identity")
    timestamp(snapshot["started"])
    timestamp(snapshot["exported"])
    for name, limit in (("conditions", 4096), ("browser", 1024), ("limits", 2048)):
        text(snapshot[name], limit)
    if "view" in snapshot:
        view = obj(snapshot["view"])
        if (
            set(view) != {"position", "clip"}
            or type(view["position"]) is not int
            or not 0 <= view["position"] < 18
            or view["clip"] not in ("A", "B", "C", "D")
        ):
            raise ValueError("Invalid listening view")
    cases = rows(deck.deck["cases"])
    case_ids = {str(case["id"]) for case in cases}
    clip_cases = {
        str(clip["id"]): str(case["id"]) for case in cases for clip in rows(case["clips"])
    }
    ratings = rows(snapshot["ratings"])
    ids: set[str] = set()
    for rating in ratings:
        clip_id = opaque(rating.get("clip_id"))
        required_rating = {"clip_id", "pcm_sha256", "notes", *RATING_FIELDS}
        if (
            set(rating) not in (required_rating, required_rating | {"answered"})
            or clip_id in ids
            or clip_id not in deck.clips
        ):
            raise ValueError("Duplicate or invalid rating")
        ids.add(clip_id)
        if rating["pcm_sha256"] != deck.clips[clip_id]["pcm_sha256"] or any(
            rating[field] not in ("yes", "no", "uncertain") for field in RATING_FIELDS
        ):
            raise ValueError("Invalid clip rating identity or answer")
        text(rating["notes"], 4096)
        if "answered" in rating:
            answered = rating["answered"]
            if not isinstance(answered, list):
                raise ValueError("Invalid answered rating fields")
            answers = cast(list[object], answered)
            if (
                len(answers) > 6
                or any(field not in RATING_FIELDS for field in answers)
                or len(set(cast(list[str], answers))) != len(answers)
            ):
                raise ValueError("Invalid answered rating fields")
    preferences = snapshot["preferences"]
    if not isinstance(preferences, list) or len(cast(list[object], preferences)) > 18:
        raise ValueError("Invalid listening preferences")
    preferred: set[str] = set()
    for preference in cast(list[object], preferences):
        if not isinstance(preference, list) or len(cast(list[object], preference)) != 2:
            raise ValueError("Invalid listening preference")
        case_id, value = cast(list[object], preference)
        if (
            case_id not in case_ids
            or case_id in preferred
            or value not in ("unrated", "A", "B", "C", "D", "tie", "uncertain")
        ):
            raise ValueError("Invalid listening preference")
        preferred.add(cast(str, case_id))
    attempts = rows(snapshot["attempts"])
    if len(attempts) > 512:
        raise ValueError("Listening attempt limit reached")
    running = 0
    for index, attempt in enumerate(attempts):
        required_attempt = {"ordinal", "lane", "status", "started", "listener"}
        if not required_attempt <= set(attempt) or set(attempt) - (
            required_attempt
            | {"clip_id", "case_id", "trial", "metrics", "error", "producer", "benchmark_manifest"}
        ):
            raise ValueError("Invalid listening attempt fields")
        if (
            type(attempt["ordinal"]) is not int
            or attempt["ordinal"] != index
            or attempt["status"] not in ("running", "complete", "stopped", "failed")
        ):
            raise ValueError("Invalid listening attempt order/status")
        running += attempt["status"] == "running"
        timestamp(attempt["started"])
        if attempt["lane"] == "recorded":
            if (
                attempt.get("clip_id") not in clip_cases
                or attempt.get("case_id") != clip_cases[str(attempt["clip_id"])]
                or "trial" in attempt
            ):
                raise ValueError("Invalid attempted clip/case")
        elif attempt["lane"] == "fresh":
            trial = obj(attempt.get("trial"))
            manifest = obj(attempt.get("benchmark_manifest", snapshot["manifest"]))
            suites, instructions = obj(manifest.get("suites")), obj(manifest.get("instructions"))
            suite = text(trial.get("suite"), 20)
            prompts = suites.get(suite)
            if (
                set(trial) != {"suite", "index", "seed", "instruction_id"}
                or suite not in ("short", "long")
                or not isinstance(prompts, list)
            ):
                raise ValueError("Invalid fresh trial fields")
            if "clip_id" in attempt or "case_id" in attempt:
                raise ValueError("Fresh trials cannot use recorded clip identities")
            if (
                type(trial["index"]) is not int
                or not 0 <= trial["index"] < len(cast(list[object], prompts))
                or type(trial["seed"]) is not int
                or trial["seed"] not in (17, 29, 42)
                or trial["instruction_id"] not in instructions
            ):
                raise ValueError("Invalid fresh trial")
        else:
            raise ValueError("Invalid listening lane")
        listener = obj(attempt["listener"])
        if (
            set(listener)
            not in (
                {"heard", "gaps", "start", "notes"},
                {"heard", "gaps", "start", "notes", "answered"},
            )
            or any(listener[key] not in ("yes", "no", "uncertain") for key in ("heard", "gaps"))
            or listener["start"] not in ("unreported", "prompt", "delayed", "uncertain")
        ):
            raise ValueError("Invalid listener observation")
        text(listener["notes"], 4096)
        if "answered" in listener:
            answered_listener = listener["answered"]
            if not isinstance(answered_listener, list):
                raise ValueError("Invalid observation answers")
            answered_fields = cast(list[object], answered_listener)
            if (
                len(answered_fields) > 3
                or any(field not in ("heard", "gaps", "start") for field in answered_fields)
                or len(set(cast(list[str], answered_fields))) != len(answered_fields)
            ):
                raise ValueError("Invalid observation answers")
        if "error" in attempt:
            text(attempt["error"], 4096)
    if running > 1:
        raise ValueError("Multiple active listening attempts")


def preserve_history(previous: Record, current: Record) -> None:
    before, after = rows(previous["attempts"]), rows(current["attempts"])
    if (
        previous["started"] != current["started"]
        or len(after) < len(before)
        or not {row["clip_id"] for row in rows(previous["ratings"])}
        <= {row["clip_id"] for row in rows(current["ratings"])}
    ):
        raise ValueError("Listening history cannot be removed")
    for old, new in zip(before, after, strict=False):
        immutable = (
            "ordinal",
            "lane",
            "clip_id",
            "case_id",
            "trial",
            "started",
            "benchmark_manifest",
        )
        if any(old.get(key) != new.get(key) for key in immutable) or (
            old["status"] != "running"
            and any(
                old.get(key) != new.get(key) for key in ("status", "metrics", "producer", "error")
            )
        ):
            raise ValueError("Completed attempt evidence cannot be rewritten")


class ResultsStore:
    def __init__(self, directory: Path, deck: ListeningDeck) -> None:
        if not hasattr(os, "getuid"):
            raise ValueError("Private local storage requires POSIX permissions")
        self.directory, self.deck = directory.absolute(), deck
        if any(path.is_symlink() for path in (self.directory, *self.directory.parents)):
            raise ValueError("Listening result directory cannot use symlinks")
        self.directory.mkdir(mode=0o700, parents=False, exist_ok=True)
        if self.directory.stat().st_mode & 0o077 or self.directory.stat().st_uid != os.getuid():
            raise ValueError("Listening result directory must be private and owned by this user")
        self.path = self.directory / "results.sqlite3"
        if not hasattr(os, "O_NOFOLLOW"):
            raise ValueError("Safe local result storage unavailable")
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("Results database must be a regular file")
            if os.fstat(descriptor).st_mode & 0o077 or os.fstat(descriptor).st_uid != os.getuid():
                raise ValueError("Results database must be private and owned by this user")
        finally:
            os.close(descriptor)
        with closing(self.connect()) as database, database:
            tables = database.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if tables not in ([], [("snapshots",)]):
                raise ValueError("Not a listening results database")
            database.execute(
                "CREATE TABLE IF NOT EXISTS snapshots (session_id TEXT NOT NULL, revision INTEGER NOT NULL, deck TEXT NOT NULL, digest TEXT NOT NULL, saved_at TEXT NOT NULL, payload BLOB NOT NULL, PRIMARY KEY(session_id, revision))"
            )

    def connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise ValueError("Results database cannot be a symlink")
        database = sqlite3.connect(self.path, timeout=3)
        page_size = cast(tuple[int], database.execute("PRAGMA page_size").fetchone())[0]
        page_count = cast(tuple[int], database.execute("PRAGMA page_count").fetchone())[0]
        if page_count * page_size > 64 * 1024 * 1024:
            database.close()
            raise ValueError("Listening database exceeds capacity")
        database.execute(f"PRAGMA max_page_count = {64 * 1024 * 1024 // page_size}")
        return database

    def load(self, session_id: str) -> Record:
        session_id = opaque(session_id)
        with closing(self.connect()) as database:
            row = cast(
                tuple[int, str, str, bytes, str] | None,
                database.execute(
                    "SELECT revision, deck, saved_at, payload, digest FROM snapshots WHERE session_id=? ORDER BY revision DESC LIMIT 1",
                    (session_id,),
                ).fetchone(),
            )
        if row is None:
            raise FileNotFoundError(session_id)
        revision, deck, saved_at, payload, digest = row
        if deck != self.deck.digest:
            raise ValueError("Saved listening deck changed")
        if len(payload) > MAX_SNAPSHOT or sha(payload) != digest:
            raise ValueError("Saved listening result is damaged")
        snapshot = obj(cast(object, json.loads(payload)))
        encode_snapshot(snapshot)
        validate_snapshot(snapshot, self.deck)
        return {
            "schema": STORE_SCHEMA,
            "session_id": session_id,
            "revision": revision,
            "saved_at": saved_at,
            "snapshot": snapshot,
        }

    def save(self, session_id: str, revision: int, snapshot: Record) -> Record:
        session_id = opaque(session_id)
        if type(revision) is not int or not 1 <= revision <= MAX_REVISIONS:
            raise ValueError("Invalid listening revision")
        payload = encode_snapshot(snapshot)
        if len(payload) > MAX_SNAPSHOT:
            raise ValueError("Listening snapshot exceeds limit")
        validate_snapshot(snapshot, self.deck)
        digest = sha(payload)
        with closing(self.connect()) as database, database:
            database.execute("BEGIN IMMEDIATE")
            retry = cast(
                tuple[str, str, str] | None,
                database.execute(
                    "SELECT deck, digest, saved_at FROM snapshots WHERE session_id=? AND revision=?",
                    (session_id, revision),
                ).fetchone(),
            )
            if retry is not None:
                retry_deck, retry_digest, retry_time = retry
                if retry_deck != self.deck.digest or retry_digest != digest:
                    raise FileExistsError("Listening revision already contains different results")
                return {
                    "schema": STORE_SCHEMA,
                    "session_id": session_id,
                    "revision": revision,
                    "saved_at": retry_time,
                    "deck_sha256": self.deck.digest,
                }
            stored_bytes = cast(
                tuple[int],
                database.execute(
                    "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM snapshots"
                ).fetchone(),
            )[0]
            if stored_bytes + len(payload) > MAX_STORAGE:
                raise OverflowError("Listening storage capacity reached")
            latest = cast(
                tuple[int, str, str, str, bytes] | None,
                database.execute(
                    "SELECT revision, deck, digest, saved_at, payload FROM snapshots WHERE session_id=? ORDER BY revision DESC LIMIT 1",
                    (session_id,),
                ).fetchone(),
            )
            if (
                latest is not None
                and latest[0] == revision
                and latest[1] == self.deck.digest
                and latest[2] == digest
            ):
                saved_at = latest[3]  # An acknowledged-or-lost-response retry is idempotent.
            else:
                if revision != (latest[0] + 1 if latest else 1) or (
                    latest and latest[1] != self.deck.digest
                ):
                    raise FileExistsError("Listening session changed in another tab; no overwrite")
                if latest:
                    preserve_history(obj(cast(object, json.loads(latest[4]))), snapshot)
                elif (
                    cast(
                        tuple[int],
                        database.execute(
                            "SELECT COUNT(DISTINCT session_id) FROM snapshots"
                        ).fetchone(),
                    )[0]
                    >= MAX_SESSIONS
                ):
                    raise OverflowError("Listening session capacity reached")
                saved_at = datetime.now(UTC).isoformat()
                database.execute(
                    "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, revision, self.deck.digest, digest, saved_at, payload),
                )
        return {
            "schema": STORE_SCHEMA,
            "session_id": session_id,
            "revision": revision,
            "saved_at": saved_at,
            "deck_sha256": self.deck.digest,
        }


def attach_results(app: FastAPI, deck: ListeningDeck, directory: Path) -> None:
    store = ResultsStore(directory, deck)

    def checked(request: Request) -> None:
        if request.query_params or request.headers.get("X-Simo-Listening-Deck") != deck.digest:
            raise HTTPException(status_code=409, detail="Listening deck mismatch")

    @app.get("/api/listening/results/{session_id}", include_in_schema=False)
    async def restore(session_id: str, request: Request) -> Record:
        checked(request)
        try:
            return await asyncio.to_thread(store.load, session_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="No saved listening session") from error
        except (ValueError, TypeError, KeyError, RecursionError, OSError, sqlite3.Error) as error:
            raise HTTPException(
                status_code=409, detail="Saved listening session unavailable"
            ) from error

    @app.put("/api/listening/results/{session_id}", include_in_schema=False)
    async def save(session_id: str, request: Request) -> Record:
        checked(request)
        if request.headers.get("origin") != f"https://{request.headers.get('host')}":
            raise HTTPException(
                status_code=403, detail="Listening saves require same-origin requests"
            )
        if request.headers.get("content-type") != "application/json":
            raise HTTPException(status_code=415, detail="Expected listening JSON")

        async def body() -> bytes:
            raw = bytearray()
            async for chunk in request.stream():
                if len(raw) + len(chunk) > MAX_SNAPSHOT + 128:
                    raise HTTPException(status_code=413, detail="Listening result too large")
                raw.extend(chunk)
            return bytes(raw)

        def nonfinite(value: str) -> object:
            raise ValueError("Nonfinite listening JSON")

        try:
            raw = await asyncio.wait_for(body(), timeout=5)
            payload = obj(
                cast(object, json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite))
            )
            if set(payload) != {"revision", "snapshot"}:
                raise ValueError("Invalid save envelope")
            return await asyncio.to_thread(
                store.save, session_id, cast(int, payload["revision"]), obj(payload["snapshot"])
            )
        except FileExistsError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            raise HTTPException(status_code=422, detail="Invalid listening result") from error
        except TimeoutError as error:
            raise HTTPException(status_code=408, detail="Listening save timed out") from error
        except (OSError, sqlite3.Error, OverflowError) as error:
            raise HTTPException(
                status_code=507, detail="Local result storage unavailable"
            ) from error
