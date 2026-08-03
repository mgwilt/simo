"""Lifecycle owner for one loopback-only development LiveKit server."""

from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from time import monotonic
from typing import Final, cast

SERVER_HOST: Final = "127.0.0.1"
DEV_API_KEY: Final = "devkey"
DEV_API_SECRET: Final = "simo-local-development-secret-2026"


@dataclass(slots=True)
class LocalLiveKitServer:
    server_url: str
    api_key: str
    api_secret: str = field(repr=False)
    version: str
    _process: asyncio.subprocess.Process = field(repr=False)

    async def aclose(self) -> None:
        if self._process.returncode is not None:
            return
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()


async def start_local_livekit_server(
    server_binary: str | None = None,
) -> LocalLiveKitServer:
    """Start a fresh loopback room service on ephemeral TCP and UDP ports."""

    binary = server_binary or shutil.which("livekit-server")
    if binary is None:
        raise RuntimeError("livekit-server is required; install the Homebrew livekit formula")
    server_port = _available_port(socket.SOCK_STREAM)
    udp_port = _available_port(socket.SOCK_DGRAM)
    process = await asyncio.create_subprocess_exec(
        binary,
        "--dev",
        "--bind",
        SERVER_HOST,
        "--node-ip",
        SERVER_HOST,
        "--udp-port",
        str(udp_port),
        "--config-body",
        f"port: {server_port}",
        "--keys",
        f"{DEV_API_KEY}: {DEV_API_SECRET}\n",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await _wait_for_server(server_port, timeout_s=8.0)
        version = _server_version(binary)
    except BaseException:
        temporary = LocalLiveKitServer(
            f"ws://{SERVER_HOST}:{server_port}",
            DEV_API_KEY,
            DEV_API_SECRET,
            "unknown",
            process,
        )
        await temporary.aclose()
        raise
    return LocalLiveKitServer(
        f"ws://{SERVER_HOST}:{server_port}",
        DEV_API_KEY,
        DEV_API_SECRET,
        version,
        process,
    )


async def _wait_for_server(port: int, *, timeout_s: float) -> None:
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        try:
            reader, writer = await asyncio.open_connection(SERVER_HOST, port)
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


def _available_port(socket_type: socket.SocketKind) -> int:
    with socket.socket(socket.AF_INET, socket_type) as selected:
        selected.bind((SERVER_HOST, 0))
        return cast(int, selected.getsockname()[1])


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
