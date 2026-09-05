"""Screen retained Breeze WAVs with existing local ASR; no perceptual claims."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import wave
from contextlib import redirect_stdout
from pathlib import Path
from typing import cast

from simo.breeze import BENCHMARK_PROMPTS, LONG_BENCHMARK_PROMPTS, benchmark
from simo.config import RuntimeConfig
from simo.inference import MLXTextGenerator, ParakeetMLXRecognizer
from simo.model_proof import resample_pcm_s16le


def word_errors(expected: str, actual: str) -> tuple[int, int]:
    left = cast(list[str], re.findall(r"[a-z0-9]+", expected.lower()))
    right = cast(list[str], re.findall(r"[a-z0-9]+", actual.lower()))
    previous = list(range(len(right) + 1))
    for row, word in enumerate(left, 1):
        current = [row]
        for column, heard in enumerate(right, 1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (word != heard))
            )
        previous = current
    return previous[-1], len(left)


async def evaluate(
    paths: list[Path], resident_screen: bool, long_audio_dir: Path | None
) -> dict[str, object]:
    config = RuntimeConfig.from_environment()
    recognizer = ParakeetMLXRecognizer(config.stt.local_path)
    reports: list[dict[str, object]] = []
    for path in paths:
        payload = cast(dict[str, object], json.loads(path.read_text()))
        rows: list[dict[str, object]] = []
        total_errors = total_words = 0
        samples = cast(list[dict[str, object]], payload["samples"])
        artifacts = cast(list[dict[str, object]], payload["audio_artifacts"])
        for sample, artifact in zip(samples, artifacts, strict=True):
            with wave.open(str(artifact["path"]), "rb") as audio:
                if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                    raise ValueError("Expected mono PCM16 WAV")
                pcm, rate = audio.readframes(audio.getnframes()), audio.getframerate()
            if hashlib.sha256(pcm).hexdigest() != artifact["pcm_sha256"]:
                raise ValueError("Listening artifact changed since benchmark")
            transcript = await recognizer.transcribe(resample_pcm_s16le(pcm, rate, 16000), 16000)
            errors, words = word_errors(str(sample["prompt"]), transcript)
            total_errors += errors
            total_words += words
            rows.append(
                {
                    "prompt": sample["prompt"],
                    "seed": sample["seed"],
                    "transcript": transcript,
                    "word_errors": errors,
                    "reference_words": words,
                    "wer": errors / max(1, words),
                }
            )
        reports.append(
            {
                "benchmark": str(path),
                "samples": rows,
                "wer": total_errors / max(1, total_words),
            }
        )
    resident: dict[str, object] | None = None
    if resident_screen:
        # Hold both existing Simo models in this process; no identity or model changes.
        llm = MLXTextGenerator(config.text.local_path)
        await llm.generate("Reply with one word: ready.", max_tokens=1)
        resident = {
            "stt": config.stt.model_id,
            "llm": config.text.model_id,
            "short": await benchmark(config, warmups=1, prompts=BENCHMARK_PROMPTS[:3], seeds=(42,)),
            "long": await benchmark(
                config,
                warmups=0,
                prompts=LONG_BENCHMARK_PROMPTS,
                seeds=(42,),
                audio_dir=long_audio_dir,
            ),
        }
    return {
        "schema_version": 1,
        "asr_model": config.stt.model_id,
        "asr_revision": config.stt.revision,
        "reports": reports,
        "resident_screen": resident,
        "quality_acceptance": False,
        "limits": "ASR is a defect screen, not matched listening or instruction/perceptual acceptance. Resident screen is bounded, not the full release suite.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmarks", type=Path, nargs="+")
    parser.add_argument("--resident-screen", action="store_true")
    parser.add_argument("--long-audio-dir", type=Path)
    args = parser.parse_args()
    with redirect_stdout(sys.stderr):
        result = asyncio.run(
            evaluate(
                cast(list[Path], args.benchmarks),
                cast(bool, args.resident_screen),
                cast(Path | None, args.long_audio_dir),
            )
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
