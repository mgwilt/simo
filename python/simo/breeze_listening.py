"""Hash-bound recorded listening decks, deliberately separate from live inference."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import stat
import wave
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

Record = dict[str, object]
SCHEMA = "simo.breeze.listening.v1"
MAX_JSON = 4 * 1024 * 1024
MAX_PCM = 120 * 24000 * 2
ARMS = ("bf16", "int8", "bf16-backbone-int8-depth", "int8-backbone-bf16-depth")
RATING_FIELDS = (
    "heard_fully",
    "intelligible",
    "complete_words",
    "instruction",
    "natural",
    "gap_free",
)


def obj(value: object) -> Record:
    if not isinstance(value, dict):
        raise TypeError("Expected an object")
    return cast(Record, value)


def rows(value: object) -> list[Record]:
    if not isinstance(value, list):
        raise TypeError("Expected a list")
    return [obj(row) for row in cast(list[object], value)]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def read_bounded(path: Path, limit: int) -> bytes:
    # Open the same inode that is checked/read, rejecting symlink components.
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValueError("Symlinks are not listening artifacts")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("Safe listening artifact reads are unsupported on this platform")
    with os.fdopen(os.open(absolute, os.O_RDONLY | os.O_NOFOLLOW), "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Invalid or oversized listening artifact")
        payload = source.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Oversized listening artifact")
    return payload


def unique(pairs: list[tuple[str, object]]) -> Record:
    value: Record = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def read_json(path: Path) -> tuple[Record, str]:
    raw = read_bounded(path, MAX_JSON)
    return obj(cast(object, json.loads(raw, object_pairs_hook=unique))), sha(raw)


def pcm(raw: bytes) -> bytes:
    with wave.open(io.BytesIO(raw), "rb") as audio:
        if (
            audio.getnchannels(),
            audio.getsampwidth(),
            audio.getframerate(),
            audio.getcomptype(),
        ) != (1, 2, 24000, "NONE"):
            raise ValueError("Expected mono 24kHz PCM16 WAV")
        size = audio.getnframes() * 2
        if not 0 < size <= MAX_PCM:
            raise ValueError("Invalid WAV duration")
        data = audio.readframes(audio.getnframes() + 1)
        if len(data) != size:
            raise ValueError("Incomplete WAV")
        return data


def prepare_listening(comparison: Path, expected_sha: str, output: Path) -> Record:
    matrix, digest = read_json(comparison)
    if digest != expected_sha or matrix.get("completed") is not True:
        raise ValueError("Comparison changed or is incomplete")
    arms, cases, probes = (
        rows(matrix["arms"]),
        rows(matrix["cases"]),
        rows(matrix["validated_probes"]),
    )
    attempts = rows(matrix["attempts"])
    if (
        tuple(arm["name"] for arm in arms) != ARMS
        or len(probes) != 4
        or len(cases) != 18
        or len(attempts) != 4
    ):
        raise ValueError("Expected the complete four-arm, eighteen-case matrix")
    if [case["ordinal"] for case in cases] != list(range(18)):
        raise ValueError("Missing or duplicate case ordinal")
    files: dict[str, bytes] = {}
    clips_by_case: list[list[Record]] = [[] for _ in cases]
    mapping: Record = {}
    request_ids: set[str] = set()
    for arm, probe, attempt in zip(arms, probes, attempts, strict=True):
        name = str(arm["name"])
        if (
            probe["arm"] != arm
            or attempt.get("label") != name
            or attempt.get("completed") is not True
            or attempt.get("exit_code") != 0
        ):
            raise ValueError("Mismatched or failed matrix arm")
        report, report_sha = read_json(comparison.parent / name / "report.json")
        if report_sha != attempt["stdout_sha256"]:
            raise ValueError("Changed producer report")
        samples, artifacts = rows(report["samples"]), rows(report["audio_artifacts"])
        timed = rows(probe["timed"])
        if len(samples) != 18 or len(artifacts) != 18 or len(timed) != 18:
            raise ValueError("Expected all timed cases, without warmups")
        for ordinal, (case, sample, artifact, held) in enumerate(
            zip(cases, samples, artifacts, timed, strict=True)
        ):
            producer = obj(sample["producer"])
            request_id = str(producer["request_id"])
            if (
                re.fullmatch(r"portable-[0-9a-f]{32}", request_id) is None
                or request_id in request_ids
                or held["request_id"] != request_id
                or sample.get("failure") is not None
            ):
                raise ValueError("Incomplete, duplicate or mismatched producer case")
            if any(
                producer.get(key) is not value
                for key, value in (("completed", True), ("eos_reached", True), ("cancelled", False))
            ) or (sample["prompt"], sample["instruction"], sample["seed"]) != (
                case["text"],
                case["instruction"],
                case["seed"],
            ):
                raise ValueError("Incomplete or mismatched producer case")
            request_ids.add(request_id)
            source = Path(str(artifact["path"]))
            if (
                not source.is_relative_to(comparison.parent / name / "audio")
                or str(source) != held["path"]
            ):
                raise ValueError("Audio path escaped its exact matrix arm")
            raw = read_bounded(source, MAX_PCM + 65536)
            data = pcm(raw)
            if (
                sha(raw) != held["wav_sha256"]
                or sha(data) != held["pcm_sha256"]
                or sha(data) != artifact["pcm_sha256"]
            ):
                raise ValueError("Changed or incomplete audio")
            if (
                any(
                    value != len(data) // 2
                    for value in (held["samples"], artifact["samples"], producer["audio_samples"])
                )
                or producer["audio_samples"] != cast(int, producer["codec_frames"]) * 1920
                or artifact["sample_rate"] != 24000
            ):
                raise ValueError("Incomplete audio sample totals")
            clip_id = secrets.token_hex(16)
            files[clip_id] = raw
            clips_by_case[ordinal].append(
                {
                    "id": clip_id,
                    "samples": len(data) // 2,
                    "pcm_sha256": sha(data),
                    "wav_sha256": sha(raw),
                }
            )
            mapping[clip_id] = {
                "arm": name,
                "ordinal": ordinal,
                "report_sha256": report_sha,
                "source": str(source),
                "request_id": request_id,
            }
    order = list(range(18))
    random = secrets.SystemRandom()
    random.shuffle(order)
    deck_cases: list[Record] = []
    for ordinal in order:
        clips = clips_by_case[ordinal]
        random.shuffle(clips)
        for label, clip in zip("ABCD", clips, strict=True):
            clip["label"] = label
        deck_cases.append(
            {
                "id": secrets.token_hex(16),
                "text": cases[ordinal]["text"],
                "instruction": cases[ordinal]["instruction"],
                "seed": cases[ordinal]["seed"],
                "clips": clips,
            }
        )
    key: Record = {
        "schema": SCHEMA,
        "comparison_sha256": digest,
        "mapping": mapping,
        "asr_rows": matrix["asr_rows"],
        "identity": matrix["identity"],
    }
    deck = {
        "schema": SCHEMA,
        "kind": "recorded-matched",
        "sample_rate": 24000,
        "cases": deck_cases,
        "private_key_sha256": sha(encoded(key)),
    }
    deck_bytes = encoded(deck)
    key["deck_sha256"] = sha(deck_bytes)
    # Exclusive directory and files: partial failure cannot overwrite a prior deck.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    (output / "clips").mkdir(mode=0o700)
    for clip_id, raw in files.items():
        with (output / "clips" / f"{clip_id}.wav").open("xb") as target:
            target.write(raw)
    for name, payload in (("private-key.json", encoded(key)), ("deck.json", deck_bytes)):
        with (output / name).open("xb") as target:
            target.write(payload)
        (output / name).chmod(0o600)
    return {
        "deck": str(output / "deck.json"),
        "private_key": str(output / "private-key.json"),
        "deck_sha256": sha(deck_bytes),
        "clips": 72,
        "quality_accepted": False,
    }


class ListeningDeck:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.deck, self.digest = read_json(path)
        if (
            set(self.deck) != {"schema", "kind", "sample_rate", "cases", "private_key_sha256"}
            or self.deck["schema"] != SCHEMA
            or self.deck["kind"] != "recorded-matched"
            or self.deck["sample_rate"] != 24000
            or re.fullmatch(r"[0-9a-f]{64}", str(self.deck["private_key_sha256"])) is None
        ):
            raise ValueError("Invalid listening deck")
        self.clips: dict[str, Record] = {}
        cases = rows(self.deck["cases"])
        case_ids: set[str] = set()
        if len(cases) != 18:
            raise ValueError("Expected eighteen listening cases")
        for case in cases:
            if set(case) != {"id", "text", "instruction", "seed", "clips"}:
                raise ValueError("Unexpected public case fields")
            case_id = self._id(case["id"])
            if case_id in case_ids:
                raise ValueError("Duplicate case ID")
            case_ids.add(case_id)
            if (
                any(
                    not isinstance(case[field], str) or not 0 < len(str(case[field])) <= 4096
                    for field in ("text", "instruction")
                )
                or type(case["seed"]) is not int
            ):
                raise ValueError("Invalid case text or seed")
            clips = rows(case["clips"])
            if [clip["label"] for clip in clips] != list("ABCD"):
                raise ValueError("Expected four blinded labels")
            for clip in clips:
                if set(clip) != {"id", "label", "samples", "pcm_sha256", "wav_sha256"}:
                    raise ValueError("Unexpected public clip fields")
                clip_id = self._id(clip["id"])
                if (
                    clip_id in self.clips
                    or type(clip["samples"]) is not int
                    or not 0 < clip["samples"] <= MAX_PCM // 2
                ):
                    raise ValueError("Duplicate or invalid clip")
                if any(
                    re.fullmatch(r"[0-9a-f]{64}", str(clip[field])) is None
                    for field in ("pcm_sha256", "wav_sha256")
                ):
                    raise ValueError("Invalid clip hash")
                self.clips[clip_id] = clip
        for clip_id in self.clips:
            self.audio(clip_id)

    @staticmethod
    def _id(value: object) -> str:
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
            raise ValueError("Invalid opaque ID")
        return value

    def audio(self, clip_id: str) -> bytes:
        clip = self.clips[self._id(clip_id)]
        raw = read_bounded(self.path.parent / "clips" / f"{clip_id}.wav", MAX_PCM + 65536)
        data = pcm(raw)
        if (
            sha(raw) != clip["wav_sha256"]
            or sha(data) != clip["pcm_sha256"]
            or len(data) != cast(int, clip["samples"]) * 2
        ):
            raise ValueError("Listening audio changed")
        return data


def attach_listening(app: FastAPI, path: Path, *, results: Path | None = None) -> None:
    deck = ListeningDeck(path)
    if results is not None:
        from simo.listening_results import attach_results

        attach_results(app, deck, results)

    @app.get("/api/listening", include_in_schema=False)
    def listing(request: Request) -> Record:
        if request.query_params:
            raise HTTPException(status_code=400, detail="No listening query fields")
        return {**deck.deck, "deck_sha256": deck.digest, "server_results": results is not None}

    @app.post("/api/listening/clips/{clip_id}", include_in_schema=False)
    async def clip(clip_id: str, request: Request) -> Response:
        if request.query_params or request.headers.get("X-Simo-Listening-Deck") != deck.digest:
            raise HTTPException(status_code=409, detail="Listening deck mismatch")
        async for chunk in request.stream():
            if chunk:
                raise HTTPException(status_code=400, detail="Listening requests are bodyless")
        try:
            data = deck.audio(clip_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Unknown clip") from error
        except (ValueError, OSError, wave.Error) as error:
            raise HTTPException(
                status_code=409, detail="Recorded audio unavailable or changed"
            ) from error
        return Response(
            data,
            media_type="audio/pcm",
            headers={
                "Cache-Control": "no-store",
                "X-Simo-Cache": "RECORDED",
                "X-Simo-Listening-Deck": deck.digest,
                "X-Simo-PCM-SHA256": sha(data),
                "X-Simo-Audio-Samples": str(len(data) // 2),
                "X-Sample-Rate": "24000",
                "X-Sample-Format": "s16le",
            },
        )


def verify_listening(deck_path: Path, key_path: Path, ratings_path: Path) -> Record:
    deck = ListeningDeck(deck_path)
    key, _ = read_json(key_path)
    export, export_sha = read_json(ratings_path)
    if (
        key.get("deck_sha256") != deck.digest
        or export.get("deck_sha256") != deck.digest
        or export.get("schema") != SCHEMA
    ):
        raise ValueError("Stale or mismatched listening export/key")
    if (
        set(key)
        != {"schema", "comparison_sha256", "mapping", "asr_rows", "identity", "deck_sha256"}
        or key["schema"] != SCHEMA
        or sha(encoded({name: value for name, value in key.items() if name != "deck_sha256"}))
        != deck.deck["private_key_sha256"]
    ):
        raise ValueError("Private key content changed")
    mapping = obj(key["mapping"])
    if set(mapping) != set(deck.clips):
        raise ValueError("Private key does not cover the full deck")
    identities: set[tuple[str, int]] = set()
    for value in mapping.values():
        item = obj(value)
        if (
            set(item) != {"arm", "ordinal", "report_sha256", "source", "request_id"}
            or item["arm"] not in ARMS
            or type(item["ordinal"]) is not int
            or not 0 <= item["ordinal"] < 18
        ):
            raise ValueError("Invalid private recipe mapping")
        identities.add((str(item["arm"]), item["ordinal"]))
    if len(identities) != 72:
        raise ValueError("Incomplete private recipe coverage")
    for case in rows(deck.deck["cases"]):
        group = [obj(mapping[str(clip["id"])]) for clip in rows(case["clips"])]
        if {item["arm"] for item in group} != set(ARMS) or len(
            {item["ordinal"] for item in group}
        ) != 1:
            raise ValueError("Mismatched blinded recipe group")
    ratings = rows(export["ratings"])
    ids = [str(row["clip_id"]) for row in ratings]
    if len(ids) != len(set(ids)) or set(ids) - set(deck.clips):
        raise ValueError("Duplicate or unknown rating")
    for row in ratings:
        if (
            any(row.get(field) not in ("yes", "no", "uncertain") for field in RATING_FIELDS)
            or row.get("pcm_sha256") != deck.clips[str(row["clip_id"])]["pcm_sha256"]
        ):
            raise ValueError("Invalid or changed clip rating")
    attempts = rows(export["attempts"])
    for ordinal, attempt in enumerate(attempts):
        if (
            attempt.get("ordinal") != ordinal
            or attempt.get("lane") not in ("recorded", "fresh")
            or attempt.get("status") not in ("complete", "stopped", "failed")
        ):
            raise ValueError("Invalid attempt history")
        if attempt["lane"] == "recorded" and attempt.get("clip_id") not in deck.clips:
            raise ValueError("Unknown attempted clip")
    return {
        "deck_sha256": deck.digest,
        "export_sha256": export_sha,
        "rated": len(ratings),
        "unrated": len(deck.clips) - len(ratings),
        "attempts": len(attempts),
        "all_rated": len(ratings) == len(deck.clips),
        "quality_accepted": False,
        "acoustic_onset": "unmeasured",
        "note": "Identity/structure verified only; listener reports and browser telemetry are not acoustic or release attestation.",
        "ratings_by_arm": [
            {
                **row,
                "arm": obj(mapping[str(row["clip_id"])])["arm"],
                "ordinal": obj(mapping[str(row["clip_id"])])["ordinal"],
            }
            for row in ratings
        ],
    }
