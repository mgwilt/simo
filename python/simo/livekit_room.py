"""Provider-neutral LiveKit room authentication and local-server contracts."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlparse

from livekit import api

_INSECURE_SCHEME: Final = "ws"
_SECURE_SCHEME: Final = "wss"
_LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "::1", "localhost"})


@dataclass(frozen=True, slots=True)
class LiveKitRoomConfig:
    """Authenticated room scope for one independently identified Simo."""

    server_url: str
    api_key: str
    api_secret: str = field(repr=False)
    room_name: str
    participant_identity: str
    participant_name: str
    allowed_remote_identities: frozenset[str]

    def __post_init__(self) -> None:
        parsed = urlparse(self.server_url)
        if parsed.scheme not in {_INSECURE_SCHEME, _SECURE_SCHEME} or not parsed.hostname:
            raise ValueError("LiveKit URL must use ws:// or wss:// with a host")
        if parsed.scheme == _INSECURE_SCHEME and parsed.hostname not in _LOOPBACK_HOSTS:
            raise ValueError("unencrypted LiveKit is permitted only on the local loopback")
        required = {
            "API key": self.api_key,
            "API secret": self.api_secret,
            "room name": self.room_name,
            "participant identity": self.participant_identity,
            "participant name": self.participant_name,
        }
        for label, value in required.items():
            if not value.strip():
                raise ValueError(f"LiveKit {label} must not be empty")
        if not self.allowed_remote_identities:
            raise ValueError("LiveKit room scope requires at least one allowed remote identity")
        if any(not identity.strip() for identity in self.allowed_remote_identities):
            raise ValueError("allowed LiveKit remote identities must not be empty")
        if self.participant_identity in self.allowed_remote_identities:
            raise ValueError("local LiveKit identity cannot also be an allowed remote identity")

    @classmethod
    def from_environment(
        cls,
        *,
        room_name: str,
        participant_identity: str,
        participant_name: str,
        allowed_remote_identities: frozenset[str],
    ) -> LiveKitRoomConfig:
        """Load credentials without accepting secrets on the process command line."""

        values = {
            "server_url": os.environ.get("SIMO_LIVEKIT_URL", ""),
            "api_key": os.environ.get("SIMO_LIVEKIT_API_KEY", ""),
            "api_secret": os.environ.get("SIMO_LIVEKIT_API_SECRET", ""),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            names = ", ".join(name.upper() for name in missing)
            raise ValueError(f"LiveKit room service is not configured: missing {names}")
        return cls(
            **values,
            room_name=room_name,
            participant_identity=participant_identity,
            participant_name=participant_name,
            allowed_remote_identities=allowed_remote_identities,
        )

    def issue_join_token(self) -> str:
        """Issue the least-capable room token needed by an audio participant."""

        grants = api.VideoGrants(
            room_join=True,
            room=self.room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=False,
            can_publish_sources=["microphone"],
        )
        return (
            api.AccessToken(self.api_key, self.api_secret)
            .with_identity(self.participant_identity)
            .with_name(self.participant_name)
            .with_grants(grants)
            .to_jwt()
        )

    def allows_remote_audio(self, participant_identity: str, *, audio: bool) -> bool:
        """Return whether a remote publication belongs in this media plane."""

        return audio and participant_identity in self.allowed_remote_identities


def local_livekit_server_command(*, image: str) -> tuple[str, ...]:
    """Return a pinned, loopback-only Docker command without executing it."""

    selected = image.strip()
    if not selected or "@sha256:" not in selected:
        raise ValueError("LiveKit server image must be pinned by sha256 digest")
    return (
        "docker",
        "run",
        "--rm",
        "--name",
        "simo-livekit",
        "-p",
        "127.0.0.1:7880:7880/tcp",
        "-p",
        "127.0.0.1:7881:7881/tcp",
        "-p",
        "127.0.0.1:7882:7882/udp",
        selected,
        "--dev",
        "--bind",
        "0.0.0.0",  # noqa: S104 - container bind is host-published to loopback only.
        "--node-ip",
        "127.0.0.1",
        "--udp-port",
        "7882",
    )
