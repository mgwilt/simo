from __future__ import annotations

import argparse
import json
import runpy
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import patch


class BreezeIdentityTests(unittest.TestCase):
    def test_operator_defaults_and_experiment_conflicts_reject_before_model_load(self) -> None:
        service = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "services/breeze/serve.py")
        )
        parser = cast(Callable[[], argparse.ArgumentParser], service["build_parser"])()
        defaults = cast(dict[str, object], vars(parser.parse_args(["unused-model"])))
        self.assertEqual(defaults["performance_mode"], "quality")
        self.assertIsNone(defaults["experimental_recipe"])
        run = cast(Callable[[], int], service["main"])
        cases = [
            (["--performance-mode", "fast"], "Fast has no released recipe"),
            *[
                (
                    ["--experimental-recipe", "mlx-int8-v1", "--port", "7861", *conflict],
                    "separate loopback port",
                )
                for conflict in (
                    ["--port", "7860"],
                    ["--host", "0.0.0.0"],  # noqa: S104 - rejected input, no binding
                    ["--device", "cpu"],
                    ["--engine", "reference"],
                    ["--attention", "sdpa"],
                    ["--depth-cache", "compiled"],
                    ["--quantization", "int8"],
                )
            ],
        ]
        for flags, message in cases:
            with (
                self.subTest(flags=flags),
                patch("sys.argv", ["serve.py", "unused-model", *flags]),
                self.assertRaisesRegex(RuntimeError, message),
            ):
                run()

    def test_fingerprint_covers_model_source_and_effective_settings(self) -> None:
        service = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "services/breeze/serve.py")
        )
        identity = cast(
            Callable[[Path, argparse.Namespace], dict[str, object]], service["runtime_identity"]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model"
            model.mkdir()
            marker = model / ".simo-model.json"
            marker.write_text(
                json.dumps(
                    {
                        "model_id": "BreezeBlue/Breeze-TTS-2",
                        "revision": service["BREEZE_MODEL_REVISION"],
                    }
                )
            )
            weight = model / "model.safetensors"
            weight.write_bytes(b"original weights")
            (root / "models").mkdir()
            source = root / "models/runtime.py"
            source.write_text("original source")
            args = argparse.Namespace(
                model=model,
                device="mps",
                engine="streaming",
                attention="eager",
                quantization="none",
                depth_cache="dynamic",
                performance_mode="quality",
            )
            with (
                patch("subprocess.check_output", return_value="revision\n"),
                patch("platform.platform", return_value="test-platform"),
                patch("importlib.metadata.version", return_value="locked"),
            ):
                first = identity(root, args)["runtime_fingerprint"]
                weight.write_bytes(b"changed weights")
                second = identity(root, args)["runtime_fingerprint"]
                source.write_text("changed source")
                third = identity(root, args)["runtime_fingerprint"]
                args.attention = "sdpa"
                fourth = identity(root, args)["runtime_fingerprint"]
                self.assertEqual(len({first, second, third, fourth}), 4)
                marker.write_text('{"model_id": "wrong"}')
                with self.assertRaisesRegex(RuntimeError, "pinned"):
                    identity(root, args)
                marker.unlink()
                with self.assertRaises(FileNotFoundError):
                    identity(root, args)


if __name__ == "__main__":
    unittest.main()
