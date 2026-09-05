from __future__ import annotations

import asyncio
import copy
import io
import json
import tempfile
import unittest
from collections.abc import AsyncGenerator
from dataclasses import replace
from pathlib import Path
from typing import ClassVar, cast
from unittest.mock import patch

import httpx
from simo.breeze import BENCHMARK_PROMPTS, LONG_BENCHMARK_PROMPTS
from simo.breeze_benchmark import (
    POLICY,
    SCHEMA,
    BenchmarkConnection,
    _BenchmarkResponse,
    _completed_metrics,
    _identity,
    run_https_benchmark,
)
from simo.cli import main
from simo.config import RuntimeConfig
from simo.inference import AudioChunk, BreezeHTTPSynthesizer
from simo.lan_site import VOICE_PREVIEW_PRESETS
from simo.preview_site import PreviewSiteSettings, create_preview_site
from starlette.types import Message, Scope

FP = "a" * 64
RID = "api-" + "b" * 32
PCM = b"\x01\x00" * 3840


def runtime(request_id: str = RID) -> dict[str, object]:
    return {
        "status": "ready",
        "busy": False,
        "runtime_fingerprint": FP,
        "sample_rate": 24000,
        "experimental_recipe": "mlx-int8-v1",
        "performance_mode": "experimental",
        "release_accepted": False,
        "last_request": {
            "request_id": request_id,
            "completed": True,
            "cancelled": False,
            "eos_reached": True,
            "audio_samples": 3840,
            "codec_frames": 2,
            "audio_s": 0.16,
        },
    }


