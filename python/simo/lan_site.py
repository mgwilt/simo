"""Supervise one trusted-LAN browser conversation with a persisted Simo alias."""

from __future__ import annotations

import asyncio
import hashlib
import io
import secrets
import shutil
import signal
import socket
import tempfile
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlparse
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from simo.config import RuntimeConfig
from simo.inference import BreezeHTTPSynthesizer
from simo.livekit_local_server import LocalLiveKitServer
from simo.livekit_room import LiveKitRoomConfig
from simo.livekit_runtime import LiveKitAliasRunRequest, LiveKitAliasRuntime
from simo.persistence import SimoStore

_LOOPBACK: Final = "127.0.0.1"
_BOT_IDENTITY: Final = "simo-alias"
_HUMAN_IDENTITY: Final = "simo-browser"


@dataclass(frozen=True, slots=True)
class VoicePreviewPreset:
    preset_id: str
    label: str
    description: str
    instruction: str
    text: str
    seed: int


VOICE_PREVIEW_PRESETS: Final = (
    VoicePreviewPreset(
        "warm-companion",
        "Warm companion",
        "Soft, intimate, and reassuring",
        (
            "A warm adult feminine voice with a soft lower register, intimate presence, "
            "gentle pacing, and reassuring emotional warmth. Speak naturally, never theatrically."
        ),
        "I am here with you. We can take this one thoughtful step at a time.",
        17,
    ),
    VoicePreviewPreset(
        "bright-guide",
        "Bright guide",
        "Youthful, crisp, and energetic",
        (
            "A bright youthful androgynous voice with crisp diction, light energy, a subtle "
            "smile, and an upbeat conversational rhythm. Keep the delivery intelligent and grounded."
        ),
        "I am here with you. We can take this one thoughtful step at a time.",
        29,
    ),
    VoicePreviewPreset(
        "grounded-mentor",
        "Grounded mentor",
        "Mature, resonant, and unhurried",
        (
            "A mature masculine voice with a resonant baritone, measured pacing, calm authority, "
            "and precise articulation. Sound thoughtful and present rather than formal."
        ),
        "I am here with you. We can take this one thoughtful step at a time.",
        41,
    ),
)


@dataclass(frozen=True, slots=True)
class LanSiteSettings:
    alias_id: str
    hostname: str
    certificate: Path
    private_key: Path
    node_ip: str
    https_port: int = 8443
    rtc_tcp_port: int = 7881
    rtc_udp_port: int = 7882

    def __post_init__(self) -> None:
        if not self.alias_id.strip() or not self.hostname.strip():
            raise ValueError("LAN alias and hostname must not be empty")
        if not self.certificate.is_file() or not self.private_key.is_file():
            raise ValueError("LAN HTTPS certificate and private key must exist")
        parsed_ip = socket.inet_aton(self.node_ip)
        if not parsed_ip or self.node_ip.startswith("127."):
            raise ValueError("LAN node IP must be a non-loopback IPv4 address")
        if any(port <= 0 or port > 65_535 for port in self.public_ports):
            raise ValueError("LAN ports must be between 1 and 65535")

    @property
    def public_ports(self) -> tuple[int, int, int]:
        return (self.https_port, self.rtc_tcp_port, self.rtc_udp_port)

    @property
    def site_url(self) -> str:
        return f"https://{self.hostname}:{self.https_port}"

    @classmethod
    def create(
        cls,
        *,
        alias_id: str,
        certificate: Path,
        private_key: Path,
        hostname: str | None = None,
        node_ip: str | None = None,
        https_port: int = 8443,
    ) -> LanSiteSettings:
        selected_hostname = hostname or f"{socket.gethostname().split('.', 1)[0]}.local"
        return cls(
            alias_id,
            selected_hostname,
            certificate.resolve(),
            private_key.resolve(),
            node_ip or discover_lan_ip(),
            https_port,
        )


