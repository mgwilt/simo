from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator
from typing import cast

import httpx
from fastapi.testclient import TestClient
from livekit.agents import llm
from livekit.agents.voice.agent import ModelSettings
from simo.adapters.livekit.agent_session import PassageVoiceAgent, speech_passages
from simo.adapters.livekit.providers import LocalLLM, LocalTTS
from simo.config import RuntimeConfig
from simo.inference import AudioChunk
from simo.lan_site import _BrowserSessionIssuer
from simo.live_controls import ConversationSettings, LiveConversationControls, StaleSettingsError
from simo.livekit_room import LiveKitRoomConfig


def controls() -> LiveConversationControls:
    return LiveConversationControls(ConversationSettings("Explain fully", "Low, warm voice", 512))


class ControlsTests(unittest.TestCase):
    def test_atomic_revision_and_validation(self) -> None:
        state = controls()
        original = state.snapshot()
        self.assertEqual(original, state.update(original.as_dict()))
        edited = {**original.as_dict(), "prompt": "Include examples", "max_tokens": 1024}
        self.assertEqual(1, state.update(edited).revision)
        self.assertEqual("Explain fully", original.prompt)
        with self.assertRaises(StaleSettingsError):
            state.update(edited)
        for key, value in (
            ("max_tokens", True),
            ("max_tokens", 2049),
            ("prompt", ""),
            ("voice_instruction", "x" * 2001),
            ("revision", -1),
        ):
            with self.assertRaises((ValueError, TypeError)):
                state.update({**state.snapshot().as_dict(), key: value})
        self.assertEqual(1, state.snapshot().revision)
        with self.assertRaises(ValueError):
            state.update({**state.snapshot().as_dict(), "endpoint": "http://elsewhere"})

    def test_qwen_voice_changes_fail_explicitly(self) -> None:
        state = LiveConversationControls(controls().snapshot(), voice_editable=False)
        with self.assertRaisesRegex(ValueError, "Breeze"):
            state.update({**state.snapshot().as_dict(), "voice_instruction": "Different"})

    def test_passages_keep_short_replies_and_all_long_text(self) -> None:
        self.assertEqual(["a", "b"], list(speech_passages("ab", max_chars=1)))
        short = "One sentence. Another sentence. A third sentence."
        self.assertEqual([short], list(speech_passages(short)))
        for text in (short * 150, "x" * 8000, "沒有空格的句子。" * 1000, "words " * 2000):
            parts = list(speech_passages(text))
            self.assertEqual(text, "".join(parts))
            self.assertTrue(all(0 < len(part) <= 600 for part in parts))

    def test_http_controls_are_bounded_same_origin_and_live(self) -> None:
        state = controls()
        room = LiveKitRoomConfig(
            "ws://127.0.0.1:7880",
            "key",
            "secret",
            "room",
            "simo-browser",
            "LAN",
            frozenset({"simo-alias"}),
        )
        issuer = _BrowserSessionIssuer(
            room,
            RuntimeConfig.from_environment({}),
            alias_name="Ada",
            allowed_hosts=frozenset({"simo.local"}),
            https_port=8443,
            live_controls=state,
        )
        with TestClient(issuer.app, base_url="https://simo.local:8443") as raw_client:
            client = cast(httpx.Client, raw_client)
            response = client.get("/api/controls")
            self.assertEqual(200, response.status_code)
            payload = {**state.snapshot().as_dict(), "prompt": "Explain at length"}
            self.assertEqual(403, client.put("/api/controls", json=payload).status_code)
            self.assertEqual(
                403,
                client.put(
                    "/api/controls", json=payload, headers={"Origin": "https://hostile.example"}
                ).status_code,
            )
            headers = {"Origin": "https://simo.local:8443"}
            updated = client.put("/api/controls", json=payload, headers=headers)
            self.assertEqual(200, updated.status_code)
            self.assertEqual("Explain at length", state.snapshot().prompt)
            self.assertEqual(
                409, client.put("/api/controls", json=payload, headers=headers).status_code
            )
            self.assertEqual(400, client.put("/api/controls", json=[], headers=headers).status_code)
            self.assertEqual(
                413,
                client.put("/api/controls", json={"x": "x" * 48001}, headers=headers).status_code,
            )
            self.assertEqual(
                415, client.put("/api/controls", content="{}", headers=headers).status_code
            )
            self.assertEqual(
                400,
                client.get("/api/controls", headers={"Host": "hostile.example:8443"}).status_code,
            )


