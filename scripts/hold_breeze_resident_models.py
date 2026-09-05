"""Hold Simo's evaluated STT/LLM weights for an isolated Breeze residency benchmark.

Run in Simo's existing environment, not the separate Breeze overlay. Newline
commands are ``status`` and ``exit``; EOF also exits. An exclusive JSONL report
records materialized parameters and live memory snapshots. This proves idle
weight retention, not concurrent model inference or OS page-pinning.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import time
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path
from typing import Protocol, TextIO, cast

from simo.config import ModelConfig, RuntimeConfig
from simo.inference import MLXTextGenerator, ParakeetMLXRecognizer


class Parameter(Protocol):
    @property
    def nbytes(self) -> int: ...


class Model(Protocol):
    def parameters(self) -> object: ...


class Mlx(Protocol):
    def eval(self, parameters: object) -> None: ...
    def synchronize(self) -> None: ...
    def get_active_memory(self) -> int: ...
    def get_cache_memory(self) -> int: ...


class Tree(Protocol):
    def tree_flatten(self, tree: object) -> list[tuple[str, Parameter]]: ...


def model_identity(config: ModelConfig) -> dict[str, object]:
    marker_path = config.local_path / ".simo-model.json"
    content = marker_path.read_bytes()
    marker = cast(dict[str, object], json.loads(content))
    if marker.get("model_id") != config.model_id or marker.get("revision") != config.revision:
        raise ValueError("Local model marker does not match effective Simo configuration")
    return {
        "model_id": config.model_id,
        "revision": config.revision,
        "local_path": str(config.local_path.resolve()),
        "marker_sha256": hashlib.sha256(content).hexdigest(),
        "weight_digest_verified": False,
    }


def materialize(model: Model, mx: Mlx, tree: Tree) -> dict[str, int]:
    parameters = model.parameters()
    mx.eval(parameters)
    mx.synchronize()
    # Count unique array objects, not repeated paths to a tied parameter.
    arrays = {id(value): value for _, value in tree.tree_flatten(parameters)}
    size = sum(value.nbytes for value in arrays.values())
    if not arrays or size <= 0:
        raise ValueError("Resident model must contain evaluated nonempty parameters")
    return {"unique_arrays": len(arrays), "parameter_bytes": size}


async def load_models(mx: Mlx, tree: Tree) -> tuple[tuple[Model, ...], list[dict[str, object]]]:
    config = RuntimeConfig.from_environment()
    identities = [model_identity(item) for item in (config.stt, config.text)]
    recognizer = ParakeetMLXRecognizer(config.stt.local_path)
    stt = cast(Model, recognizer._load_model())  # noqa: SLF001 - diagnostic materialization
    identities[0].update(materialize(stt, mx, tree))
    generator = MLXTextGenerator(config.text.local_path)
    await generator.generate("Reply with one word: ready.", max_tokens=1)
    loaded = cast(tuple[Model, object] | None, generator._loaded)  # noqa: SLF001
    if loaded is None:
        raise RuntimeError("Simo text model was not loaded")
    text = loaded[0]
    identities[1].update(materialize(text, mx, tree))
    return (stt, text), identities


def command_loop(commands: TextIO, emit: Callable[[str], None]) -> None:
    for line in commands:
        command = line.strip()
        if command == "exit":
            emit("stopped")
            return
        emit("status" if command == "status" else "invalid_command")
    emit("eof")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="New JSONL evidence path")
    args = parser.parse_args()
    report_path = cast(Path, args.report)
    # Exclusive creation precedes loading, so a typo cannot overwrite prior proof.
    with report_path.open("x") as report:
        mx = cast(Mlx, importlib.import_module("mlx.core"))
        tree = cast(Tree, importlib.import_module("mlx.utils"))
        started = time.time_ns()
        source_paths = [
            Path(__file__),
            Path(importlib.import_module("simo.inference").__file__ or ""),
            Path(importlib.import_module("simo.config").__file__ or ""),
        ]
        sources = {
            str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_paths
        }
        with redirect_stdout(sys.stderr):
            models, identities = asyncio.run(load_models(mx, tree))

        def emit(event: str) -> None:
            # Strong references survive through every status and the final event.
            if len(models) != 2:
                raise RuntimeError("Expected both existing Simo models")
            mx.synchronize()
            record = {
                "schema_version": 1,
                "event": event,
                "pid": os.getpid(),
                "started_unix_ns": started,
                "unix_ns": time.time_ns(),
                "monotonic_ns": time.perf_counter_ns(),
                "models": identities,
                "active_memory_bytes": mx.get_active_memory(),
                "cache_memory_bytes": mx.get_cache_memory(),
                "dependencies": {
                    name: importlib.metadata.version(name)
                    for name in ("mlx", "mlx-metal", "mlx-lm", "parakeet-mlx", "transformers")
                },
                "sources": sources,
                "limits": "Evaluated idle weights held in this process; no concurrent STT/LLM inference or OS page-pinning assertion. Markers verified, full weights not rehashed.",
            }
            content = json.dumps(record, sort_keys=True)
            report.write(content + "\n")
            report.flush()
            print(content, flush=True)

        emit("ready")
        command_loop(sys.stdin, emit)


if __name__ == "__main__":
    main()
