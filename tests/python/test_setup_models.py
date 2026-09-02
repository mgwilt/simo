from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from simo.config import RunMode, RuntimeConfig

from scripts.setup_models import (
    download_models,
    marker_is_current,
    model_plans,
    plan_payload,
)


class ModelSetupTests(unittest.TestCase):
    def config(self, directory: str) -> RuntimeConfig:
        return RuntimeConfig.from_environment(
            {"SIMO_MODELS_DIR": directory},
            mode=RunMode.LIVE,
        )

    def test_default_plan_is_pinned_and_requires_extra_free_space(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(directory)
            payload = plan_payload(config, model_plans(config))

        self.assertEqual(13_270_174_788, payload["expected_bytes"])
        self.assertGreater(payload["required_free_bytes"], payload["expected_bytes"])
        self.assertEqual("--accept-download", payload["requires_explicit_flag"])
        self.assertTrue(all(len(model["revision"]) == 40 for model in payload["models"]))

    def test_fake_download_verifies_files_writes_marker_and_is_idempotent(self) -> None:
        calls: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(directory)
            plans = model_plans(config)

            def download(**kwargs: object) -> str:
                calls.append((str(kwargs["repo_id"]), str(kwargs["revision"])))
                target = Path(str(kwargs["local_dir"]))
                selected = next(plan.config for plan in plans if plan.config.local_path == target)
                for relative in selected.required_paths:
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"fixture")
                return str(target)

            with redirect_stdout(io.StringIO()):
                download_models(plans, downloader=download)
                download_models(plans, downloader=download)

            self.assertEqual(3, len(calls))
            self.assertTrue(all(marker_is_current(plan.config) for plan in plans))
            marker = json.loads((plans[0].config.local_path / ".simo-model.json").read_text())
            self.assertEqual(plans[0].config.revision, marker["revision"])


if __name__ == "__main__":
    unittest.main()
