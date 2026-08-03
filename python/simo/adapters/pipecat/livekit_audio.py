"""Audio-only LiveKit transport for isolated Simo participants."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from livekit import rtc
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    OutputAudioRawFrame,
    StartFrame,
    UserAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport
from pipecat.transports.base_transport import BaseTransport, TransportParams

from simo.livekit_room import LiveKitRoomConfig


@dataclass(frozen=True, slots=True)
class RemoteAudioSubscription:
    participant_sid: str
    participant_identity: str
    track_sid: str


@dataclass(frozen=True, slots=True)
class _InboundAudio:
    participant_sid: str
    participant_identity: str
    audio: bytes
    sample_rate: int
    num_channels: int


class _LiveKitAudioSession:
    """Share one SDK room connection between Pipecat input and output."""

    def __init__(
        self,
        config: LiveKitRoomConfig,
        *,
        input_sample_rate: int,
        output_sample_rate: int,
        channels: int,
    ) -> None:
        self._config = config
        self._input_sample_rate = input_sample_rate
        self._output_sample_rate = output_sample_rate
        self._channels = channels
        self._room = rtc.Room()
        self._room.on("track_published")(  # pyright: ignore[reportUnknownMemberType]
            self._on_track_published
        )
        self._room.on("track_subscribed")(  # pyright: ignore[reportUnknownMemberType]
            self._on_track_subscribed
        )
        self._room.on("track_unsubscribed")(  # pyright: ignore[reportUnknownMemberType]
            self._on_track_unsubscribed
        )
        self._room.on("participant_disconnected")(  # pyright: ignore[reportUnknownMemberType]
            self._on_participant_disconnected
        )
        self._audio_source: rtc.AudioSource | None = None
        self._audio_track: rtc.LocalAudioTrack | None = None
        self._inbound: asyncio.Queue[_InboundAudio] = asyncio.Queue(maxsize=256)
        self._streams: dict[str, tuple[rtc.AudioStream, asyncio.Task[None]]] = {}
        self._cleanup_tasks: set[asyncio.Task[None]] = set()
        self._subscriptions: dict[str, RemoteAudioSubscription] = {}
        self._connected = False
        self._last_local_participant_sid: str | None = None
        self._owners = 0
        self._lock = asyncio.Lock()
        self.connected = asyncio.Event()
        self.remote_audio_ready = asyncio.Event()

    @property
    def local_participant_sid(self) -> str | None:
        return self._last_local_participant_sid

    @property
    def subscriptions(self) -> tuple[RemoteAudioSubscription, ...]:
        return tuple(sorted(self._subscriptions.values(), key=lambda item: item.participant_sid))

    async def acquire(self) -> None:
        async with self._lock:
            self._owners += 1
            if self._connected:
                return
            try:
                await self._room.connect(
                    self._config.server_url,
                    self._config.issue_join_token(),
                    options=rtc.RoomOptions(auto_subscribe=False),
                )
                self._audio_source = rtc.AudioSource(
                    self._output_sample_rate,
                    self._channels,
                    queue_size_ms=250,
                )
                self._audio_track = rtc.LocalAudioTrack.create_audio_track(
                    "simo-speech",
                    self._audio_source,
                )
                options = rtc.TrackPublishOptions()
                options.source = rtc.TrackSource.SOURCE_MICROPHONE
                await self._room.local_participant.publish_track(self._audio_track, options)
                self._connected = True
                self._last_local_participant_sid = self._room.local_participant.sid
                self.connected.set()
                self._subscribe_existing_audio()
            except BaseException:
                self._owners -= 1
                raise

    async def release(self) -> None:
        async with self._lock:
            if self._owners == 0:
                return
            self._owners -= 1
            if self._owners > 0 or not self._connected:
                return
            self._connected = False
            self.connected.clear()
            await self._close_all_streams()
            await self._room.disconnect()
            self._audio_source = None
            self._audio_track = None
            self._subscriptions.clear()
            self.remote_audio_ready.clear()

    async def publish(self, frame: OutputAudioRawFrame) -> bool:
        source = self._audio_source
        if not self._connected or source is None:
            return False
        if frame.sample_rate != self._output_sample_rate or frame.num_channels != self._channels:
            raise ValueError("LiveKit output PCM does not match the configured media format")
        await source.capture_frame(
            rtc.AudioFrame(
                data=frame.audio,
                sample_rate=frame.sample_rate,
                num_channels=frame.num_channels,
                samples_per_channel=frame.num_frames,
            )
        )
        return True

    def interrupt_output(self) -> None:
        if self._audio_source is not None:
            self._audio_source.clear_queue()

    async def receive(self) -> _InboundAudio:
        return await self._inbound.get()

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
        audio = publication.kind == rtc.TrackKind.KIND_AUDIO
        publication.set_subscribed(
            self._config.allows_remote_audio(participant.identity, audio=audio)
        )

    def _on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if not self._config.allows_remote_audio(
            participant.identity,
            audio=track.kind == rtc.TrackKind.KIND_AUDIO,
        ):
            publication.set_subscribed(False)
            return
        previous = self._streams.get(participant.sid)
        if previous is not None:
            self._streams.pop(participant.sid)
            self._subscriptions.pop(participant.sid, None)
            self._schedule_entry_close(previous)
        stream = rtc.AudioStream(
            track,
            sample_rate=self._input_sample_rate,
            num_channels=self._channels,
            frame_size_ms=20,
        )
        task = asyncio.create_task(
            self._read_stream(stream, participant.sid, participant.identity),
            name=f"simo-livekit-audio-{participant.sid}",
        )
        self._streams[participant.sid] = (stream, task)
        self._subscriptions[participant.sid] = RemoteAudioSubscription(
            participant.sid,
            participant.identity,
            publication.sid,
        )
        self.remote_audio_ready.set()

    def _on_track_unsubscribed(
        self,
        _track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        self._schedule_stream_close(participant.sid, publication.sid)

    def _on_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        self._schedule_stream_close(participant.sid)

    def _schedule_stream_close(
        self,
        participant_sid: str,
        expected_track_sid: str | None = None,
    ) -> None:
        task = asyncio.create_task(
            self._close_stream(participant_sid, expected_track_sid),
            name=f"simo-livekit-close-{participant_sid}",
        )
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)

    def _schedule_entry_close(
        self,
        entry: tuple[rtc.AudioStream, asyncio.Task[None]],
    ) -> None:
        task = asyncio.create_task(self._close_entry(entry), name="simo-livekit-close-replaced")
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)

    async def _read_stream(
        self,
        stream: rtc.AudioStream,
        participant_sid: str,
        participant_identity: str,
    ) -> None:
        async for event in stream:
            frame = event.frame
            inbound = _InboundAudio(
                participant_sid,
                participant_identity,
                bytes(frame.data),
                frame.sample_rate,
                frame.num_channels,
            )
            if self._inbound.full():
                _ = self._inbound.get_nowait()
            self._inbound.put_nowait(inbound)

    async def _close_stream(
        self,
        participant_sid: str,
        expected_track_sid: str | None = None,
    ) -> None:
        subscription = self._subscriptions.get(participant_sid)
        if (
            expected_track_sid is not None
            and subscription is not None
            and subscription.track_sid != expected_track_sid
        ):
            return
        entry = self._streams.pop(participant_sid, None)
        self._subscriptions.pop(participant_sid, None)
        if not self._subscriptions:
            self.remote_audio_ready.clear()
        if entry is None:
            return
        await self._close_entry(entry)

    @staticmethod
    async def _close_entry(
        entry: tuple[rtc.AudioStream, asyncio.Task[None]],
    ) -> None:
        stream, task = entry
        if task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await stream.aclose()

    async def _close_all_streams(self) -> None:
        for participant_sid in tuple(self._streams):
            await self._close_stream(participant_sid)
        if self._cleanup_tasks:
            await asyncio.gather(*tuple(self._cleanup_tasks), return_exceptions=True)


class LiveKitAudioInputTransport(BaseInputTransport):
    def __init__(
        self,
        transport: SimoLiveKitTransport,
        session: _LiveKitAudioSession,
        params: TransportParams,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(params, name=name)  # pyright: ignore[reportUnknownMemberType]
        self._transport = transport
        self._session = session
        self._receive_task: asyncio.Task[None] | None = None
        self._acquired = False

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._acquired:
            return
        await self._session.acquire()
        self._acquired = True
        self._receive_task = self.create_task(  # pyright: ignore[reportUnknownMemberType]
            self._receive_audio()
        )
        await self.set_transport_ready(frame)

    async def stop(self, frame: EndFrame) -> None:
        await super().stop(frame)
        await self._teardown()

    async def cancel(self, frame: CancelFrame) -> None:
        await super().cancel(frame)
        await self._teardown()

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._teardown()

    async def _receive_audio(self) -> None:
        while True:
            inbound = await self._session.receive()
            frame = UserAudioRawFrame(
                user_id=inbound.participant_sid,
                audio=inbound.audio,
                sample_rate=inbound.sample_rate,
                num_channels=inbound.num_channels,
            )
            frame.transport_source = inbound.participant_identity
            await self.push_audio_frame(frame)

    async def _teardown(self) -> None:
        if self._receive_task is not None:
            await self.cancel_task(  # pyright: ignore[reportUnknownMemberType]
                self._receive_task
            )
            self._receive_task = None
        if self._acquired:
            self._acquired = False
            await self._session.release()


class LiveKitAudioOutputTransport(BaseOutputTransport):
    def __init__(
        self,
        transport: SimoLiveKitTransport,
        session: _LiveKitAudioSession,
        params: TransportParams,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(params, name=name)  # pyright: ignore[reportUnknownMemberType]
        self._transport = transport
        self._session = session
        self._acquired = False

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._acquired:
            return
        await self._session.acquire()
        self._acquired = True
        await self.set_transport_ready(frame)

    async def stop(self, frame: EndFrame) -> None:
        await super().stop(frame)
        await self._teardown()

    async def cancel(self, frame: CancelFrame) -> None:
        await super().cancel(frame)
        await self._teardown()

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._teardown()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, InterruptionFrame):
            self._session.interrupt_output()
        await super().process_frame(frame, direction)

    async def write_audio_frame(self, frame: OutputAudioRawFrame) -> bool:
        return await self._session.publish(frame)

    async def _teardown(self) -> None:
        if self._acquired:
            self._acquired = False
            await self._session.release()


class SimoLiveKitTransport(BaseTransport):
    """Pipecat media boundary that publishes and subscribes to audio only."""

    def __init__(
        self,
        config: LiveKitRoomConfig,
        *,
        input_sample_rate: int = 16_000,
        output_sample_rate: int = 24_000,
        channels: int = 1,
    ) -> None:
        if input_sample_rate <= 0 or output_sample_rate <= 0 or channels != 1:
            raise ValueError("LiveKit media formats require positive-rate mono PCM")
        super().__init__(name=f"livekit-{config.participant_identity}")
        self._params = TransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=input_sample_rate,
            audio_in_channels=channels,
            audio_out_enabled=True,
            audio_out_sample_rate=output_sample_rate,
            audio_out_channels=channels,
            audio_out_auto_silence=False,
            audio_out_end_silence_secs=0,
            video_in_enabled=False,
            video_out_enabled=False,
        )
        self._session = _LiveKitAudioSession(
            config,
            input_sample_rate=input_sample_rate,
            output_sample_rate=output_sample_rate,
            channels=channels,
        )
        self._input: LiveKitAudioInputTransport | None = None
        self._output: LiveKitAudioOutputTransport | None = None

    @property
    def local_participant_sid(self) -> str | None:
        return self._session.local_participant_sid

    @property
    def remote_audio_subscriptions(self) -> tuple[RemoteAudioSubscription, ...]:
        return self._session.subscriptions

    @property
    def connected(self) -> asyncio.Event:
        return self._session.connected

    @property
    def remote_audio_ready(self) -> asyncio.Event:
        return self._session.remote_audio_ready

    def input(self) -> LiveKitAudioInputTransport:
        if self._input is None:
            self._input = LiveKitAudioInputTransport(self, self._session, self._params)
        return self._input

    def output(self) -> LiveKitAudioOutputTransport:
        if self._output is None:
            self._output = LiveKitAudioOutputTransport(self, self._session, self._params)
        return self._output


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]
