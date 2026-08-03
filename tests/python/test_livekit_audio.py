from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

import jwt

os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[1] / "fixtures/nltk_data"),
)

from simo.adapters.pipecat.livekit_audio import (
    LiveKitRoomConfig,
    SimoLiveKitTransport,
    local_livekit_server_command,
)


class LiveKitRoomConfigTests(unittest.IsolatedAsyncioTestCase):
    def config(self) -> LiveKitRoomConfig:
        return LiveKitRoomConfig(
            "ws://127.0.0.1:7880",
            "devkey",
            "development-secret-that-is-long-enough",
            "simo-lab",
            "alias:ada",
            "Ada",
            frozenset({"alias:grace"}),
        )

    def test_join_token_is_room_scoped_and_cannot_publish_data(self) -> None:
        config = self.config()

        claims = cast(
            dict[str, object],
            jwt.decode(  # pyright: ignore[reportUnknownMemberType]
                config.issue_join_token(), options={"verify_signature": False}
            ),
        )

        self.assertEqual("alias:ada", claims["sub"])
        self.assertEqual("devkey", claims["iss"])
        self.assertEqual("Ada", claims["name"])
        self.assertEqual(
            {
                "roomJoin": True,
                "room": "simo-lab",
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": False,
                "canPublishSources": ["microphone"],
            },
            claims["video"],
        )
        self.assertNotIn(config.api_secret, repr(config))

    def test_subscription_gate_accepts_only_declared_remote_audio(self) -> None:
        config = self.config()

        self.assertTrue(config.allows_remote_audio("alias:grace", audio=True))
        self.assertFalse(config.allows_remote_audio("alias:grace", audio=False))
        self.assertFalse(config.allows_remote_audio("alias:mallory", audio=True))
        self.assertFalse(config.allows_remote_audio("alias:ada", audio=True))

    def test_environment_loader_fails_closed_without_room_service(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "not configured"):
                LiveKitRoomConfig.from_environment(
                    room_name="simo-lab",
                    participant_identity="alias:ada",
                    participant_name="Ada",
                    allowed_remote_identities=frozenset({"alias:grace"}),
                )

    def test_environment_loader_accepts_loopback_development_service(self) -> None:
        environment = {
            "SIMO_LIVEKIT_URL": "ws://localhost:7880",
            "SIMO_LIVEKIT_API_KEY": "devkey",
            "SIMO_LIVEKIT_API_SECRET": "secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = LiveKitRoomConfig.from_environment(
                room_name="simo-lab",
                participant_identity="alias:ada",
                participant_name="Ada",
                allowed_remote_identities=frozenset({"alias:grace"}),
            )

        self.assertEqual("ws://localhost:7880", config.server_url)

    def test_validation_rejects_insecure_remote_and_self_subscription(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            LiveKitRoomConfig(
                "ws://livekit.example.com",
                "key",
                "secret",
                "room",
                "alias:ada",
                "Ada",
                frozenset({"alias:grace"}),
            )
        with self.assertRaisesRegex(ValueError, "local LiveKit identity"):
            LiveKitRoomConfig(
                "wss://livekit.example.com",
                "key",
                "secret",
                "room",
                "alias:ada",
                "Ada",
                frozenset({"alias:ada"}),
            )

    async def test_transport_exposes_audio_only_pipecat_processors(self) -> None:
        transport = SimoLiveKitTransport(self.config())

        self.assertIs(transport.input(), transport.input())
        self.assertIs(transport.output(), transport.output())
        self.assertIsNone(transport.local_participant_sid)
        self.assertEqual((), transport.remote_audio_subscriptions)

    def test_server_command_requires_digest_and_loopback_ports(self) -> None:
        image = "livekit/livekit-server@sha256:" + "a" * 64
        command = local_livekit_server_command(image=image)

        self.assertEqual("docker", command[0])
        self.assertIn("127.0.0.1:7880:7880/tcp", command)
        self.assertIn("127.0.0.1:7882:7882/udp", command)
        self.assertIn(image, command)
        with self.assertRaisesRegex(ValueError, "sha256"):
            local_livekit_server_command(image="livekit/livekit-server:latest")


if __name__ == "__main__":
    unittest.main()
