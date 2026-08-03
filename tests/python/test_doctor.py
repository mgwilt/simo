from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from simo.config import RunMode, RuntimeConfig
from simo.doctor import inspect_runtime


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
        self.assertEqual(["platform", "architecture", "native core"], [
            check.name for check in report.checks
        ])

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
        self.assertEqual(11, len(report.checks))
        self.assertEqual(
            8,
            sum(not check.ok for check in report.checks),
        )
        self.assertEqual("live", report.as_dict()["mode"])


if __name__ == "__main__":
    unittest.main()
