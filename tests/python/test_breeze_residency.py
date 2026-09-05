from __future__ import annotations

import io
import json
import runpy
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from simo.config import ModelConfig


class BreezeResidencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "scripts/hold_breeze_resident_models.py")
        )

    def test_materialization_precedes_counting_and_deduplicates(self) -> None:
        calls: list[tuple[str, object]] = []
        array = SimpleNamespace(nbytes=64)
        parameters = object()
        model = SimpleNamespace(parameters=lambda: parameters)

        def evaluate(value: object) -> None:
            calls.append(("eval", value))

        def flatten(value: object) -> list[tuple[str, SimpleNamespace]]:
            return [("a", array), ("tied", array)]

        def empty(value: object) -> list[tuple[str, SimpleNamespace]]:
            return []

        mx = SimpleNamespace(
            eval=evaluate,
            synchronize=lambda: calls.append(("sync", None)),
        )
        tree = SimpleNamespace(tree_flatten=flatten)
        materialize = cast(Callable[..., dict[str, int]], self.script["materialize"])
        self.assertEqual(materialize(model, mx, tree), {"unique_arrays": 1, "parameter_bytes": 64})
        self.assertEqual(calls, [("eval", parameters), ("sync", None)])
        tree.tree_flatten = empty
        with self.assertRaisesRegex(ValueError, "nonempty"):
            materialize(model, mx, tree)

    def test_marker_mismatch_is_not_residency_proof(self) -> None:
        identity = cast(Callable[[ModelConfig], dict[str, object]], self.script["model_identity"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = ModelConfig("test/model", "revision", root, ())
            marker = root / ".simo-model.json"
            marker.write_text(json.dumps({"model_id": "test/model", "revision": "revision"}))
            self.assertFalse(identity(config)["weight_digest_verified"])
            marker.write_text('{"model_id":"wrong","revision":"revision"}')
            with self.assertRaisesRegex(ValueError, "marker"):
                identity(config)

    def test_live_status_and_exit_eof_protocol(self) -> None:
        command_loop = cast(Callable[..., None], self.script["command_loop"])
        events: list[str] = []
        command_loop(io.StringIO("status\ninvalid\nexit\nstatus\n"), events.append)
        self.assertEqual(events, ["status", "invalid_command", "stopped"])
        events.clear()
        command_loop(io.StringIO("status\n"), events.append)
        self.assertEqual(events, ["status", "eof"])


if __name__ == "__main__":
    unittest.main()
