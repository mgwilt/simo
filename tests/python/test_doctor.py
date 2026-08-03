from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from simo.config import RunMode, RuntimeConfig
from simo.doctor import _local_audio_device_check, _model_check, inspect_runtime


class DoctorTests(unittest.TestCase):
    def test_headless_requires_native_core_but_not_model_weights(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "libsimo_core.dylib"
            library.touch()
            config = RuntimeConfig.from_environment(
                {"SIMO_CORE_LIBRARY": str(library)}, mode=RunMode.HEADLESS
            )
            report = inspect_runtime(config)

        self.assertTrue(report.ready)
        self.assertEqual(
            ["platform", "architecture", "native core"],
            [check.name for check in report.checks],
        )

    def test_live_reports_each_missing_runtime_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "libsimo_core.dylib"
            library.touch()
            config = RuntimeConfig.from_environment(
                {
                    "SIMO_CORE_LIBRARY": str(library),
                    "SIMO_MODELS_DIR": str(Path(directory) / "models"),
                },
                mode=RunMode.LIVE,
            )
            with patch("simo.doctor.importlib.util.find_spec", return_value=None):
                report = inspect_runtime(config)

        self.assertFalse(report.ready)
        self.assertEqual(13, len(report.checks))
        self.assertEqual(
            10,
            sum(not check.ok for check in report.checks),
        )
        self.assertEqual("live", report.as_dict()["mode"])

    def test_audio_check_uses_configured_device_indices(self) -> None:
        config = RuntimeConfig.from_environment(
            {
                "SIMO_AUDIO_INPUT_DEVICE_INDEX": "2",
                "SIMO_AUDIO_OUTPUT_DEVICE_INDEX": "4",
            },
            mode=RunMode.LIVE,
        )
        completed = SimpleNamespace(
            returncode=0,
            stdout='{"input":"Mic","output":"Speaker"}\n',
            stderr="",
        )
        with patch("simo.doctor.subprocess.run", return_value=completed) as run:
            check = _local_audio_device_check(config)

        self.assertTrue(check.ok)
        self.assertEqual("input=Mic; output=Speaker", check.detail)
        self.assertEqual(["2", "4"], run.call_args.args[0][-2:])

    def test_model_check_requires_files_and_matching_revision_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = RuntimeConfig.from_environment({"SIMO_MODELS_DIR": directory})
            for relative in config.tts.required_paths:
                path = config.tts.local_path / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

            unverified = _model_check("TTS model", config.tts)
            self.assertFalse(unverified.ok)
            self.assertIn("unverified", unverified.detail)

            marker = config.tts.local_path / ".simo-model.json"
            marker.write_text(
                json.dumps({"model_id": config.tts.model_id, "revision": "wrong"})
            )
            mismatch = _model_check("TTS model", config.tts)
            self.assertFalse(mismatch.ok)
            self.assertIn("does not match", mismatch.detail)

            marker.write_text(
                json.dumps(
                    {
                        "model_id": config.tts.model_id,
                        "revision": config.tts.revision,
                    }
                )
            )
            self.assertTrue(_model_check("TTS model", config.tts).ok)


if __name__ == "__main__":
    unittest.main()
