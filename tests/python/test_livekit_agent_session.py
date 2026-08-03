from __future__ import annotations

import unittest
from collections.abc import AsyncIterator
from typing import cast

from livekit.agents import llm
from livekit.plugins import silero
from simo.adapters.livekit import SileroVADSettings, build_livekit_agent_session
from simo.config import RuntimeConfig
from simo.inference import AudioChunk


class FakeEngine:
    def snapshot(self) -> dict[str, object]:
        return {
            "revision": 4,
            "alias_id": "alias-a",
            "conversation_id": "conversation-a",
            "local_participant_id": "alias:alias-a",
            "participants": [
                {
                    "participant_id": "alias:alias-a",
                    "kind": "alias",
                    "alias_id": "alias-a",
                    "display_name": "Ada",
                    "transport_participant_id": "lk-ada",
                },
                {
                    "participant_id": "alias:alias-b",
                    "kind": "external",
                    "alias_id": "",
                    "display_name": "Bea",
                    "transport_participant_id": "lk-bea",
                },
            ],
            "memory_revision": 0,
            "memories": [],
            "items": [],
        }


class FakeRecognizer:
    async def transcribe(self, pcm_s16le: bytes, sample_rate: int) -> str:
        return "heard"


class FakeGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, max_tokens: int) -> str:
        self.prompts.append(prompt)
        return "reply"


class FakeSynthesizer:
    async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
        yield AudioChunk(b"\x00\x00" * 240, 24_000)


class FakeEvents:
    def assistant_generated(self, text: str, request_id: str) -> None:
        pass

    def tts_submitted(self, text: str, request_id: str) -> None:
        pass


class LiveKitAgentSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_audio_only_remote_scoped_session_with_frozen_context(self) -> None:
        config = RuntimeConfig.from_environment({})
        settings = SileroVADSettings.from_runtime(config)
        loaded_vad = silero.VAD.load(
            min_speech_duration=settings.min_speech_duration,
            min_silence_duration=settings.min_silence_duration,
            prefix_padding_duration=settings.prefix_padding_duration,
            max_buffered_speech=settings.max_buffered_speech,
            activation_threshold=settings.activation_threshold,
        )
        generator = FakeGenerator()
        history = llm.ChatContext.empty()
        history.add_message(role="user", content="Earlier turn")

        components = build_livekit_agent_session(
            config,
            FakeEngine(),
            persona_instructions="Be Ada: thoughtful and precise.",
            remote_transport_identity="lk-bea",
            recognizer=FakeRecognizer(),
            generator=generator,
            synthesizer=FakeSynthesizer(),
            event_sink=FakeEvents(),
            chat_context=history,
            loaded_vad=loaded_vad,
        )
        response = await components.llm.chat(chat_ctx=history).collect()

        self.assertEqual("reply", response.text)
        self.assertIn("Simo semantic context (revision 4)", generator.prompts[0])
        instructions = cast(str, components.agent.instructions)
        self.assertTrue(instructions.startswith("Be Ada: thoughtful and precise."))
        self.assertIn("no more than 35 words", instructions)
        self.assertIn("Always finish the current sentence", instructions)
        self.assertEqual("vad", components.turn_handling.get("turn_detection"))
        self.assertEqual(
            0.6,
            components.turn_handling.get("endpointing", {}).get("max_delay"),
        )
        self.assertEqual("lk-bea", components.room_options.participant_identity)
        self.assertFalse(components.room_options.text_input)
        self.assertFalse(components.room_options.text_output)
        self.assertFalse(components.room_options.video_input)
        audio_input = components.room_options.get_audio_input_options()
        audio_output = components.room_options.get_audio_output_options()
        self.assertIsNotNone(audio_input)
        self.assertIsNotNone(audio_output)
        self.assertEqual(16_000, audio_input.sample_rate)  # type: ignore[union-attr]
        self.assertEqual(24_000, audio_output.sample_rate)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
