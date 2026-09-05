"""An isolated, trusted-LAN experimental preview site; no conversation runtime."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from simo.breeze import health as breeze_health
from simo.config import RuntimeConfig, TTSBackend
from simo.lan_site import VoicePreviewService


@dataclass(frozen=True, slots=True)
class PreviewSiteSettings:
    node_ip: str
    certificate: Path
    private_key: Path
    assets: Path
    https_port: int = 8444
    hostname: str | None = None
    streaming_runtime: str | None = None
    enable_benchmarks: bool = False
    listening_deck: Path | None = None
    listening_results: Path | None = None

    def __post_init__(self) -> None:
        address = ipaddress.IPv4Address(self.node_ip)
        if (
            not address.is_private
            or address.is_loopback
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        ):
            raise ValueError("Preview site requires a specific private LAN IPv4 address")
        if not 1 <= self.https_port <= 65535 or self.https_port in (8443, 7881, 7882, 7860):
            raise ValueError("Preview site requires a separate valid HTTPS port")
        if not self.certificate.is_file() or not self.private_key.is_file():
            raise ValueError("Existing trusted TLS certificate and key are required")
        if self.hostname is not None and (
            not self.hostname
            or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
                for char in self.hostname
            )
        ):
            raise ValueError("Invalid preview hostname")
        validate_assets(self.assets)
        if self.listening_results is not None:
            if self.listening_deck is None:
                raise ValueError("Listening results require a listening deck")
            results = self.listening_results.resolve()
            if results.is_relative_to(
                self.assets.resolve()
            ) or self.assets.resolve().is_relative_to(results):
                raise ValueError("Listening results must be separate from served assets")
            if results.is_relative_to(
                self.listening_deck.resolve().parent
            ) or self.listening_deck.resolve().parent.is_relative_to(results):
                raise ValueError("Listening results require their own directory")
        if self.streaming_runtime is not None and (
            len(self.streaming_runtime) != 64
            or any(char not in "0123456789abcdef" for char in self.streaming_runtime)
        ):
            raise ValueError("Streaming previews require an exact runtime fingerprint")
        if self.enable_benchmarks and self.streaming_runtime is None:
            raise ValueError("Benchmarks require an explicitly selected streaming runtime")

    @property
    def authorities(self) -> frozenset[str]:
        return frozenset(
            f"{host.lower()}:{self.https_port}"
            for host in (self.hostname or self.node_ip, self.node_ip)
        )

    @property
    def site_url(self) -> str:
        return f"https://{self.hostname or self.node_ip}:{self.https_port}"


def validate_assets(root: Path) -> None:
    if not (root / "preview.html").is_file():
        raise ValueError("Build the separate preview assets with pnpm --dir web build:preview")
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink() or (
            path.is_file()
            and not (
                relative.as_posix() in ("preview.html", "pcm-worklet.js", "pcm-queue.js")
                or (relative.parts[0] == "assets" and path.suffix in (".js", ".css"))
            )
        ):
            raise ValueError("Preview asset directory contains unexpected files or symlinks")


class PreviewBoundary:
    def __init__(self, app: ASGIApp, *, authorities: frozenset[str]) -> None:
        self.app, self.authorities = app, authorities

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        pairs = cast(list[tuple[bytes, bytes]], scope["headers"])
        headers = {key.lower(): value.decode("latin1") for key, value in pairs}
        host = headers.get(b"host", "").lower()
        origin = headers.get(b"origin")
        if host not in self.authorities:
            await Response("Invalid preview host", status_code=400)(scope, receive, send)
            return
        if origin is not None and origin.lower() != f"https://{host}":
            await Response("Cross-origin preview requests are not allowed", status_code=403)(
                scope, receive, send
            )
            return

        async def no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = cast(list[tuple[bytes, bytes]], message["headers"])
                message["headers"] = [
                    (key, value)
                    for key, value in response_headers
                    if key.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store")]
            await send(message)

        await self.app(
            scope,
            receive,
            no_store
            if cast(str, scope["path"]).startswith(("/api/benchmarks", "/api/listening"))
            else send,
        )


class ExperimentalPreviewService(VoicePreviewService):
    def __init__(self, config: RuntimeConfig, *, streaming_runtime: str | None = None) -> None:
        super().__init__(config)
        self._streaming_runtime = streaming_runtime

    def enable_benchmarks(self, assets: Path) -> None:
        from simo.breeze_benchmark import attach_benchmarks

        if self._streaming_runtime is None:
            raise ValueError("Benchmarks require an explicitly selected streaming runtime")
        attach_benchmarks(
            self.app,
            self._config,
            assets,
            self._streaming_runtime,
            lock=self._preview_lock,
            check_runtime=self._runtime_fingerprint,
        )

    @property
    def playback_policy(self) -> str:
        return "mlx-stream-v1" if self._streaming_runtime is not None else "complete-clip"

    async def _runtime_fingerprint(self) -> str:
        try:
            payload = await asyncio.to_thread(breeze_health, self._config)
        except (OSError, ValueError) as error:
            raise HTTPException(
                status_code=503, detail="Experimental Breeze is unavailable"
            ) from error
        fingerprint = payload.get("runtime_fingerprint")
        expected = {
            "status": "ready",
            "experimental_recipe": "mlx-int8-v1",
            "performance_mode": "experimental",
            "sample_rate": 24_000,
        }
        valid_identity = (
            all(payload.get(key) == value for key, value in expected.items())
            and payload.get("release_accepted") is False
        )
        if (
            not valid_identity
            or not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            raise HTTPException(
                status_code=503, detail="Expected the unaccepted mlx-int8-v1 experimental runtime"
            )
        if self._streaming_runtime is not None and fingerprint != self._streaming_runtime:
            raise HTTPException(status_code=503, detail="The selected streaming runtime changed")
        return fingerprint

    async def health(self) -> dict[str, str]:
        fingerprint = await self._runtime_fingerprint()
        return {
            "status": "ready",
            "experimental_recipe": "mlx-int8-v1",
            "runtime_fingerprint": fingerprint,
            "playback_policy": self.playback_policy,
        }

    async def previews(self) -> dict[str, object]:
        fingerprint = await self._runtime_fingerprint()
        return {
            **await super().previews(),
            "experimental_recipe": "mlx-int8-v1",
            "playback_policy": self.playback_policy,
            "runtime_fingerprint": fingerprint,
            "render_note": (
                "Experimental streaming uses a 640ms reserve and a bounded two-second queue."
                if self._streaming_runtime is not None
                else "The complete clip is buffered before playback."
            ),
        }

    async def preview_stream(self, preset_id: str) -> Response:
        response = await super().preview_stream(preset_id)
        response.headers["X-Simo-Playback-Policy"] = self.playback_policy
        return response

    async def preview(self, preset_id: str) -> Response:
        response = await super().preview(preset_id)
        response.headers["X-Simo-Playback-Policy"] = self.playback_policy
        return response


def create_preview_site(
    config: RuntimeConfig, settings: PreviewSiteSettings
) -> ExperimentalPreviewService:
    if config.tts_backend is not TTSBackend.BREEZE or config.tts_cfg_scale != 4.0:
        raise ValueError("Experimental previews require Breeze with explicit CFG4")
    service = ExperimentalPreviewService(config, streaming_runtime=settings.streaming_runtime)
    service.app.title = "Simo experimental MLX previews"
    service.app.router.routes[:] = [
        route
        for route in service.app.router.routes
        if not isinstance(route, Route) or route.path != "/openapi.json"
    ]
    # Starlette's factory protocol widens ASGI messages to Any, unlike its ASGIApp alias.
    service.app.add_middleware(PreviewBoundary, authorities=settings.authorities)  # ty: ignore[invalid-argument-type]
    if settings.enable_benchmarks:
        service.enable_benchmarks(settings.assets)
    if settings.listening_deck is not None:
        from simo.breeze_listening import attach_listening

        attach_listening(service.app, settings.listening_deck, results=settings.listening_results)

    @service.app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(settings.assets / "preview.html", headers={"Cache-Control": "no-cache"})

    service.app.mount("/", StaticFiles(directory=settings.assets), name="preview-assets")
    return service


async def run_preview_site(
    config: RuntimeConfig,
    settings: PreviewSiteSettings,
    *,
    ready: Callable[[str], None] | None = None,
) -> None:
    service = create_preview_site(config, settings)
    await service.health()  # Never label another backend as this experiment.
    server = uvicorn.Server(
        uvicorn.Config(
            service.app,
            host=settings.node_ip,
            port=settings.https_port,
            ssl_certfile=str(settings.certificate),
            ssl_keyfile=str(settings.private_key),
            proxy_headers=False,
            access_log=False,
            log_level="warning",
            timeout_graceful_shutdown=5,
        )
    )
    # Own the exact listener before spawning; an unrelated open port is not readiness.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((settings.node_ip, settings.https_port))
        listener.listen(128)
        task = asyncio.create_task(
            server.serve(sockets=[listener]), name="simo-experimental-preview"
        )
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                        raise RuntimeError("Preview server stopped before readiness")
                    await asyncio.sleep(0.02)
            if ready is not None:
                ready(settings.site_url)
            await asyncio.shield(task)
        finally:
            server.should_exit = True
            await asyncio.gather(task, return_exceptions=True)
