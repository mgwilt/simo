"""Two-process synthetic conversational lab using LiveKit Agents end to end."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Final, cast
from uuid import uuid4

from simo.config import RunMode, RuntimeConfig
from simo.livekit_room import LiveKitRoomConfig
from simo.livekit_runtime import (
    LiveKitAliasRunRequest,
    LiveKitAliasRunResult,
    LiveKitAliasRuntime,
)
from simo.persistence import SimoStore

_SERVER_HOST: Final = "127.0.0.1"
_DEV_API_KEY: Final = "devkey"
_DEV_API_SECRET: Final = "secret"


@dataclass(frozen=True, slots=True)
class AgentLabParticipant:
    role: str
    process_id: int
    data_dir: str
    run: LiveKitAliasRunResult

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "process_id": self.process_id,
            "data_dir": self.data_dir,
            "run": self.run.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class TwoAgentLabResult:
    server_version: str
    room_name: str
    artifacts_dir: str
    participants: tuple[AgentLabParticipant, AgentLabParticipant]
    processes_distinct: bool
    participant_sids_distinct: bool
    self_echo_turns: int
    unexpected_identity_turns: int
    attribution_errors: int
    duplicate_turns: int
    incomplete_generated_turns: int
    interrupted_spoken_turns: int
    raw_audio_retained: bool
    synthetic_audio_user_turns: int
    transcripts_reviewable: bool
    elapsed_ms: int

    def as_dict(self) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(self))
        payload["participants"] = [participant.as_dict() for participant in self.participants]
        return payload


async def run_two_agent_lab(
    *,
    artifacts_dir: Path | None = None,
    server_binary: str | None = None,
    turns_per_alias: int = 2,
    max_duration_s: float = 180.0,
) -> TwoAgentLabResult:
    """Run two persisted aliases through only the self-hosted WebRTC audio path."""

    if turns_per_alias <= 0:
        raise ValueError("turns per alias must be positive")
    if max_duration_s <= 0:
        raise ValueError("lab duration must be positive")
    binary = server_binary or shutil.which("livekit-server")
    if binary is None:
        raise RuntimeError("livekit-server is required; install the Homebrew livekit formula")
    started = monotonic()
    run_id = uuid4().hex[:12]
    root = (artifacts_dir or Path(".artifacts/livekit-agents-lab") / run_id).resolve()
    root.mkdir(parents=True, exist_ok=False)
    data_a = root / "ada"
    data_b = root / "bea"
    store_a = SimoStore(data_a)
    store_b = SimoStore(data_b)
    alias_a = store_a.create_alias(
        "Ada",
        persona_summary="A precise, reflective conversationalist.",
        persona_instructions=(
            "You are Ada. Speak in concise, thoughtful sentences, remember what Bea says, "
            "and ask one natural follow-up question at a time. Never claim to be Bea."
        ),
    )
    alias_b = store_b.create_alias(
        "Bea",
        persona_summary="A warm, playful conversationalist.",
        persona_instructions=(
            "You are Bea. Speak warmly with light humor, respond directly to Ada, and ask "
            "one curious follow-up question at a time. Never claim to be Ada."
        ),
    )
    room_name = f"simo-agents-{run_id}"
    identity_a = f"alias-{alias_a.alias_id}"
    identity_b = f"alias-{alias_b.alias_id}"
    server_port = _available_port(socket.SOCK_STREAM)
    udp_port = _available_port(socket.SOCK_DGRAM)
    server_url = f"ws://{_SERVER_HOST}:{server_port}"
    server_version = _server_version(binary)
    server = await asyncio.create_subprocess_exec(
        binary,
        "--dev",
        "--bind",
        _SERVER_HOST,
        "--node-ip",
        _SERVER_HOST,
        "--udp-port",
        str(udp_port),
        "--config-body",
        f"port: {server_port}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await _wait_for_server(server_port, timeout_s=8.0)
        environment = os.environ.copy()
        environment.update(
            {
                "SIMO_LIVEKIT_URL": server_url,
                "SIMO_LIVEKIT_API_KEY": _DEV_API_KEY,
                "SIMO_LIVEKIT_API_SECRET": _DEV_API_SECRET,
                "LOGURU_AUTOINIT": "False",
            }
        )
        responder = await _spawn_participant(
            role="responder",
            data_dir=data_b,
            alias_id=alias_b.alias_id,
            remote_alias_id=alias_a.alias_id,
            remote_display_name=alias_a.display_name,
            room_name=room_name,
            local_identity=identity_b,
            remote_identity=identity_a,
            max_spoken_turns=turns_per_alias,
            max_duration_s=max_duration_s,
            opening_instructions=None,
            environment=environment,
        )
        initiator = await _spawn_participant(
            role="initiator",
            data_dir=data_a,
            alias_id=alias_a.alias_id,
            remote_alias_id=alias_b.alias_id,
            remote_display_name=alias_b.display_name,
            room_name=room_name,
            local_identity=identity_a,
            remote_identity=identity_b,
            max_spoken_turns=turns_per_alias + 1,
            max_duration_s=max_duration_s,
            opening_instructions=(
                "Begin the conversation now. Greet Bea by name, say that your favorite color "
                "is ultramarine, and ask what color Bea likes. Keep it to two short sentences."
            ),
            environment=environment,
        )
        participants = await asyncio.wait_for(
            asyncio.gather(
                _collect_participant(initiator, "initiator"),
                _collect_participant(responder, "responder"),
            ),
            timeout=max_duration_s + 90.0,
        )
    finally:
        if server.returncode is None:
            server.terminate()
            try:
                await asyncio.wait_for(server.wait(), timeout=5.0)
            except TimeoutError:
                server.kill()
                await server.wait()

    ordered = tuple(sorted(participants, key=lambda item: item.role))
    if len(ordered) != 2:
        raise RuntimeError("two LiveKit Agents participant results were not collected")
    first, second = ordered
    checks_a = _inspect_transcript(
        store_a,
        first.run.conversation_id if first.role == "initiator" else second.run.conversation_id,
        local_participant_id=f"alias:{alias_a.alias_id}",
        local_transport_identity=identity_a,
        remote_participant_id=f"alias:{alias_b.alias_id}",
        remote_transport_identity=identity_b,
    )
    checks_b = _inspect_transcript(
        store_b,
        first.run.conversation_id if first.role == "responder" else second.run.conversation_id,
        local_participant_id=f"alias:{alias_b.alias_id}",
        local_transport_identity=identity_b,
        remote_participant_id=f"alias:{alias_a.alias_id}",
        remote_transport_identity=identity_a,
    )
    result = TwoAgentLabResult(
        server_version,
        room_name,
        str(root),
        (first, second),
        first.process_id != second.process_id,
        first.run.local_participant_sid != second.run.local_participant_sid,
        checks_a.self_echo_turns + checks_b.self_echo_turns,
        checks_a.unexpected_identity_turns + checks_b.unexpected_identity_turns,
        checks_a.attribution_errors + checks_b.attribution_errors,
        checks_a.duplicate_turns + checks_b.duplicate_turns,
        checks_a.incomplete_generated_turns + checks_b.incomplete_generated_turns,
        checks_a.interrupted_spoken_turns + checks_b.interrupted_spoken_turns,
        first.run.raw_audio_retained or second.run.raw_audio_retained,
        checks_a.user_turns + checks_b.user_turns,
        checks_a.reviewable and checks_b.reviewable,
        round((monotonic() - started) * 1_000),
    )
    _validate_result(result, turns_per_alias=turns_per_alias)
    (root / "result.json").write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


@dataclass(frozen=True, slots=True)
class _TranscriptChecks:
    self_echo_turns: int
    unexpected_identity_turns: int
    attribution_errors: int
    duplicate_turns: int
    incomplete_generated_turns: int
    interrupted_spoken_turns: int
    user_turns: int
    reviewable: bool


def _inspect_transcript(
    store: SimoStore,
    conversation_id: str,
    *,
    local_participant_id: str,
    local_transport_identity: str,
    remote_participant_id: str,
    remote_transport_identity: str,
) -> _TranscriptChecks:
    detail = store.get_conversation(conversation_id)
    transcript = store.transcript(conversation_id)
    self_echo = 0
    unexpected = 0
    attribution = 0
    incomplete_generated = 0
    interrupted_spoken = 0
    user_turns = 0
    for event in detail.events:
        if event.event_type == "assistant.generated" and not _complete_voice_text(event.text):
            incomplete_generated += 1
        if event.event_type == "assistant.spoken" and event.interrupted:
            interrupted_spoken += 1
        if event.event_type != "user.transcript.final":
            continue
        user_turns += 1
        transport = event.metadata.get("transport_participant_id")
        if transport == local_transport_identity:
            self_echo += 1
        if transport != remote_transport_identity:
            unexpected += 1
        if event.participant_id != remote_participant_id:
            attribution += 1
    duplicate = sum(
        first.participant_id == second.participant_id and first.text == second.text
        for first, second in pairwise(transcript)
    )
    participants = {participant.participant_id for participant in detail.participants}
    reviewable = (
        bool(transcript)
        and local_participant_id in participants
        and remote_participant_id in participants
        and not detail.conversation.raw_audio_retained
    )
    return _TranscriptChecks(
        self_echo,
        unexpected,
        attribution,
        duplicate,
        incomplete_generated,
        interrupted_spoken,
        user_turns,
        reviewable,
    )


def _complete_voice_text(text: str | None) -> bool:
    if text is None:
        return False
    selected = text.rstrip().rstrip("\"'”)]}").rstrip()
    return bool(selected) and selected[-1] in ".!?…"


def _validate_result(result: TwoAgentLabResult, *, turns_per_alias: int) -> None:
    if not result.processes_distinct or not result.participant_sids_distinct:
        raise RuntimeError("LiveKit Agents lab did not use two independent participants")
    if result.self_echo_turns or result.unexpected_identity_turns or result.attribution_errors:
        raise RuntimeError("LiveKit Agents lab violated participant identity isolation")
    if result.duplicate_turns:
        raise RuntimeError("LiveKit Agents lab persisted a duplicate adjacent turn")
    if result.incomplete_generated_turns:
        raise RuntimeError("LiveKit Agents lab generated an incomplete voice turn")
    if result.raw_audio_retained:
        raise RuntimeError("LiveKit Agents lab retained raw audio")
    if result.synthetic_audio_user_turns < turns_per_alias * 2 - 1:
        raise RuntimeError("LiveKit Agents lab did not complete the bounded audio conversation")
    if not result.transcripts_reviewable:
        raise RuntimeError("LiveKit Agents lab transcripts are not reviewable")


async def run_participant(
    *,
    role: str,
    data_dir: Path,
    alias_id: str,
    remote_alias_id: str,
    remote_display_name: str,
    room_name: str,
    local_identity: str,
    remote_identity: str,
    max_spoken_turns: int,
    max_duration_s: float,
    opening_instructions: str | None,
) -> AgentLabParticipant:
    store = SimoStore(data_dir)
    config = RuntimeConfig.from_environment(mode=RunMode.LIVE)
    room_config = LiveKitRoomConfig.from_environment(
        room_name=room_name,
        participant_identity=local_identity,
        participant_name=f"Simo {role}",
        allowed_remote_identities=frozenset({remote_identity}),
    )
    runtime = LiveKitAliasRuntime(store, config, room_config)
    result = await runtime.run(
        LiveKitAliasRunRequest(
            alias_id,
            f"alias:{remote_alias_id}",
            remote_display_name,
            remote_identity,
            opening_instructions=opening_instructions,
            max_spoken_turns=max_spoken_turns,
            max_duration_s=max_duration_s,
            complete_on_close=True,
        )
    )
    return AgentLabParticipant(role, os.getpid(), str(data_dir), result)


async def _spawn_participant(
    *,
    role: str,
    data_dir: Path,
    alias_id: str,
    remote_alias_id: str,
    remote_display_name: str,
    room_name: str,
    local_identity: str,
    remote_identity: str,
    max_spoken_turns: int,
    max_duration_s: float,
    opening_instructions: str | None,
    environment: dict[str, str],
) -> asyncio.subprocess.Process:
    command = [
        sys.executable,
        "-m",
        "simo.livekit_agent_lab",
        "participant",
        "--role",
        role,
        "--data-dir",
        str(data_dir),
        "--alias-id",
        alias_id,
        "--remote-alias-id",
        remote_alias_id,
        "--remote-display-name",
        remote_display_name,
        "--room",
        room_name,
        "--local-identity",
        local_identity,
        "--remote-identity",
        remote_identity,
        "--max-spoken-turns",
        str(max_spoken_turns),
        "--max-duration-s",
        str(max_duration_s),
    ]
    if opening_instructions is not None:
        command.extend(["--opening-instructions", opening_instructions])
    return await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
        cwd=Path(__file__).resolve().parents[2],
    )


async def _collect_participant(
    process: asyncio.subprocess.Process,
    role: str,
) -> AgentLabParticipant:
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        diagnostic = stderr.decode("utf-8", errors="replace")[-4_000:]
        raise RuntimeError(
            f"{role} LiveKit Agents participant exited with status {process.returncode}: "
            f"{diagnostic}"
        )
    try:
        lines = [line for line in stdout.decode("utf-8").splitlines() if line.strip()]
        value = cast(object, json.loads(lines[-1]))
    except (IndexError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{role} LiveKit Agents participant returned invalid JSON") from error
    if not isinstance(value, dict):
        raise TypeError(f"{role} LiveKit Agents participant result must be an object")
    payload = cast(dict[str, object], value)
    raw_run = payload.get("run")
    if not isinstance(raw_run, dict):
        raise TypeError("LiveKit Agents participant run result must be an object")
    run = _parse_run(cast(dict[str, object], raw_run))
    return AgentLabParticipant(
        _required_str(payload, "role"),
        _required_int(payload, "process_id"),
        _required_str(payload, "data_dir"),
        run,
    )


def _parse_run(payload: dict[str, object]) -> LiveKitAliasRunResult:
    session_events = payload.get("session_events")
    if not isinstance(session_events, dict):
        raise TypeError("LiveKit alias run session events must be integer values")
    raw_session_events = cast(dict[object, object], session_events)
    if any(
        not isinstance(key, str) or not isinstance(value, int)
        for key, value in raw_session_events.items()
    ):
        raise TypeError("LiveKit alias run session events must be integer values")
    typed_session_events = {
        cast(str, key): cast(int, value) for key, value in raw_session_events.items()
    }
    return LiveKitAliasRunResult(
        _required_str(payload, "alias_id"),
        _required_str(payload, "conversation_id"),
        _required_str(payload, "local_transport_identity"),
        _required_str(payload, "local_participant_sid"),
        _required_str(payload, "remote_transport_identity"),
        _required_int(payload, "event_count"),
        _required_int(payload, "transcript_turns"),
        _required_int(payload, "spoken_turns"),
        _required_int(payload, "world_revision"),
        _required_str(payload, "close_reason"),
        _required_bool(payload, "raw_audio_retained"),
        typed_session_events,
    )


async def _wait_for_server(port: int, *, timeout_s: float) -> None:
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        try:
            reader, writer = await asyncio.open_connection(_SERVER_HOST, port)
            writer.write(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.read(32), timeout=1.0)
            writer.close()
            await writer.wait_closed()
            if response.startswith(b"HTTP/"):
                return
        except (OSError, TimeoutError):
            await asyncio.sleep(0.05)
    raise RuntimeError("LiveKit server did not become ready")


def _available_port(socket_type: socket.SocketKind) -> int:
    with socket.socket(socket.AF_INET, socket_type) as selected:
        selected.bind((_SERVER_HOST, 0))
        return cast(int, selected.getsockname()[1])


def _server_version(binary: str) -> str:
    completed = subprocess.run(
        [binary, "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    selected = completed.stdout.strip()
    if not selected:
        raise RuntimeError("livekit-server did not report a version")
    return selected


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise TypeError(f"participant result {key} must be a string")
    return value


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise TypeError(f"participant result {key} must be an integer")
    return value


def _required_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"participant result {key} must be a boolean")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simo.livekit_agent_lab")
    subcommands = parser.add_subparsers(dest="command", required=True)
    participant = subcommands.add_parser("participant")
    participant.add_argument("--role", choices=("initiator", "responder"), required=True)
    participant.add_argument("--data-dir", type=Path, required=True)
    participant.add_argument("--alias-id", required=True)
    participant.add_argument("--remote-alias-id", required=True)
    participant.add_argument("--remote-display-name", required=True)
    participant.add_argument("--room", required=True)
    participant.add_argument("--local-identity", required=True)
    participant.add_argument("--remote-identity", required=True)
    participant.add_argument("--max-spoken-turns", type=int, required=True)
    participant.add_argument("--max-duration-s", type=float, required=True)
    participant.add_argument("--opening-instructions")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "participant":  # pyright: ignore[reportAny]
        raise AssertionError("unhandled LiveKit Agents lab command")
    try:
        result = asyncio.run(
            run_participant(
                role=cast(str, args.role),
                data_dir=cast(Path, args.data_dir),
                alias_id=cast(str, args.alias_id),
                remote_alias_id=cast(str, args.remote_alias_id),
                remote_display_name=cast(str, args.remote_display_name),
                room_name=cast(str, args.room),
                local_identity=cast(str, args.local_identity),
                remote_identity=cast(str, args.remote_identity),
                max_spoken_turns=cast(int, args.max_spoken_turns),
                max_duration_s=cast(float, args.max_duration_s),
                opening_instructions=cast(str | None, args.opening_instructions),
            )
        )
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        print(f"simo LiveKit Agents participant: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
