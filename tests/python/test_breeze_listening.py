from __future__ import annotations

import io
import tempfile
import unittest
import wave
from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI
from simo.breeze_listening import (
    ARMS,
    RATING_FIELDS,
    SCHEMA,
    ListeningDeck,
    attach_listening,
    encoded,
    obj,
    prepare_listening,
    read_bounded,
    read_json,
    rows,
    sha,
    verify_listening,
)


def matrix_fixture(root: Path) -> tuple[Path, str]:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\1\0" * 1920)
    raw = buffer.getvalue()
    cases = [
        {
            "ordinal": index,
            "text": f"text {index // 3}",
            "instruction": "speak calmly",
            "seed": (17, 29, 42)[index % 3],
        }
        for index in range(18)
    ]
    arms = [{"name": name} for name in ARMS]
    probes: list[object] = []
    attempts: list[object] = []
    for arm_index, arm in enumerate(arms):
        folder = root / arm["name"] / "audio"
        folder.mkdir(parents=True)
        samples: list[object] = []
        artifacts: list[object] = []
        timed: list[object] = []
        for index, case in enumerate(cases):
            path = folder / f"sample-{index}.wav"
            path.write_bytes(raw)
            request_id = f"portable-{arm_index * 18 + index:032x}"
            producer = {
                "request_id": request_id,
                "completed": True,
                "eos_reached": True,
                "cancelled": False,
                "audio_samples": 1920,
                "codec_frames": 1,
            }
            samples.append(
                {
                    "prompt": case["text"],
                    "instruction": case["instruction"],
                    "seed": case["seed"],
                    "producer": producer,
                    "failure": None,
                }
            )
            artifact = {
                "path": str(path),
                "pcm_sha256": sha(b"\1\0" * 1920),
                "samples": 1920,
                "sample_rate": 24000,
            }
            artifacts.append(artifact)
            timed.append({**artifact, "request_id": request_id, "wav_sha256": sha(raw)})
        report = encoded({"samples": samples, "audio_artifacts": artifacts})
        (folder.parent / "report.json").write_bytes(report)
        attempts.append(
            {"label": arm["name"], "completed": True, "exit_code": 0, "stdout_sha256": sha(report)}
        )
        probes.append({"arm": arm, "timed": timed, "warmups": [{"do_not_serve": "warmup"}]})
    matrix = root / "comparison.json"
    data = encoded(
        {
            "completed": True,
            "arms": arms,
            "cases": cases,
            "validated_probes": probes,
            "attempts": attempts,
            "asr_rows": [{"private_asr": "secret hint"}],
            "identity": {"private_model": "source"},
        }
    )
    matrix.write_bytes(data)
    return matrix, sha(data)


class ListeningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.matrix, self.digest = matrix_fixture(self.root)
        self.output = self.root / "deck"

    def prepare(self) -> ListeningDeck:
        prepare_listening(self.matrix, self.digest, self.output)
        return ListeningDeck(self.output / "deck.json")

    def test_full_schedule_keeps_equal_pcm_clips_distinct_and_blinded(self) -> None:
        deck = self.prepare()
        self.assertEqual(len(deck.clips), 72)
        self.assertEqual(len({clip["pcm_sha256"] for clip in deck.clips.values()}), 1)
        public = encoded(deck.deck)
        for private in (
            b"bf16",
            b"int8",
            b"secret hint",
            b"private_model",
            b"request_id",
            b"path",
            b"warmup",
        ):
            self.assertNotIn(private, public)
        key, _ = read_json(self.output / "private-key.json")
        self.assertEqual(key["deck_sha256"], deck.digest)
        self.assertEqual(len(obj(key["mapping"])), 72)
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_changed_matrix_report_and_pcm_fail_before_creating_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "Comparison"):
            prepare_listening(self.matrix, "0" * 64, self.output)
        report = self.root / "bf16" / "report.json"
        held = report.read_bytes()
        report.write_bytes(held + b" ")
        with self.assertRaisesRegex(ValueError, "producer report"):
            self.prepare()
        report.write_bytes(held)
        audio = self.root / "bf16" / "audio" / "sample-0.wav"
        audio.write_bytes(audio.read_bytes()[:-2])
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_symlinks_duplicates_and_private_manifest_fields_rejected(self) -> None:
        deck = self.prepare()
        clip_id = next(iter(deck.clips))
        audio = self.output / "clips" / f"{clip_id}.wav"
        moved = self.root / "moved.wav"
        audio.rename(moved)
        audio.symlink_to(moved)
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            deck.audio(clip_id)
        alias = self.root / "alias"
        alias.symlink_to(self.output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            read_bounded(alias / "deck.json", 1024)
        data = deck.deck
        data["private_key"] = "not allowed"
        (self.output / "deck.json").write_bytes(encoded(data))
        with self.assertRaisesRegex(ValueError, "Invalid listening deck"):
            ListeningDeck(self.output / "deck.json")
        duplicate = self.root / "duplicate.json"
        duplicate.write_text('{"schema":1,"schema":2}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            read_json(duplicate)

    async def test_only_opaque_full_unchanged_pcm_is_served(self) -> None:
        deck = self.prepare()
        app = FastAPI()
        attach_listening(app, self.output / "deck.json")
        clip_id = next(iter(deck.clips))
        headers = {"X-Simo-Listening-Deck": deck.digest}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://example.test"
        ) as client:
            listing = await client.get("/api/listening")
            self.assertNotIn("mapping", obj(cast(object, listing.json())))
            route = f"/api/listening/clips/{clip_id}"
            response = await client.post(route, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, deck.audio(clip_id))
            self.assertEqual(response.headers["X-Simo-Cache"], "RECORDED")
            self.assertNotIn("X-Simo-Runtime-Fingerprint", response.headers)
            self.assertEqual((await client.post(route)).status_code, 409)
            self.assertEqual(
                (await client.post(route + "?path=private-key.json", headers=headers)).status_code,
                409,
            )
            self.assertEqual(
                (await client.post(route, headers=headers, content=b"x")).status_code, 400
            )
            for path in (
                "/private-key.json",
                "/deck.json",
                "/clips/" + clip_id + ".wav",
                "/api/listening/../private-key.json",
            ):
                self.assertEqual((await client.get(path)).status_code, 404)
            self.assertEqual(
                (
                    await client.post("/api/listening/clips/" + "f" * 32, headers=headers)
                ).status_code,
                404,
            )
            audio = self.output / "clips" / f"{clip_id}.wav"
            raw = audio.read_bytes()
            audio.write_bytes(raw[:-1] + b"\1")
            self.assertEqual((await client.post(route, headers=headers)).status_code, 409)

    def test_export_retains_incomplete_uncertain_and_replay_without_acceptance(self) -> None:
        deck = self.prepare()
        clip_id, clip = next(iter(deck.clips.items()))
        rating = {
            "clip_id": clip_id,
            "pcm_sha256": clip["pcm_sha256"],
            **dict.fromkeys(RATING_FIELDS, "uncertain"),
        }
        export = {
            "schema": SCHEMA,
            "deck_sha256": deck.digest,
            "ratings": [rating],
            "attempts": [
                {"ordinal": ordinal, "lane": "recorded", "clip_id": clip_id, "status": state}
                for ordinal, state in enumerate(("failed", "stopped", "complete"))
            ],
        }
        path = self.root / "ratings.json"
        path.write_bytes(encoded(export))
        result = verify_listening(deck.path, self.output / "private-key.json", path)
        self.assertEqual((result["rated"], result["unrated"], result["attempts"]), (1, 71, 3))
        self.assertFalse(result["quality_accepted"])
        self.assertEqual(result["acoustic_onset"], "unmeasured")
        self.assertEqual(rows(result["ratings_by_arm"])[0]["clip_id"], clip_id)
        export["ratings"] = [rating, rating]
        path.write_bytes(encoded(export))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify_listening(deck.path, self.output / "private-key.json", path)
        export["ratings"] = []
        export["deck_sha256"] = "0" * 64
        path.write_bytes(encoded(export))
        with self.assertRaisesRegex(ValueError, "Stale"):
            verify_listening(deck.path, self.output / "private-key.json", path)

    def test_private_recipe_mapping_is_cryptographically_bound_to_public_deck(self) -> None:
        deck = self.prepare()
        key_path = self.output / "private-key.json"
        key, _ = read_json(key_path)
        path = self.root / "ratings.json"
        path.write_bytes(
            encoded({"schema": SCHEMA, "deck_sha256": deck.digest, "ratings": [], "attempts": []})
        )
        first = obj(next(iter(obj(key["mapping"]).values())))
        first["arm"] = "int8" if first["arm"] != "int8" else "bf16"
        key_path.write_bytes(encoded(key))
        with self.assertRaisesRegex(ValueError, "Private key content changed"):
            verify_listening(deck.path, key_path, path)