class RecordingGenerator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def generate(self, prompt: str, *, max_tokens: int) -> str:
        self.calls.append((prompt, max_tokens))
        return "First sentence. Second sentence. Third sentence. Fourth sentence."


class RecordingSynthesizer:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.closed = False
        self.block = False
        self.started = asyncio.Event()

    async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
        self.texts.append(text)
        self.started.set()
        try:
            if self.block:
                await asyncio.Event().wait()
            yield AudioChunk(b"\x00\x00" * 480, 24000)
        finally:
            self.closed = True


class LivePropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_next_llm_job_uses_new_prompt_and_budget_without_rewriting_inflight(self) -> None:
        state = controls()
        generator = RecordingGenerator()
        provider = LocalLLM(generator, live_controls=state)
        ctx = llm.ChatContext.empty()
        ctx.add_message(
            id="lk.agent_task.instructions", role="system", content="Old two-sentence instruction"
        )
        ctx.add_message(role="system", content="Retain the per-turn greeting instruction")
        ctx.add_message(role="user", content="Please explain")
        first = provider.chat(chat_ctx=ctx)
        state.update(
            {**state.snapshot().as_dict(), "prompt": "Develop examples", "max_tokens": 1024}
        )
        self.assertIn("Fourth sentence", (await first.collect()).text)
        await provider.chat(chat_ctx=ctx).collect()
        self.assertEqual([512, 1024], [budget for _, budget in generator.calls])
        self.assertIn("Explain fully", generator.calls[0][0])
        self.assertNotIn("Develop examples", generator.calls[0][0])
        self.assertIn("Develop examples", generator.calls[1][0])
        self.assertNotIn("Old two-sentence instruction", generator.calls[1][0])
        self.assertIn("Retain the per-turn greeting instruction", generator.calls[1][0])
        self.assertIn("Old two-sentence instruction", ctx.messages()[0].text_content or "")

    async def test_reply_groups_sentences_and_snapshots_one_voice(self) -> None:
        first, second = RecordingSynthesizer(), RecordingSynthesizer()
        selected = first
        calls = 0

        def factory() -> LocalTTS:
            nonlocal calls
            calls += 1
            return LocalTTS(selected)

        agent = PassageVoiceAgent(
            instructions="Test", chat_ctx=llm.ChatContext.empty(), provider_factory=factory
        )

        async def text() -> AsyncIterator[str]:
            nonlocal selected
            yield "One sentence. "
            selected = second
            yield "Another sentence."

        _ = [frame async for frame in agent.tts_node(text(), ModelSettings())]
        self.assertEqual(["One sentence. Another sentence."], first.texts)
        self.assertEqual([], second.texts)
        self.assertEqual(1, calls)
        _ = [frame async for frame in agent.tts_node(text(), ModelSettings())]
        self.assertEqual(["One sentence. Another sentence."], second.texts)

    async def test_cancellation_closes_provider_and_next_request_works(self) -> None:
        synth = RecordingSynthesizer()
        synth.block = True
        agent = PassageVoiceAgent(
            instructions="Test",
            chat_ctx=llm.ChatContext.empty(),
            provider_factory=lambda: LocalTTS(synth),
        )

        async def text() -> AsyncIterator[str]:
            yield "One sentence. A second sentence."

        async def speak() -> None:
            async for _ in agent.tts_node(text(), ModelSettings()):
                pass

        task = asyncio.create_task(speak())
        await asyncio.wait_for(synth.started.wait(), timeout=2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(synth.closed)
        synth.block = False
        await speak()


if __name__ == "__main__":
    unittest.main()
