"""Construction of one audio-only LiveKit Agents session for a Simo alias."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from livekit.agents import llm, vad
from livekit.agents.voice import Agent, AgentSession, room_io
from livekit.agents.voice.turn import TurnHandlingOptions
from livekit.plugins import silero

from simo.adapters.livekit.providers import (
    InferenceEventSink,
    LocalLLM,
    LocalSTT,
    LocalTTS,
)
from simo.config import RuntimeConfig
from simo.inference import SpeechRecognizer, SpeechSynthesizer, TextGenerator
from simo.semantic_context import SemanticContextSnapshot, format_semantic_context


class ContextSnapshotSource(Protocol):
    def snapshot(self) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class SileroVADSettings:
    min_speech_duration: float
    min_silence_duration: float
    prefix_padding_duration: float
    max_buffered_speech: float
    activation_threshold: float

    @classmethod
    def from_runtime(cls, config: RuntimeConfig) -> SileroVADSettings:
        return cls(
            min_speech_duration=config.vad_start_ms / 1_000,
            min_silence_duration=config.vad_stop_ms / 1_000,
            prefix_padding_duration=config.vad_pre_roll_ms / 1_000,
            max_buffered_speech=config.max_utterance_s,
            activation_threshold=config.vad_confidence,
        )

    def load(self) -> vad.VAD:
        """Load the bundled ONNX Silero model with the frozen session settings."""

        return silero.VAD.load(
            min_speech_duration=self.min_speech_duration,
            min_silence_duration=self.min_silence_duration,
            prefix_padding_duration=self.prefix_padding_duration,
            max_buffered_speech=self.max_buffered_speech,
            activation_threshold=self.activation_threshold,
            sample_rate=16_000,
            force_cpu=True,
        )


@dataclass(frozen=True, slots=True)
class LiveKitAgentSessionComponents:
    agent: Agent
    session: AgentSession[object]
    stt: LocalSTT
    llm: LocalLLM
    tts: LocalTTS
    vad: vad.VAD
    vad_settings: SileroVADSettings
    turn_handling: TurnHandlingOptions
    room_options: room_io.RoomOptions


def build_livekit_agent_session(
    config: RuntimeConfig,
    engine: ContextSnapshotSource,
    *,
    persona_instructions: str,
    remote_transport_identity: str,
    recognizer: SpeechRecognizer,
    generator: TextGenerator,
    synthesizer: SpeechSynthesizer,
    event_sink: InferenceEventSink,
    chat_context: llm.ChatContext | None = None,
    loaded_vad: vad.VAD | None = None,
) -> LiveKitAgentSessionComponents:
    """Freeze models, persona, turn mechanics, and RoomIO scope for one session."""

    if not persona_instructions.strip():
        raise ValueError("persona instructions must not be empty")
    if not remote_transport_identity.strip():
        raise ValueError("remote transport identity must not be empty")

    def semantic_context() -> str:
        raw = engine.snapshot()
        snapshot = SemanticContextSnapshot.from_native(raw)
        snapshot.require_fresh(config.context_max_age_ms)
        return format_semantic_context(snapshot, max_chars=config.context_max_chars)

    local_stt = LocalSTT(
        recognizer,
        model=config.stt.model_id,
    )
    local_llm = LocalLLM(
        generator,
        max_tokens=config.text_max_tokens,
        model=config.text.model_id,
        context_provider=semantic_context,
        event_sink=event_sink,
    )
    local_tts = LocalTTS(
        synthesizer,
        sample_rate=24_000,
        model=config.tts.model_id,
        event_sink=event_sink,
    )
    vad_settings = SileroVADSettings.from_runtime(config)
    selected_vad = loaded_vad or vad_settings.load()
    turn_handling = TurnHandlingOptions(
        turn_detection="vad",
        endpointing={
            "mode": "fixed",
            "min_delay": 0.05,
            "max_delay": 0.6,
        },
        interruption={
            "enabled": True,
            "mode": "vad",
            "min_duration": config.vad_start_ms / 1_000,
            "min_words": 0,
            "resume_false_interruption": True,
            "false_interruption_timeout": 1.0,
        },
        preemptive_generation={"enabled": False},
    )
    session = AgentSession[object](
        stt=local_stt,
        vad=selected_vad,
        llm=local_llm,
        tts=local_tts,
        turn_handling=turn_handling,
        use_tts_aligned_transcript=True,
        aec_warmup_duration=None,
        user_away_timeout=None,
    )
    agent = Agent(
        instructions=persona_instructions,
        chat_ctx=chat_context or llm.ChatContext.empty(),
    )
    options = room_io.RoomOptions(
        text_input=False,
        audio_input=room_io.AudioInputOptions(
            sample_rate=16_000,
            num_channels=1,
            frame_size_ms=20,
            auto_gain_control=False,
            pre_connect_audio=True,
        ),
        video_input=False,
        audio_output=room_io.AudioOutputOptions(
            sample_rate=24_000,
            num_channels=1,
        ),
        text_output=False,
        participant_identity=remote_transport_identity,
        close_on_disconnect=True,
        delete_room_on_close=False,
    )
    return LiveKitAgentSessionComponents(
        agent,
        session,
        local_stt,
        local_llm,
        local_tts,
        selected_vad,
        vad_settings,
        turn_handling,
        options,
    )
