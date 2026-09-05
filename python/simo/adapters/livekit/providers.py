"""Local model providers implementing the LiveKit Agents contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Protocol
from uuid import uuid4

from livekit import rtc
from livekit.agents import llm, stt, tts
from livekit.agents.language import LanguageCode
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.agents.voice.generation import update_instructions

from simo.inference import AudioChunk, SpeechRecognizer, SpeechSynthesizer, TextGenerator
from simo.live_controls import LiveConversationControls

SemanticContextProvider = Callable[[], str]


class InferenceEventSink(Protocol):
    """Non-blocking observation boundary for local inference lifecycle events."""

    def assistant_generated(self, text: str, request_id: str) -> None: ...

    def tts_submitted(self, text: str, request_id: str) -> None: ...


class LocalSTT(stt.STT[str]):
    """Expose Simo's batch local recognizer to LiveKit Agents."""

    def __init__(
        self,
        recognizer: SpeechRecognizer,
        *,
        sample_rate: int = 16_000,
        language: str = "en",
        model: str = "parakeet-mlx",
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("STT sample rate must be positive")
        if not language.strip() or not model.strip():
            raise ValueError("STT language and model must not be empty")
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,
                interim_results=False,
            )
        )
        self._recognizer = recognizer
        self._sample_rate = sample_rate
        self._language = LanguageCode(language)
        self._model_name = model

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "simo-local"

    async def _recognize_impl(
        self,
        buffer: list[rtc.AudioFrame] | rtc.AudioFrame,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        del conn_options
        frames: list[rtc.AudioFrame]
        if isinstance(buffer, rtc.AudioFrame):
            frames = [buffer]
        else:
            frames = buffer
        if not frames:
            raise ValueError("STT audio buffer must not be empty")
        if any(frame.num_channels != 1 for frame in frames):
            raise ValueError("Simo local STT requires mono audio")
        input_rate = frames[0].sample_rate
        if any(frame.sample_rate != input_rate for frame in frames):
            raise ValueError("STT audio frames must have one sample rate")
        selected = frames
        if input_rate != self._sample_rate:
            resampler = rtc.AudioResampler(
                input_rate=input_rate,
                output_rate=self._sample_rate,
                num_channels=1,
                quality=rtc.AudioResamplerQuality.HIGH,
            )
            selected = [output for frame in frames for output in resampler.push(frame)]
            selected.extend(resampler.flush())
        pcm = b"".join(frame.data.tobytes() for frame in selected)
        text = (await self._recognizer.transcribe(pcm, self._sample_rate)).strip()
        selected_language = LanguageCode(language) if isinstance(language, str) else self._language
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            request_id=f"simo-stt-{uuid4().hex}",
            alternatives=[
                stt.SpeechData(
                    language=selected_language,
                    text=text,
                    confidence=1.0,
                )
            ],
        )


