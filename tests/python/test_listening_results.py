from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from simo.breeze_listening import (
    RATING_FIELDS,
    ListeningDeck,
    Record,
    attach_listening,
    obj,
    prepare_listening,
    rows,
)
from simo.listening_results import MAX_SNAPSHOT, ResultsStore
from simo.preview_site import PreviewBoundary
from test_breeze_listening import matrix_fixture


class ResultsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        matrix, digest = matrix_fixture(self.root)
        prepare_listening(matrix, digest, self.root / "deck")
        self.deck = ListeningDeck(self.root / "deck" / "deck.json")
        self.directory = self.root / "results"
        self.store = ResultsStore(self.directory, self.deck)
        self.session_id = "a" * 32

    def snapshot(self) -> Record:
        return {
            "schema": "simo.breeze.listening.v1",
            "deck_sha256": self.deck.digest,
            "started": "2026-09-05T12:00:00Z",
            "exported": "2026-09-05T12:00:01Z",
            "conditions": "SYNTHETIC TRANSPORT FIXTURE; NOT LISTENER FEEDBACK",
            "browser": "CPU fixture",
            "player": "preview-player/listening-v1",
            "manifest": None,
            "ratings": [],
            "preferences": [],
            "attempts": [],
            "quality_accepted": False,
            "acoustic_onset": "unmeasured",
            "limits": "No physical playback performed.",
            "view": {"position": 0, "clip": "A"},
        }

    def attempt(self, status: str = "running") -> Record:
        case = rows(self.deck.deck["cases"])[0]
        clip = rows(case["clips"])[0]
        return {
            "ordinal": 0,
            "lane": "recorded",
            "case_id": case["id"],
            "clip_id": clip["id"],
            "status": status,
            "started": "2026-09-05T12:00:01Z",
            "listener": {
                "heard": "uncertain",
                "gaps": "uncertain",
                "start": "unreported",
                "notes": "",
            },
        }

    def test_restart_idempotency_old_retry_and_revision_conflicts(self) -> None:
        first = self.snapshot()
        ack = self.store.save(self.session_id, 1, first)
        restarted = ResultsStore(self.directory, self.deck)
        self.assertEqual(restarted.load(self.session_id)["snapshot"], first)
        self.assertEqual(restarted.save(self.session_id, 1, first), ack)
        second = {**first, "conditions": "updated synthetic fixture"}
        restarted.save(self.session_id, 2, second)
        self.assertEqual(restarted.save(self.session_id, 1, first), ack)
        for revision in (1, 2, 4):
            with self.assertRaises(FileExistsError):
                restarted.save(self.session_id, revision, {**second, "conditions": "conflict"})
        self.assertEqual(restarted.load(self.session_id)["snapshot"], second)

    def test_concurrent_stale_writers_cannot_overwrite(self) -> None:
        self.store.save(self.session_id, 1, self.snapshot())

        def writer(note: str) -> str:
            try:
                self.store.save(self.session_id, 2, {**self.snapshot(), "conditions": note})
            except FileExistsError:
                return "conflict"
            return "saved"

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(writer, ("one", "two")), ["saved", "conflict"])

    def test_partial_and_terminal_attempts_are_retained_without_acceptance(self) -> None:
        first = self.snapshot()
        first["attempts"] = [self.attempt()]
        self.store.save(self.session_id, 1, first)
        self.assertEqual(
            rows(obj(self.store.load(self.session_id)["snapshot"])["attempts"])[0]["status"],
            "running",
        )
        stopped = copy.deepcopy(first)
        attempt = rows(stopped["attempts"])[0]
        attempt.update(status="stopped", error="Page closed before completion")
        self.store.save(self.session_id, 2, stopped)
        observed = copy.deepcopy(stopped)
        obj(rows(observed["attempts"])[0]["listener"])["heard"] = "no"
        self.store.save(self.session_id, 3, observed)
        invalid_history: tuple[Record, ...] = (
            first,
            {**observed, "attempts": []},
            {**observed, "quality_accepted": True},
        )
        for changed in invalid_history:
            with self.assertRaises(ValueError):
                self.store.save(self.session_id, 4, changed)

    def test_partial_radio_answers_and_clip_hashes(self) -> None:
        clip_id, clip = next(iter(self.deck.clips.items()))
        rating = {
            "clip_id": clip_id,
            "pcm_sha256": clip["pcm_sha256"],
            "notes": "",
            "answered": ["natural"],
            **dict.fromkeys(RATING_FIELDS, "uncertain"),
        }
        snapshot = {**self.snapshot(), "ratings": [rating]}
        self.store.save(self.session_id, 1, snapshot)
        for invalid in (
            {**rating, "pcm_sha256": "0" * 64},
            {**rating, "answered": ["natural", "natural"]},
            {**rating, "natural": "maybe"},
        ):
            with self.assertRaises(ValueError):
                self.store.save("b" * 32, 1, {**snapshot, "ratings": [invalid]})

    def test_limits_nonfinite_identity_and_disk_quota_fail_before_write(self) -> None:
        for changed in (
            {"deck_sha256": "0" * 64},
            {"conditions": "x" * 4097},
            {"manifest": {"value": float("inf")}},
            {"manifest": {"value": "x" * MAX_SNAPSHOT}},
            {"view": {"position": 18, "clip": "A"}},
        ):
            with self.assertRaises(ValueError):
                self.store.save(self.session_id, 1, {**self.snapshot(), **changed})
        with patch("simo.listening_results.MAX_STORAGE", 1), self.assertRaises(OverflowError):
            self.store.save(self.session_id, 1, self.snapshot())
        with patch("simo.listening_results.MAX_SESSIONS", 0), self.assertRaises(OverflowError):
            self.store.save(self.session_id, 1, self.snapshot())
        with self.assertRaises(FileNotFoundError):
            self.store.load(self.session_id)

    def test_private_storage_and_corruption_fail_closed(self) -> None:
        public = self.root / "public"
        public.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError, "private"):
            ResultsStore(public, self.deck)
        alias = self.root / "alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            ResultsStore(alias, self.deck)
        self.store.save(self.session_id, 1, self.snapshot())
        with closing(sqlite3.connect(self.store.path)) as database, database:
            database.execute("UPDATE snapshots SET payload=?", (b"{}",))
        with self.assertRaisesRegex(ValueError, "damaged"):
            self.store.load(self.session_id)

    async def test_http_roundtrip_no_listing_and_request_boundaries(self) -> None:
        app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        app.add_middleware(PreviewBoundary, authorities=frozenset({"example.test"}))  # ty: ignore[invalid-argument-type]
        attach_listening(app, self.deck.path, results=self.directory)
        headers = {"X-Simo-Listening-Deck": self.deck.digest, "Origin": "https://example.test"}
        route = f"/api/listening/results/{self.session_id}"
        payload = {"revision": 1, "snapshot": self.snapshot()}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://example.test"
        ) as client:
            self.assertTrue((await client.get("/api/listening")).json()["server_results"])
            self.assertEqual((await client.get(route, headers=headers)).status_code, 404)
            saved = await client.put(route, json=payload, headers=headers)
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(
                (await client.put(route, json=payload, headers=headers)).json(), saved.json()
            )
            restored = await client.get(route, headers=headers)
            self.assertEqual(restored.json()["snapshot"], payload["snapshot"])
            self.assertIn("no-store", restored.headers["cache-control"])
            self.assertNotIn("access-control-allow-origin", restored.headers)
            self.assertEqual(
                (await client.get(route + "?deck=x", headers=headers)).status_code, 409
            )
            self.assertEqual(
                (
                    await client.put(
                        route, json=payload, headers={"X-Simo-Listening-Deck": self.deck.digest}
                    )
                ).status_code,
                403,
            )
            self.assertEqual(
                (
                    await client.put(
                        route, json=payload, headers={**headers, "Origin": "https://evil.test"}
                    )
                ).status_code,
                403,
            )
            self.assertEqual(
                (
                    await client.put(
                        route, json=payload, headers={**headers, "X-Simo-Listening-Deck": "b" * 64}
                    )
                ).status_code,
                409,
            )
            invalid = json.dumps(payload).replace(
                '"manifest": null', '"manifest": {"overflow": 1e999}'
            )
            self.assertEqual(
                (
                    await client.put(
                        route,
                        content=invalid,
                        headers={**headers, "Content-Type": "application/json"},
                    )
                ).status_code,
                422,
            )
            self.assertEqual(
                (
                    await client.put(
                        route,
                        content=b"x" * (MAX_SNAPSHOT + 129),
                        headers={**headers, "Content-Type": "application/json"},
                    )
                ).status_code,
                413,
            )
            for path in ("/api/listening/results", "/results.sqlite3", "/private-key.json"):
                self.assertEqual((await client.get(path, headers=headers)).status_code, 404)
            restored_snapshot = obj(cast(object, restored.json()["snapshot"]))
            self.assertFalse(restored_snapshot["quality_accepted"])
