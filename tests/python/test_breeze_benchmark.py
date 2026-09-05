from __future__ import annotations

import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from simo.breeze import _percentile, benchmark
from simo.config import RuntimeConfig
from simo.inference import AudioChunk


class BenchmarkTests(unittest.IsolatedAsyncioTestCase):
    async def test_matched_seeds_warmups_and_listening_artifacts(self) -> None:
        class Synth:
            seeds: ClassVar[list[int]] = []
            calls = 0

            def __init__(self, *args: object, **kwargs: object) -> None:
                self.seeds.append(int(str(kwargs["seed"])))

            async def synthesize(self, text: str) -> AsyncIterator[AudioChunk]:
                self.__class__.calls += 1
                yield AudioChunk(b"\x00\x00" * 1920, 24000)
                yield AudioChunk(b"\x01\x00" * 1920, 24000)

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("simo.breeze.BreezeHTTPSynthesizer", Synth),
                patch(
                    "simo.breeze.health",
                    return_value={"status": "ready", "runtime_fingerprint": "test"},
                ),
            ):
                result = await benchmark(
                    RuntimeConfig.from_environment({}),
                    warmups=3,
                    prompts=("x",),
                    seeds=(17, 29, 42),
                    audio_dir=Path(directory),
                )
            self.assertEqual(Synth.calls, 6)
            self.assertEqual(len(list(Path(directory).glob("*.wav"))), 3)
            self.assertEqual(
                result["release_gate"],
                {
                    "browser_playback": "not_measured",
                    "underruns": "not_measured",
                    "listening": "not_measured",
                    "accepted": False,
                },
            )

    def test_nearest_rank_p95_is_not_always_maximum(self) -> None:
        self.assertEqual(_percentile(list(range(1, 101)), 0.95), 95)
