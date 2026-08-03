"""Two-process synthetic-audio proof for Simo's LiveKit media boundary."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from array import array
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from math import pi, sin
from pathlib import Path
from time import monotonic
from typing import Final, cast
from uuid import uuid4

os.environ.setdefault("LOGURU_AUTOINIT", "False")

from pipecat.frames.frames import EndFrame, Frame, TTSAudioRawFrame, UserAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.workers.runner import WorkerRunner

from simo.adapters.pipecat.livekit_audio import SimoLiveKitTransport
from simo.livekit_room import LiveKitRoomConfig

_SERVER_HOST: Final = "127.0.0.1"
_SERVER_PORT: Final = 17_880
_SERVER_UDP_PORT: Final = 17_882
_SERVER_URL: Final = f"ws://{_SERVER_HOST}:{_SERVER_PORT}"
_DEV_API_KEY: Final = "devkey"
_DEV_API_SECRET: Final = "secret"
_INPUT_SAMPLE_RATE: Final = 16_000
_OUTPUT_SAMPLE_RATE: Final = 24_000
_PROBE_DURATION_S: Final = 0.9
_MIN_RECEIVED_S: Final = 0.45


@dataclass(frozen=True, slots=True)
class WebRTCParticipantProbe:
    role: str
    process_id: int
    local_identity: str
    local_participant_sid: str
    remote_identity: str
    remote_participant_sids: tuple[str, ...]
    received_frames: int
    received_samples: int
    received_peak: int
    self_echo_frames: int
    unexpected_identity_frames: int
    published_samples: int
    elapsed_ms: int

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class TwoProcessWebRTCProbe:
    server_version: str
    room_name: str
    participants: tuple[WebRTCParticipantProbe, WebRTCParticipantProbe]
    processes_distinct: bool
    participant_sids_distinct: bool
    self_echo_frames: int
    unexpected_identity_frames: int
    raw_audio_retained: bool

    def as_dict(self) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(self))
        payload["participants"] = [participant.as_dict() for participant in self.participants]
        return payload


class _RemoteAudioProbe(FrameProcessor):
    def __init__(
        self,
        expected_identity: str,
        local_sid: Callable[[], str | None],
    ) -> None:
        super().__init__(  # pyright: ignore[reportUnknownMemberType]
            enable_direct_mode=True
        )
        self._expected_identity = expected_identity
        self._local_sid = local_sid
        self.received_frames = 0
        self.received_samples = 0
        self.received_peak = 0
        self.self_echo_frames = 0
        self.unexpected_identity_frames = 0
        self.remote_sids: set[str] = set()
        self.signal_received = asyncio.Event()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(frame, UserAudioRawFrame):
            local_sid = self._local_sid()
            if local_sid is not None and frame.user_id == local_sid:
                self.self_echo_frames += 1
            if frame.transport_source != self._expected_identity:
                self.unexpected_identity_frames += 1
            else:
                values = array("h")
                values.frombytes(frame.audio)
                peak = max((abs(value) for value in values), default=0)
                self.received_frames += 1
                self.received_samples += frame.num_frames
                self.received_peak = max(self.received_peak, peak)
                self.remote_sids.add(frame.user_id)
                if (
                    self.received_samples >= round(_MIN_RECEIVED_S * frame.sample_rate)
                    and self.received_peak >= 256
                ):
                    self.signal_received.set()
        await self.push_frame(frame, direction)


def _synthetic_speech_shaped_pcm(*, marker: int) -> bytes:
    """Generate bounded voiced PCM with syllabic envelopes and no retained fixture."""

    sample_count = round(_PROBE_DURATION_S * _OUTPUT_SAMPLE_RATE)
    samples = array("h")
    base_frequency = 170 + marker * 37
    for index in range(sample_count):
        time_s = index / _OUTPUT_SAMPLE_RATE
        syllable_phase = (time_s * 4.5) % 1.0
        envelope = sin(pi * min(1.0, syllable_phase * 1.35)) ** 2
        if syllable_phase > 0.74:
            envelope = 0.0
        formant = 510 + marker * 83 + 75 * sin(2 * pi * 2.0 * time_s)
        signal = envelope * (
            5_200 * sin(2 * pi * base_frequency * time_s)
            + 2_800 * sin(2 * pi * formant * time_s)
            + 1_300 * sin(2 * pi * (formant * 1.7) * time_s)
        )
        samples.append(round(max(-32_768, min(32_767, signal))))
    return samples.tobytes()


async def run_participant_probe(
    *,
    role: str,
    room_name: str,
    local_identity: str,
    remote_identity: str,
    timeout_s: float = 20.0,
) -> WebRTCParticipantProbe:
    if role not in {"initiator", "responder"}:
        raise ValueError("WebRTC probe role must be initiator or responder")
    started = monotonic()
    config = LiveKitRoomConfig.from_environment(
        room_name=room_name,
        participant_identity=local_identity,
        participant_name=f"Simo probe {role}",
        allowed_remote_identities=frozenset({remote_identity}),
    )
    transport = SimoLiveKitTransport(config)
    probe = _RemoteAudioProbe(remote_identity, lambda: transport.local_participant_sid)
    pipeline = Pipeline([transport.input(), probe, transport.output()])
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=_INPUT_SAMPLE_RATE,
            audio_out_sample_rate=_OUTPUT_SAMPLE_RATE,
        ),
        enable_rtvi=False,
        enable_turn_tracking=False,
        idle_timeout_secs=None,
        name=f"probe-{role}",
    )
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)

    async def exchange() -> None:
        await asyncio.wait_for(transport.connected.wait(), timeout=timeout_s)
        await asyncio.wait_for(transport.remote_audio_ready.wait(), timeout=timeout_s)
        if role == "responder":
            await asyncio.wait_for(probe.signal_received.wait(), timeout=timeout_s)
        audio = _synthetic_speech_shaped_pcm(marker=1 if role == "initiator" else 2)
        await worker.queue_frame(
            TTSAudioRawFrame(
                audio=audio,
                sample_rate=_OUTPUT_SAMPLE_RATE,
                num_channels=1,
                context_id=f"probe-{role}",
            )
        )
        if not await worker.flush_pipeline(timeout=timeout_s):
            raise RuntimeError("synthetic WebRTC output did not drain")
        if role == "initiator":
            await asyncio.wait_for(probe.signal_received.wait(), timeout=timeout_s)
        else:
            await asyncio.sleep(_PROBE_DURATION_S + 0.35)
        await worker.queue_frame(EndFrame())

    exchange_task = asyncio.create_task(exchange(), name=f"probe-exchange-{role}")
    try:
        async with asyncio.timeout(timeout_s + 5.0):
            await runner.run()
        await exchange_task
    finally:
        if not exchange_task.done():
            exchange_task.cancel()
            await asyncio.gather(exchange_task, return_exceptions=True)

    local_sid = transport.local_participant_sid
    if local_sid is None:
        raise RuntimeError("LiveKit participant SID was unavailable after the probe")
    if probe.received_peak < 256 or not probe.remote_sids:
        raise RuntimeError("no attributed remote WebRTC signal was observed")
    return WebRTCParticipantProbe(
        role,
        os.getpid(),
        local_identity,
        local_sid,
        remote_identity,
        tuple(sorted(probe.remote_sids)),
        probe.received_frames,
        probe.received_samples,
        probe.received_peak,
        probe.self_echo_frames,
        probe.unexpected_identity_frames,
        len(_synthetic_speech_shaped_pcm(marker=1 if role == "initiator" else 2)) // 2,
        round((monotonic() - started) * 1_000),
    )


async def run_two_process_probe(
    *,
    server_binary: str | None = None,
    timeout_s: float = 30.0,
) -> TwoProcessWebRTCProbe:
    binary = server_binary or shutil.which("livekit-server")
    if binary is None:
        raise RuntimeError("livekit-server is required; install the Homebrew livekit formula")
    server_version = _server_version(binary)
    room_name = f"simo-probe-{uuid4().hex[:12]}"
    identities = (f"simo-a-{uuid4().hex[:8]}", f"simo-b-{uuid4().hex[:8]}")
    server = await asyncio.create_subprocess_exec(
        binary,
        "--dev",
        "--bind",
        _SERVER_HOST,
        "--node-ip",
        _SERVER_HOST,
        "--udp-port",
        str(_SERVER_UDP_PORT),
        "--config-body",
        f"port: {_SERVER_PORT}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await _wait_for_server(timeout_s=5.0)
        environment = os.environ.copy()
        environment.update(
            {
                "SIMO_LIVEKIT_URL": _SERVER_URL,
                "SIMO_LIVEKIT_API_KEY": _DEV_API_KEY,
                "SIMO_LIVEKIT_API_SECRET": _DEV_API_SECRET,
                "LOGURU_AUTOINIT": "False",
            }
        )
        responder = await _spawn_participant(
            "responder", room_name, identities[1], identities[0], environment
        )
        initiator = await _spawn_participant(
            "initiator", room_name, identities[0], identities[1], environment
        )
        outputs = await asyncio.wait_for(
            asyncio.gather(
                _collect_participant(initiator, "initiator"),
                _collect_participant(responder, "responder"),
            ),
            timeout=timeout_s,
        )
    finally:
        if server.returncode is None:
            server.terminate()
            try:
                await asyncio.wait_for(server.wait(), timeout=5.0)
            except TimeoutError:
                server.kill()
                await server.wait()
    participants = tuple(sorted(outputs, key=lambda item: item.role))
    if len(participants) != 2:
        raise RuntimeError("two participant results were not collected")
    first, second = participants
    result = TwoProcessWebRTCProbe(
        server_version,
        room_name,
        (first, second),
        first.process_id != second.process_id,
        first.local_participant_sid != second.local_participant_sid,
        first.self_echo_frames + second.self_echo_frames,
        first.unexpected_identity_frames + second.unexpected_identity_frames,
        False,
    )
    if not result.processes_distinct or not result.participant_sids_distinct:
        raise RuntimeError("WebRTC proof did not use two independent participants")
    if result.self_echo_frames or result.unexpected_identity_frames:
        raise RuntimeError("WebRTC proof violated identity isolation")
    return result


async def _spawn_participant(
    role: str,
    room_name: str,
    local_identity: str,
    remote_identity: str,
    environment: dict[str, str],
) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "simo.livekit_probe",
        "participant",
        "--role",
        role,
        "--room",
        room_name,
        "--local-identity",
        local_identity,
        "--remote-identity",
        remote_identity,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
        cwd=Path(__file__).resolve().parents[2],
    )


async def _collect_participant(
    process: asyncio.subprocess.Process,
    role: str,
) -> WebRTCParticipantProbe:
    stdout, _stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"{role} WebRTC participant exited with status {process.returncode}")
    try:
        value = cast(object, json.loads(stdout.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{role} WebRTC participant returned invalid JSON") from error
    if not isinstance(value, dict):
        raise TypeError(f"{role} WebRTC participant result must be an object")
    payload = cast(dict[str, object], value)
    return WebRTCParticipantProbe(
        role=_required_str(payload, "role"),
        process_id=_required_int(payload, "process_id"),
        local_identity=_required_str(payload, "local_identity"),
        local_participant_sid=_required_str(payload, "local_participant_sid"),
        remote_identity=_required_str(payload, "remote_identity"),
        remote_participant_sids=tuple(_required_str_list(payload, "remote_participant_sids")),
        received_frames=_required_int(payload, "received_frames"),
        received_samples=_required_int(payload, "received_samples"),
        received_peak=_required_int(payload, "received_peak"),
        self_echo_frames=_required_int(payload, "self_echo_frames"),
        unexpected_identity_frames=_required_int(payload, "unexpected_identity_frames"),
        published_samples=_required_int(payload, "published_samples"),
        elapsed_ms=_required_int(payload, "elapsed_ms"),
    )


async def _wait_for_server(*, timeout_s: float) -> None:
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        try:
            reader, writer = await asyncio.open_connection(_SERVER_HOST, _SERVER_PORT)
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


def _required_str_list(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise TypeError(f"participant result {key} must be a string list")
    entries = cast(list[object], value)
    if any(not isinstance(item, str) for item in entries):
        raise TypeError(f"participant result {key} must be a string list")
    return [cast(str, item) for item in entries]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simo.livekit_probe")
    subcommands = parser.add_subparsers(dest="command", required=True)
    participant = subcommands.add_parser("participant")
    participant.add_argument("--role", choices=("initiator", "responder"), required=True)
    participant.add_argument("--room", required=True)
    participant.add_argument("--local-identity", required=True)
    participant.add_argument("--remote-identity", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "participant":  # pyright: ignore[reportAny]
        raise AssertionError("unhandled LiveKit probe command")
    try:
        result = asyncio.run(
            run_participant_probe(
                role=cast(str, args.role),
                room_name=cast(str, args.room),
                local_identity=cast(str, args.local_identity),
                remote_identity=cast(str, args.remote_identity),
            )
        )
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        print(f"simo livekit participant: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