class FakeSynth:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    response_request_id = RID

    def __init__(self, endpoint: str, **kwargs: object) -> None:
        del endpoint
        self.settings = kwargs

    async def synthesize(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        self.calls.append((text, self.settings))
        yield AudioChunk(PCM[:3840], 24000)
        yield AudioChunk(PCM[3840:], 24000)


class BenchmarkRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        (self.assets / "preview.html").write_text("<h1>test</h1>")
        self.cert, self.key = self.root / "cert", self.root / "key"
        self.cert.touch()
        self.key.touch()
        self.config = replace(RuntimeConfig.from_environment({}), repository=self.root)
        self.settings = PreviewSiteSettings(
            "192.168.1.10",
            self.cert,
            self.key,
            self.assets,
            streaming_runtime=FP,
            enable_benchmarks=True,
        )
        FakeSynth.calls = []
        for name, value in (
            ("simo.preview_site.breeze_health", runtime()),
            ("simo.breeze_benchmark.health", runtime()),
        ):
            mock = patch(name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        synth = patch("simo.breeze_benchmark.BreezeHTTPSynthesizer", FakeSynth)
        synth.start()
        self.addCleanup(synth.stop)

    def client(self, *, enabled: bool = True) -> httpx.AsyncClient:
        service = create_preview_site(
            self.config, replace(self.settings, enable_benchmarks=enabled)
        )
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=service.app), base_url=self.settings.site_url
        )

    async def headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        response = await client.get("/api/benchmarks")
        self.assertEqual(response.status_code, 200)
        manifest = cast(dict[str, object], response.json())
        digest = manifest.pop("manifest_sha256")
        self.assertEqual(digest, _identity(manifest))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return {"X-Simo-Benchmark-Manifest": str(digest), "X-Simo-Runtime-Fingerprint": FP}

    async def test_disabled_by_default_and_requires_streaming(self) -> None:
        with self.assertRaises(ValueError):
            replace(self.settings, streaming_runtime=None)
        async with self.client(enabled=False) as client:
            for path in (
                "/api/benchmarks",
                f"/api/benchmarks/metrics/{RID}",
                "/api/benchmarks/short/0/stream",
            ):
                self.assertEqual((await client.get(path)).status_code, 404)
                self.assertIn((await client.post(path)).status_code, (404, 405))
        self.assertEqual(FakeSynth.calls, [])

    async def test_fixed_case_request_identity_and_no_cache_writes(self) -> None:
        async with self.client() as client:
            headers = await self.headers(client)
            for seed in (17, 29, 42):
                response = await client.post(
                    "/api/benchmarks/short/0/stream",
                    json={"seed": seed, "instruction_id": "bright-guide"},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, PCM)
                for key, value in {
                    **headers,
                    "X-Breeze-Request-ID": RID,
                    "X-Simo-Cache": "BYPASS",
                    "X-Simo-Playback-Policy": POLICY,
                }.items():
                    self.assertEqual(response.headers[key], value)
            measured = await client.get(f"/api/benchmarks/metrics/{RID}")
            self.assertEqual(measured.status_code, 200)
            self.assertEqual(measured.headers["Cache-Control"], "no-store")
            self.assertEqual(
                (await client.get("/api/benchmarks/metrics/api-" + "c" * 32)).status_code, 409
            )
        self.assertEqual([call[1]["seed"] for call in FakeSynth.calls], [17, 29, 42])
        self.assertTrue(
            all(
                call[0] == BENCHMARK_PROMPTS[0] and call[1]["require_request_id"] is True
                for call in FakeSynth.calls
            )
        )
        self.assertEqual(list(self.root.rglob("*.wav")), [])
        self.assertFalse((self.root / ".artifacts").exists())

    async def test_invalid_fields_seeds_headers_and_bounds_before_synthesis(self) -> None:
        async with self.client() as client:
            headers = {**await self.headers(client), "Content-Type": "application/json"}
            valid = {"seed": 17, "instruction_id": "default"}
            bodies = [
                b"null",
                b"[]",
                b"broken",
                b'{"seed":17,"seed":29,"instruction_id":"default"}',
                *[
                    json.dumps({**valid, "seed": seed}).encode()
                    for seed in (True, 1.5, -1, 2**32, "17")
                ],
                json.dumps({**valid, "text": "arbitrary"}).encode(),
                json.dumps({**valid, "instruction_id": "unknown"}).encode(),
            ]
            for body in bodies:
                with self.subTest(body=body):
                    response = await client.post(
                        "/api/benchmarks/short/0/stream", content=body, headers=headers
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
            for route in ("short/-1", "short/10", "long/2", "unknown/0"):
                self.assertEqual(
                    (
                        await client.post(
                            f"/api/benchmarks/{route}/stream", json=valid, headers=headers
                        )
                    ).status_code,
                    404,
                )
            for key, value in (
                ("X-Simo-Benchmark-Manifest", "b" * 64),
                ("X-Simo-Runtime-Fingerprint", "c" * 64),
            ):
                self.assertEqual(
                    (
                        await client.post(
                            "/api/benchmarks/short/0/stream",
                            json=valid,
                            headers={**headers, key: value},
                        )
                    ).status_code,
                    409,
                )
            self.assertEqual(
                (
                    await client.post(
                        "/api/benchmarks/short/0/stream?seed=29", json=valid, headers=headers
                    )
                ).status_code,
                400,
            )
            self.assertEqual(
                (
                    await client.post(
                        "/api/benchmarks/short/0/stream", content=b"x" * 1025, headers=headers
                    )
                ).status_code,
                413,
            )

            async def oversized() -> AsyncGenerator[bytes, None]:
                yield b"x" * 512
                yield b"x" * 513

            self.assertEqual(
                (
                    await client.post(
                        "/api/benchmarks/short/0/stream", content=oversized(), headers=headers
                    )
                ).status_code,
                413,
            )
        self.assertEqual(FakeSynth.calls, [])

    async def test_changed_source_build_or_runtime_and_incomplete_metrics_reject(self) -> None:
        async with self.client() as client:
            await self.headers(client)
            for changed in (
                {"runtime_fingerprint": "c" * 64},
                {"busy": True},
                {
                    "last_request": {
                        **cast(dict[str, object], runtime()["last_request"]),
                        "completed": False,
                    }
                },
            ):
                with patch("simo.breeze_benchmark.health", return_value={**runtime(), **changed}):
                    self.assertEqual(
                        (await client.get(f"/api/benchmarks/metrics/{RID}")).status_code, 409
                    )
            (self.assets / "preview.html").write_text("changed")
            self.assertEqual((await client.get("/api/benchmarks")).status_code, 503)

    async def test_disconnect_before_or_after_pcm_owns_close_on_asgi23_and24(self) -> None:
        for spec in ("2.3", "2.4"):
            for before_pcm in (True, False):
                began, disconnected, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
                released: list[bool] = []
                sent: list[Message] = []

                async def source(
                    began: asyncio.Event = began,
                    before_pcm: bool = before_pcm,
                    closed: asyncio.Event = closed,
                ) -> AsyncGenerator[bytes, None]:
                    try:
                        began.set()
                        if before_pcm:
                            await asyncio.Event().wait()
                        yield PCM
                        await asyncio.Event().wait()
                    finally:
                        closed.set()

                async def receive(disconnected: asyncio.Event = disconnected) -> Message:
                    await disconnected.wait()
                    return {"type": "http.disconnect"}

                async def send(message: Message, sent: list[Message] = sent) -> None:
                    sent.append(message)

                synth = cast(BreezeHTTPSynthesizer, FakeSynth("unused"))
                response = _BenchmarkResponse(
                    source(), synth, lambda released=released: released.append(True), {}
                )
                task = asyncio.create_task(
                    response(
                        cast(Scope, {"type": "http", "asgi": {"spec_version": spec}}), receive, send
                    )
                )
                await asyncio.wait_for(began.wait(), 1)
                await asyncio.sleep(0)
                disconnected.set()
                await asyncio.wait_for(task, 1)
                self.assertTrue(closed.is_set())
                self.assertEqual(released, [True])
                self.assertEqual(bool(sent), not before_pcm)

    async def test_pre_header_failure_and_empty_output_return_502_and_release(self) -> None:
        for empty in (True, False):
            released: list[bool] = []
            sent: list[Message] = []

            async def source(empty: bool = empty) -> AsyncGenerator[bytes, None]:
                if not empty:
                    raise RuntimeError("upstream failed")
                if False:
                    yield b""

            async def receive() -> Message:
                await asyncio.Event().wait()
                return {"type": "http.disconnect"}

            async def send(message: Message, sent: list[Message] = sent) -> None:
                sent.append(message)

            response = _BenchmarkResponse(
                source(),
                cast(BreezeHTTPSynthesizer, FakeSynth("unused")),
                lambda released=released: released.append(True),
                {},
            )
            await asyncio.wait_for(response(cast(Scope, {"type": "http"}), receive, send), 1)
            self.assertEqual(sent[0]["status"], 502)
            self.assertEqual(released, [True])


class BenchmarkClientTests(unittest.TestCase):
    def manifest(self, config: RuntimeConfig) -> dict[str, object]:
        value: dict[str, object] = {
            "schema": SCHEMA,
            "runtime_fingerprint": FP,
            "playback_policy": POLICY,
            "cfg_scale": config.tts_cfg_scale,
            "sample_rate": 24000,
            "suites": {"short": list(BENCHMARK_PROMPTS), "long": list(LONG_BENCHMARK_PROMPTS)},
            "instructions": {
                "default": config.tts_instruction,
                **{p.preset_id: p.instruction for p in VOICE_PREVIEW_PRESETS},
            },
        }
        return {**value, "manifest_sha256": _identity(value)}

    def test_client_retains_matched_schedule_identity_and_failed_attempt(self) -> None:
        config = RuntimeConfig.from_environment({})
        manifest = self.manifest(config)

        class ResponseFixture:
            status = 200

            def __init__(self, request_id: str) -> None:
                self.request_id = request_id
                self.data = io.BytesIO(PCM)

            def getheader(self, key: str) -> str | None:
                return {
                    "X-Simo-Runtime-Fingerprint": FP,
                    "X-Simo-Benchmark-Manifest": str(manifest["manifest_sha256"]),
                    "X-Simo-Playback-Policy": POLICY,
                    "X-Simo-Cache": "BYPASS",
                    "X-Sample-Rate": "24000",
                    "X-Sample-Format": "s16le",
                    "X-Breeze-Request-ID": self.request_id,
                }.get(key)

            def read1(self, size: int) -> bytes:
                return self.data.read(min(size, 3839))  # Deliberately odd wire boundaries.

            def close(self) -> None:
                pass

        class ClientFixture:
            cases: ClassVar[list[tuple[str, object]]] = []
            fail = False

            def __init__(self, *args: object) -> None:
                self.count = 0

            def json(self, path: str) -> dict[str, object]:
                if path == "/api/benchmarks":
                    return copy.deepcopy(manifest)
                measured = runtime(path.rsplit("/", 1)[1])
                if self.fail:
                    measured["last_request"] = {
                        **cast(dict[str, object], measured["last_request"]),
                        "request_id": RID,
                    }
                return {"manifest_sha256": manifest["manifest_sha256"], "runtime": measured}

            def request(
                self, method: str, path: str, *, body: bytes, headers: dict[str, str]
            ) -> tuple[object, object]:
                del method, headers
                self.count += 1
                self.cases.append((path, cast(object, json.loads(body))))
                response = ResponseFixture(f"api-{self.count:032x}")
                return response, response

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("simo.breeze_benchmark.BenchmarkConnection", ClientFixture),
        ):
            root = Path(directory)
            result = run_https_benchmark(
                config, url="https://simo.local:8444", limit=1, audio_dir=root / "success"
            )
            self.assertTrue(result["completed"])
            self.assertEqual(len(cast(list[object], result["samples"])), 3)
            self.assertEqual(
                [case[1] for case in ClientFixture.cases],
                [{"seed": 17, "instruction_id": "default"}] * 4
                + [
                    {"seed": 29, "instruction_id": "default"},
                    {"seed": 42, "instruction_id": "default"},
                ],
            )
            self.assertEqual(len(list((root / "success").glob("*.wav"))), 3)
            self.assertTrue((root / "success/report.json").exists())
            with self.assertRaises(FileExistsError):
                run_https_benchmark(
                    config, url="https://simo.local:8444", limit=1, audio_dir=root / "success"
                )
            ClientFixture.fail = True
            failed = run_https_benchmark(
                config, url="https://simo.local:8444", warmups=0, limit=1, audio_dir=root / "failed"
            )
            self.assertFalse(failed["completed"])
            self.assertIn("failure", failed)
            self.assertEqual(list((root / "failed").glob("*.wav")), [])
            self.assertEqual((root / "failed/failed-partial.pcm").read_bytes(), PCM)

    def test_metrics_reject_false_completion_and_bad_sample_counts(self) -> None:
        for key, value in (
            ("completed", 1),
            ("eos_reached", False),
            ("cancelled", True),
            ("audio_samples", 0),
            ("audio_samples", 3841),
            ("codec_frames", True),
            ("audio_s", 0.15),
        ):
            measured = runtime()
            measured["last_request"] = {
                **cast(dict[str, object], measured["last_request"]),
                key: value,
            }
            with self.assertRaises((ValueError, TypeError)):
                _completed_metrics(measured, FP, RID)

    def test_tls_origin_and_destination_are_checked_before_connection(self) -> None:
        for url in (
            "http://simo.local",
            "https://user@host",
            "https://host/path",
            "https://host?x=1",
            "https://host#x",
        ):
            with self.assertRaises(ValueError):
                BenchmarkConnection(url, None, None)
        with (
            patch(
                "simo.breeze_benchmark.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("8.8.8.8", 443))],
            ),
            patch(
                "simo.breeze_benchmark.socket.create_connection",
                side_effect=AssertionError("connected"),
            ),
        ):
            with self.assertRaises(ValueError):
                BenchmarkConnection("https://simo.local", None, None).request(
                    "GET", "/api/benchmarks"
                )

    def test_cli_requires_evidence_directory_and_returns_failure_status(self) -> None:
        with patch(
            "simo.breeze_benchmark.run_https_benchmark", return_value={"completed": False}
        ) as run:
            self.assertEqual(
                main(
                    [
                        "breeze",
                        "benchmark",
                        "--url",
                        "https://simo.local:8444",
                        "--audio-dir",
                        "/private/tmp/unused-test-evidence",
                        "--json",
                    ]
                ),
                1,
            )
            self.assertEqual(run.call_count, 1)
            self.assertEqual(main(["breeze", "benchmark", "--url", "https://simo.local:8444"]), 2)