@dataclass(frozen=True, slots=True)
class LanSiteResult:
    site_url: str
    conversation_id: str
    close_reason: str


class _BrowserSessionIssuer:
    def __init__(
        self,
        room: LiveKitRoomConfig,
        config: RuntimeConfig,
        *,
        alias_name: str,
        allowed_hosts: frozenset[str],
        https_port: int,
    ) -> None:
        self._room = room
        self._config = config
        self._alias_name = alias_name
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self._https_port = https_port
        self._preview_lock = asyncio.Lock()
        self._preview_cache = config.repository / ".artifacts" / "breeze-previews"
        self.app = FastAPI(title="Simo LAN voice session", docs_url=None, redoc_url=None)
        self.app.post("/api/session")(self.issue)
        self.app.get("/api/health")(self.health)
        self.app.get("/api/previews")(self.previews)
        self.app.post("/api/previews/{preset_id}")(self.preview)

    async def issue(self, request: Request) -> dict[str, str]:
        host_header = request.headers.get("host", "")
        try:
            parsed = urlparse(f"//{host_header}")
            host = (parsed.hostname or "").lower()
            port = parsed.port
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid LAN host") from error
        if host not in self._allowed_hosts or port != self._https_port:
            raise HTTPException(status_code=400, detail="Invalid LAN host")
        return {
            "aliasName": self._alias_name,
            # Follow the address the browser actually used. This matters when a
            # device can reach the IPv4 fallback but cannot resolve mDNS.
            "serverUrl": f"wss://{host_header}",
            "participantToken": self._room.issue_join_token(),
        }

    async def health(self) -> dict[str, str]:
        return {"status": "ready"}

    async def previews(self) -> dict[str, object]:
        return {
            "text": VOICE_PREVIEW_PRESETS[0].text,
            "render_note": "An uncached sample can take about one minute on the current MPS path.",
            "presets": [
                {
                    "id": preset.preset_id,
                    "label": preset.label,
                    "description": preset.description,
                    "instruction": preset.instruction,
                    "cached": self._preview_path(preset).is_file(),
                }
                for preset in VOICE_PREVIEW_PRESETS
            ],
        }

    async def preview(self, preset_id: str) -> Response:
        preset = next(
            (item for item in VOICE_PREVIEW_PRESETS if item.preset_id == preset_id),
            None,
        )
        if preset is None:
            raise HTTPException(status_code=404, detail="Unknown voice preview")
        path = self._preview_path(preset)
        cache_status = "HIT"
        async with self._preview_lock:
            if not path.is_file():
                cache_status = "MISS"
                synthesizer = BreezeHTTPSynthesizer(
                    self._config.tts_endpoint,
                    instruction=preset.instruction,
                    cfg_scale=self._config.tts_cfg_scale,
                    seed=preset.seed,
                    timeout_s=self._config.tts_timeout_s,
                )
                pcm = bytearray()
                sample_rate = 24_000
                async for chunk in synthesizer.synthesize(preset.text):
                    pcm.extend(chunk.pcm_s16le)
                    sample_rate = chunk.sample_rate
                if not pcm:
                    raise HTTPException(status_code=502, detail="Breeze returned no preview audio")
                payload = _wav_s16le(bytes(pcm), sample_rate)
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(f".{uuid4().hex}.tmp")
                temporary.write_bytes(payload)
                temporary.replace(path)
            payload = path.read_bytes()
        return Response(
            payload,
            media_type="audio/wav",
            headers={"Cache-Control": "private, max-age=86400", "X-Simo-Cache": cache_status},
        )

    def _preview_path(self, preset: VoicePreviewPreset) -> Path:
        fingerprint = hashlib.sha256(
            (
                f"{preset.instruction}\n{preset.text}\n{preset.seed}\n{self._config.tts.revision}"
            ).encode()
        ).hexdigest()[:12]
        return self._preview_cache / f"{preset.preset_id}-{fingerprint}.wav"


