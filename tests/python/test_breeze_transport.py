from __future__ import annotations

import asyncio
import http.client
import socket
import threading
import unittest
from unittest.mock import patch

from simo.inference import BreezeHTTPSynthesizer


class SocketConnection:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock

    def connect(self) -> None:
        pass

    def request(self, *args: object, **kwargs: object) -> None:
        pass

    def getresponse(self) -> http.client.HTTPResponse:
        response = http.client.HTTPResponse(self.sock)
        response.begin()
        return response

    def close(self) -> None:
        self.sock.close()


class BreezeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_id_is_validated_exposed_and_reset_before_reuse(self) -> None:
        identifiers = iter(("api-" + "a" * 32, "", "api-invalid"))

        def connect(*args: object, **kwargs: object) -> SocketConnection:
            del args, kwargs
            client, server = socket.socketpair()
            identity = next(identifiers)
            server.sendall(
                (
                    "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nX-Sample-Rate: 24000\r\n"
                    f"X-Sample-Format: s16le\r\nX-Breeze-Request-ID: {identity}\r\n\r\n"
                ).encode()
                + b"\x01\x00"
            )
            server.close()
            return SocketConnection(client)

        with patch("simo.inference.http.client.HTTPConnection", side_effect=connect):
            synth = BreezeHTTPSynthesizer(
                "http://127.0.0.1:7861/v1/audio/speech",
                instruction="Clear",
                require_request_id=True,
            )
            first = [chunk async for chunk in synth.synthesize("one")]
            self.assertEqual(first[0].pcm_s16le, b"\x01\x00")
            self.assertEqual(synth.response_request_id, "api-" + "a" * 32)
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, "invalid request ID"):
                    _ = [chunk async for chunk in synth.synthesize("two")]
                self.assertIsNone(synth.response_request_id)

    async def test_first_pcm_does_not_wait_for_next_chunk_and_cancel_closes_worker(self) -> None:
        client, server = socket.socketpair()
        release = threading.Event()
        finished = threading.Event()

        def serve() -> None:
            try:
                server.sendall(
                    b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nX-Sample-Rate: 24000\r\nX-Sample-Format: s16le\r\n\r\n"
                )
                server.sendall(b"4\r\n\x01\x00\x02\x00\r\n")
                release.wait(5)
                server.sendall(b"0\r\n\r\n")
            except OSError:
                pass  # Client cancellation closes the peer socket.
            finally:
                server.close()
                finished.set()

        worker = threading.Thread(target=serve)
        worker.start()
        try:
            with patch(
                "simo.inference.http.client.HTTPConnection", return_value=SocketConnection(client)
            ):
                synth = BreezeHTTPSynthesizer(
                    "http://127.0.0.1:7860/v1/audio/speech", instruction="Clear", read_bytes=48000
                )
                stream = synth.synthesize("Hello")
                first = await asyncio.wait_for(anext(stream), 1)
                self.assertEqual(b"\x01\x00\x02\x00", first.pcm_s16le)
                self.assertFalse(release.is_set())
                await asyncio.wait_for(stream.aclose(), 1)
                self.assertEqual(-1, client.fileno())
        finally:
            release.set()
            client.close()
            await asyncio.to_thread(worker.join, 2)
        self.assertTrue(finished.is_set())