class LocalLLM(llm.LLM[str]):
    """Expose Simo's local text generator as a LiveKit chat provider."""

    def __init__(
        self,
        generator: TextGenerator,
        *,
        max_tokens: int = 256,
        model: str = "mlx-lm",
        context_provider: SemanticContextProvider | None = None,
        event_sink: InferenceEventSink | None = None,
        live_controls: LiveConversationControls | None = None,
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("LLM max_tokens must be positive")
        if not model.strip():
            raise ValueError("LLM model must not be empty")
        super().__init__()
        self._generator = generator
        self._max_tokens = max_tokens
        self._model_name = model
        self._context_provider = context_provider
        self._event_sink = event_sink
        self._live_controls = live_controls

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "simo-local"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, object]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        del parallel_tool_calls, tool_choice, extra_kwargs
        return _LocalLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            generation=self._generation_snapshot(chat_ctx),
        )

    def _generation_snapshot(self, chat_ctx: llm.ChatContext) -> tuple[str, int]:
        if self._live_controls is None:
            return self._prompt(chat_ctx), self._max_tokens
        settings = self._live_controls.snapshot()
        # The editable prompt replaces the session's original system instructions;
        # never leave a stale brevity rule competing with the operator's revision.
        selected = chat_ctx.copy()
        # Use LiveKit's canonical instruction message, preserving separate
        # per-turn instructions such as opening greetings and turn-limit notices.
        update_instructions(selected, instructions=settings.instructions, add_if_missing=True)
        return self._prompt(selected), settings.max_tokens

    def _prompt(self, chat_ctx: llm.ChatContext) -> str:
        sections: list[str] = []
        if self._context_provider is not None:
            context = self._context_provider().strip()
            if context:
                sections.append(context)
        conversation = [
            f"{message.role}: {message.text_content}"
            for message in chat_ctx.messages()
            if message.text_content
        ]
        if conversation:
            sections.append("Conversation:\n" + "\n".join(conversation))
        if not sections:
            raise ValueError("LiveKit chat context must contain text")
        return "\n\n".join(sections)

    async def generate(self, chat_ctx: llm.ChatContext) -> str:
        """Generate one response from an immutable LiveKit chat snapshot."""

        prompt, budget = self._generation_snapshot(chat_ctx)
        return await self.generate_snapshot(prompt, budget)

    async def generate_snapshot(self, prompt: str, budget: int) -> str:
        return await self._generator.generate(prompt, max_tokens=budget)

    def observe_generated(self, text: str, request_id: str) -> None:
        if self._event_sink is not None:
            self._event_sink.assistant_generated(text, request_id)


class _LocalLLMStream(llm.LLMStream):
    def __init__(
        self,
        provider: LocalLLM,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
        generation: tuple[str, int],
    ) -> None:
        super().__init__(  # pyright: ignore[reportUnknownMemberType]
            provider,
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
        )
        self._provider: LocalLLM = provider
        self._generation: tuple[str, int] = generation

    async def _run(self) -> None:
        prompt, budget = self._generation
        response = await self._provider.generate_snapshot(prompt, budget)
        if response:
            request_id = f"simo-llm-{uuid4().hex}"
            self._provider.observe_generated(response, request_id)
            self._event_ch.send_nowait(
                llm.ChatChunk(
                    id=request_id,
                    delta=llm.ChoiceDelta(role="assistant", content=response),
                )
            )


class LocalTTS(tts.TTS[str]):
    """Expose Simo's streaming local synthesizer to LiveKit Agents."""

    def __init__(
        self,
        synthesizer: SpeechSynthesizer,
        *,
        sample_rate: int = 24_000,
        model: str = "qwen3-tts-mlx",
        event_sink: InferenceEventSink | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("TTS sample rate must be positive")
        if not model.strip():
            raise ValueError("TTS model must not be empty")
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._synthesizer = synthesizer
        self._model_name = model
        self._event_sink = event_sink

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "simo-local"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        return _LocalChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    def audio(self, text: str) -> AsyncIterator[AudioChunk]:
        """Yield model audio through Simo's provider-neutral contract."""

        return self._synthesizer.synthesize(text)

    def observe_submitted(self, text: str, request_id: str) -> None:
        if self._event_sink is not None:
            self._event_sink.tts_submitted(text, request_id)


class _LocalChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: LocalTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(  # pyright: ignore[reportUnknownMemberType]
            tts=tts,
            input_text=input_text,
            conn_options=conn_options,
        )
        self._provider = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = f"simo-tts-{uuid4().hex}"
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._provider.sample_rate,
            num_channels=self._provider.num_channels,
            mime_type="audio/pcm",
            stream=False,
        )
        self._provider.observe_submitted(self.input_text, request_id)
        async for chunk in self._provider.audio(self.input_text):
            if chunk.sample_rate != self._provider.sample_rate:
                raise ValueError(
                    f"local TTS produced {chunk.sample_rate} Hz; "
                    f"expected {self._provider.sample_rate} Hz"
                )
            if len(chunk.pcm_s16le) % 2:
                raise ValueError("local TTS produced misaligned 16-bit PCM")
            output_emitter.push(chunk.pcm_s16le)
        output_emitter.flush()
