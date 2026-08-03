from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import llm, stt
from simo.adapters.livekit import LocalLLM, LocalSTT, LocalTTS
from simo.inference import AudioChunk


class FakeRecognizer:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, int]] = []

    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str:
        self.calls.append((pcm_s16le, sample_rate))
        return " recognized locally "


class FakeGenerator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def generate(self, prompt: str, *, max_tokens: int) -> str:
        self.calls.append((prompt, max_tokens))
        return "local reply"


class FakeSynthesizer:
    def __init__(self, *, sample_rate: int = 24_000) -> None:
        self.sample_rate = sample_rate
        self.texts: list[str] = []

    async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
        self.texts.append(text)
        yield AudioChunk(b"\x01\x00" * 240, self.sample_rate)
        yield AudioChunk(b"\x02\x00" * 240, self.sample_rate)


class LiveKitProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_returns_final_attributed_local_transcript(self) -> None:
        recognizer = FakeRecognizer()
        provider = LocalSTT(recognizer)
        frame = rtc.AudioFrame(
            data=b"\x01\x00" * 320,
            sample_rate=16_000,
            num_channels=1,
            samples_per_channel=320,
        )

        event = await provider.recognize(frame)

        self.assertEqual(stt.SpeechEventType.FINAL_TRANSCRIPT, event.type)
        self.assertEqual("recognized locally", event.alternatives[0].text)
        self.assertEqual("en", event.alternatives[0].language)
        self.assertEqual([(frame.data.tobytes(), 16_000)], recognizer.calls)
        self.assertEqual("simo-local", provider.provider)

    async def test_llm_injects_one_semantic_snapshot_into_chat_prompt(self) -> None:
        generator = FakeGenerator()
        provider = LocalLLM(
            generator,
            max_tokens=48,
            context_provider=lambda: "Flecs snapshot revision 7",
        )
        chat_ctx = llm.ChatContext.empty()
        chat_ctx.add_message(role="system", content="Be concise")
        chat_ctx.add_message(role="user", content="What do you remember?")

        response = await provider.chat(chat_ctx=chat_ctx).collect()

        self.assertEqual("local reply", response.text)
        self.assertEqual(1, len(generator.calls))
        prompt, max_tokens = generator.calls[0]
        self.assertEqual(1, prompt.count("Flecs snapshot revision 7"))
        self.assertIn("system: Be concise", prompt)
        self.assertIn("user: What do you remember?", prompt)
        self.assertEqual(48, max_tokens)

    async def test_tts_yields_livekit_audio_without_retaining_raw_audio(self) -> None:
        synthesizer = FakeSynthesizer()
        provider = LocalTTS(synthesizer)

        stream = provider.synthesize("Speak this")
        frames = [event.frame async for event in stream]

        self.assertEqual(["Speak this"], synthesizer.texts)
        self.assertGreaterEqual(sum(frame.samples_per_channel for frame in frames), 480)
        self.assertTrue(all(frame.sample_rate == 24_000 for frame in frames))
        self.assertTrue(all(frame.num_channels == 1 for frame in frames))

    async def test_tts_rejects_provider_sample_rate_drift(self) -> None:
        provider = LocalTTS(FakeSynthesizer(sample_rate=16_000))

        with self.assertRaisesRegex(ValueError, "expected 24000"):
            _ = [event async for event in provider.synthesize("wrong rate")]


if __name__ == "__main__":
    unittest.main()