async def run_lan_site(
    store: SimoStore,
    config: RuntimeConfig,
    settings: LanSiteSettings,
    *,
    conversation_id: str | None = None,
    livekit_binary: str | None = None,
    caddy_binary: str | None = None,
    ready: Callable[[str], None] | None = None,
) -> LanSiteResult:
    """Run one browser-scoped alias room until interrupted or disconnected."""

    alias = store.get_alias(settings.alias_id)
    livekit = await _start_lan_livekit(settings, livekit_binary)
    run_id = uuid4().hex[:12]
    room_name = f"simo-lan-{run_id}"
    bot_room = LiveKitRoomConfig(
        livekit.server_url,
        livekit.api_key,
        livekit.api_secret,
        room_name,
        _BOT_IDENTITY,
        alias.display_name,
        frozenset({_HUMAN_IDENTITY}),
    )
    human_room = LiveKitRoomConfig(
        livekit.server_url,
        livekit.api_key,
        livekit.api_secret,
        room_name,
        _HUMAN_IDENTITY,
        "LAN browser",
        frozenset({_BOT_IDENTITY}),
    )
    issuer = _BrowserSessionIssuer(
        human_room,
        config,
        alias_name=alias.display_name,
        allowed_hosts=frozenset({settings.hostname, settings.node_ip}),
        https_port=settings.https_port,
    )
    backend_port = _available_port()
    backend = uvicorn.Server(
        uvicorn.Config(
            issuer.app,
            host=_LOOPBACK,
            port=backend_port,
            log_level="warning",
            access_log=False,
        )
    )
    backend_task = asyncio.create_task(backend.serve(), name="simo-lan-site-api")
    caddy: asyncio.subprocess.Process | None = None
    bot_task: asyncio.Task[object] | None = None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed_signals: list[signal.Signals] = []
    try:
        await _wait_for_tcp(_LOOPBACK, backend_port, 8.0)
        caddy = await _start_caddy(settings, backend_port, livekit.server_url, caddy_binary)
        await _wait_for_tcp(settings.node_ip, settings.https_port, 8.0)
        request = LiveKitAliasRunRequest(
            settings.alias_id,
            "human:lan-browser",
            "LAN browser",
            _HUMAN_IDENTITY,
            conversation_id=conversation_id,
            complete_on_close=False,
        )
        runtime = LiveKitAliasRuntime(store, config, bot_room)
        bot_task = asyncio.create_task(runtime.run(request), name="simo-lan-alias")
        for selected_signal in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(selected_signal, stop.set)
                installed_signals.append(selected_signal)
            except NotImplementedError:
                pass
        if ready is not None:
            ready(settings.site_url)
        stop_task = asyncio.create_task(stop.wait(), name="simo-lan-stop")
        done, _ = await asyncio.wait(
            {bot_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if bot_task in done:
            bot_result = await bot_task
            stop_task.cancel()
            await asyncio.gather(stop_task, return_exceptions=True)
            return LanSiteResult(
                settings.site_url,
                bot_result.conversation_id,
                bot_result.close_reason,
            )
        bot_task.cancel()
        await asyncio.gather(bot_task, return_exceptions=True)
        return LanSiteResult(settings.site_url, conversation_id or "pending", "operator")
    finally:
        for selected_signal in installed_signals:
            loop.remove_signal_handler(selected_signal)
        if bot_task is not None and not bot_task.done():
            bot_task.cancel()
            await asyncio.gather(bot_task, return_exceptions=True)
        backend.should_exit = True
        await asyncio.gather(backend_task, return_exceptions=True)
        if caddy is not None and caddy.returncode is None:
            caddy.terminate()
            await asyncio.gather(caddy.wait(), return_exceptions=True)
        await livekit.aclose()


async def _start_lan_livekit(
    settings: LanSiteSettings,
    binary_override: str | None,
) -> LocalLiveKitServer:
    binary = binary_override or shutil.which("livekit-server")
    if binary is None:
        raise RuntimeError("livekit-server is required")
    internal_port = _available_port()
    api_key = f"simo{secrets.token_hex(8)}"
    api_secret = secrets.token_urlsafe(32)
    process = await asyncio.create_subprocess_exec(
        binary,
        "--bind",
        _LOOPBACK,
        "--node-ip",
        settings.node_ip,
        "--port",
        str(internal_port),
        "--rtc.tcp_port",
        str(settings.rtc_tcp_port),
        "--udp-port",
        str(settings.rtc_udp_port),
        "--keys",
        f"{api_key}: {api_secret}\n",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await _wait_for_tcp(_LOOPBACK, internal_port, 8.0)
    except BaseException:
        process.terminate()
        await process.wait()
        raise
    return LocalLiveKitServer(
        f"ws://{_LOOPBACK}:{internal_port}",
        api_key,
        api_secret,
        "1.13.5",
        process,
    )


async def _start_caddy(
    settings: LanSiteSettings,
    backend_port: int,
    livekit_url: str,
    binary_override: str | None,
) -> asyncio.subprocess.Process:
    binary = binary_override or shutil.which("caddy")
    if binary is None:
        raise RuntimeError("caddy is required for trusted LAN HTTPS and WSS")
    web_root = Path(__file__).resolve().parents[2] / "web" / "dist"
    if not (web_root / "index.html").is_file():
        raise RuntimeError("LAN site assets are not built; run pnpm --dir web build")
    livekit_port = int(livekit_url.rsplit(":", 1)[1])
    caddyfile = _caddyfile(settings, backend_port, livekit_port, web_root)
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="simo-caddy-",
        suffix=".Caddyfile",
        delete=False,
    )
    with temporary:
        temporary.write(caddyfile)
    process = await asyncio.create_subprocess_exec(
        binary,
        "run",
        "--config",
        temporary.name,
        "--adapter",
        "caddyfile",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return process


def _caddyfile(
    settings: LanSiteSettings,
    backend_port: int,
    livekit_port: int,
    web_root: Path,
) -> str:
    for value in (
        settings.hostname,
        settings.node_ip,
        str(settings.certificate),
        str(settings.private_key),
        str(web_root),
    ):
        if any(character in value for character in ('"', "\n", "\r")):
            raise ValueError("LAN TLS paths and host values must not contain quotes or newlines")
    return f"""https://{settings.hostname}:{settings.https_port}, https://{settings.node_ip}:{settings.https_port} {{
    tls "{settings.certificate}" "{settings.private_key}"
    handle /api/* {{
        reverse_proxy {_LOOPBACK}:{backend_port}
    }}
    handle /rtc* {{
        reverse_proxy {_LOOPBACK}:{livekit_port}
    }}
    handle {{
        root * "{web_root}"
        try_files {{path}} /index.html
        file_server
    }}
}}
"""


def discover_lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as selected:
        try:
            selected.connect(("192.0.2.1", 9))
            address = cast(tuple[str, int], selected.getsockname())[0]
        except OSError as error:
            raise RuntimeError("could not discover a LAN IPv4 address; pass --node-ip") from error
    if address.startswith("127."):
        raise RuntimeError("could not discover a non-loopback LAN IPv4 address")
    return address


def _wav_s16le(pcm: bytes, sample_rate: int) -> bytes:
    if not pcm or len(pcm) % 2 or sample_rate <= 0:
        raise ValueError("preview PCM must be aligned, non-empty, and have a sample rate")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as selected:
        selected.bind((_LOOPBACK, 0))
        return cast(tuple[str, int], selected.getsockname())[1]


async def _wait_for_tcp(host: str, port: int, timeout_s: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        try:
            _, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError:
            await asyncio.sleep(0.05)
    raise RuntimeError(f"service did not become ready at {host}:{port}")
