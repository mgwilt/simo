"""Interactive one-human, one-alias conversation through a local LiveKit room."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import cast
from uuid import uuid4

from livekit import rtc

from simo.config import RuntimeConfig
from simo.livekit_local_server import start_local_livekit_server
from simo.livekit_room import LiveKitRoomConfig
from simo.livekit_runtime import (
    LiveKitAliasRunRequest,
    LiveKitAliasRunResult,
    LiveKitAliasRuntime,
)
from simo.persistence import SimoStore


@dataclass(frozen=True, slots=True)
class LocalTalkDevices:
    microphone: str
    speaker: str


@dataclass(frozen=True, slots=True)
class LocalTalkResult:
    server_version: str
    room_name: str
    human_participant_sid: str
    devices: LocalTalkDevices
    run: LiveKitAliasRunResult

    def as_dict(self) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(self))
        payload["run"] = self.run.as_dict()
        return payload


class PlatformAudioParticipant:
    """Publish and play room audio through LiveKit's native WebRTC device module."""

    def __init__(
        self,
        config: LiveKitRoomConfig,
        *,
        input_device_index: int | None,
        output_device_index: int | None,
    ) -> None:
        self._config = config
        self._input_device_index = input_device_index
        self._output_device_index = output_device_index
        self._room = rtc.Room()
        self._platform_audio: rtc.PlatformAudio | None = None
        self._source: rtc.PlatformAudioSource | None = None
        self._publication: rtc.LocalTrackPublication | None = None
        self._devices: LocalTalkDevices | None = None
        self._participant_sid = ""
        self._room.on("track_published")(  # pyright: ignore[reportUnknownMemberType]
            self._on_track_published
        )

    @property
    def participant_sid(self) -> str:
        if not self._participant_sid:
            raise RuntimeError("platform audio participant has no LiveKit SID")
        return self._participant_sid

    @property
    def devices(self) -> LocalTalkDevices:
        if self._devices is None:
            raise RuntimeError("platform audio participant is not connected")
        return self._devices

    async def connect(self) -> None:
        if self._platform_audio is not None:
            raise RuntimeError("platform audio participant is already connected")
        platform = rtc.PlatformAudio()
        try:
            microphone = _select_device(
                platform.recording_devices(),
                self._input_device_index,
                "recording",
            )
            speaker = _select_device(
                platform.playout_devices(),
                self._output_device_index,
                "playout",
            )
            if self._input_device_index is not None:
                platform.set_recording_device(microphone.id)
            if self._output_device_index is not None:
                platform.set_playout_device(speaker.id)
            source = platform.create_audio_source(
                rtc.PlatformAudioOptions(
                    echo_cancellation=True,
                    noise_suppression=True,
                    auto_gain_control=True,
                )
            )
            await self._room.connect(
                self._config.server_url,
                self._config.issue_join_token(),
                options=rtc.RoomOptions(auto_subscribe=False),
            )
            track = rtc.LocalAudioTrack.create_audio_track("simo-human-microphone", source)
            options = rtc.TrackPublishOptions()
            options.source = rtc.TrackSource.SOURCE_MICROPHONE
            self._publication = await self._room.local_participant.publish_track(track, options)
            self._participant_sid = self._room.local_participant.sid
            self._platform_audio = platform
            self._source = source
            self._devices = LocalTalkDevices(microphone.name, speaker.name)
            self._subscribe_existing_audio()
        except BaseException:
            if self._room.isconnected():
                await self._room.disconnect()
            platform.close()
            raise

    async def aclose(self) -> None:
        if self._room.isconnected():
            await self._room.disconnect()
        if self._source is not None:
            self._source.close()
        if self._platform_audio is not None:
            self._platform_audio.close()
        self._publication = None
        self._source = None
        self._platform_audio = None

    def _subscribe_existing_audio(self) -> None:
        for participant in self._room.remote_participants.values():
            for publication in participant.track_publications.values():
                self._select_publication(publication, participant)

    def _on_track_published(
        self,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        self._select_publication(publication, participant)

    def _select_publication(
        self,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        publication.set_subscribed(
            self._config.allows_remote_audio(
                participant.identity,
                audio=publication.kind == rtc.TrackKind.KIND_AUDIO,
            )
        )


async def run_local_talk(
    store: SimoStore,
    config: RuntimeConfig,
    *,
    alias_id: str,
    conversation_id: str | None = None,
    human_name: str = "Local user",
    server_binary: str | None = None,
    max_duration_s: float | None = None,
    ready: Callable[[LocalTalkDevices], None] | None = None,
) -> LocalTalkResult:
    """Run an interruptible local headset conversation over WebRTC."""

    if not human_name.strip():
        raise ValueError("human name must not be empty")
    if max_duration_s is not None and max_duration_s <= 0:
        raise ValueError("talk duration must be positive")
    alias = store.get_alias(alias_id)
    server = await start_local_livekit_server(server_binary)
    run_id = uuid4().hex[:12]
    room_name = f"simo-talk-{run_id}"
    bot_identity = f"alias-{alias.alias_id}"
    human_identity = f"human-local-{run_id}"
    bot_room = LiveKitRoomConfig(
        server.server_url,
        server.api_key,
        server.api_secret,
        room_name,
        bot_identity,
        alias.display_name,
        frozenset({human_identity}),
    )
    human_room = LiveKitRoomConfig(
        server.server_url,
        server.api_key,
        server.api_secret,
        room_name,
        human_identity,
        human_name,
        frozenset({bot_identity}),
    )
    participant = PlatformAudioParticipant(
        human_room,
        input_device_index=config.audio_input_device_index,
        output_device_index=config.audio_output_device_index,
    )
    runtime = LiveKitAliasRuntime(store, config, bot_room)
    request = LiveKitAliasRunRequest(
        alias.alias_id,
        "human:local",
        human_name,
        human_identity,
        conversation_id=conversation_id,
        max_duration_s=max_duration_s,
        complete_on_close=False,
    )
    bot_task = asyncio.create_task(runtime.run(request), name="simo-livekit-local-alias")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed_signals: list[signal.Signals] = []
    for selected_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(selected_signal, stop.set)
            installed_signals.append(selected_signal)
        except NotImplementedError:
            pass
    stop_task: asyncio.Task[bool] | None = None
    try:
        await participant.connect()
        if ready is not None:
            ready(participant.devices)
        stop_task = asyncio.create_task(_wait_for_stop(stop, max_duration_s))
        done, _ = await asyncio.wait(
            {bot_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if bot_task in done:
            result = await bot_task
        else:
            await participant.aclose()
            result = await asyncio.wait_for(bot_task, timeout=15.0)
    finally:
        for selected_signal in installed_signals:
            loop.remove_signal_handler(selected_signal)
        if stop_task is not None and not stop_task.done():
            stop_task.cancel()
            await asyncio.gather(stop_task, return_exceptions=True)
        await participant.aclose()
        if not bot_task.done():
            bot_task.cancel()
            await asyncio.gather(bot_task, return_exceptions=True)
        await server.aclose()
    return LocalTalkResult(
        server.version,
        room_name,
        participant.participant_sid,
        participant.devices,
        result,
    )


async def _wait_for_stop(stop: asyncio.Event, max_duration_s: float | None) -> bool:
    if max_duration_s is None:
        await stop.wait()
        return True
    try:
        await asyncio.wait_for(stop.wait(), timeout=max_duration_s)
    except TimeoutError:
        return False
    return True


def _select_device(
    devices: list[rtc.AudioDeviceInfo],
    configured_index: int | None,
    kind: str,
) -> rtc.AudioDeviceInfo:
    if not devices:
        raise RuntimeError(f"LiveKit reported no {kind} audio devices")
    if configured_index is None:
        return devices[0]
    try:
        return next(device for device in devices if device.index == configured_index)
    except StopIteration as error:
        available = ", ".join(f"{device.index}:{device.name}" for device in devices)
        raise ValueError(
            f"LiveKit {kind} device index {configured_index} is unavailable; available: {available}"
        ) from error
