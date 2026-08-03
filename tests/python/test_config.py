from __future__ import annotations

import unittest
from pathlib import Path

from simo.config import (
    PARAKEET_STT_MODEL,
    QWEN_TEXT_MODEL,
    QWEN_TTS_MODEL,
    RunMode,
    RuntimeConfig,
)


class RuntimeConfigTests(unittest.TestCase):
    def test_defaults_are_mac_native_selected_models(self) -> None:
        config = RuntimeConfig.from_environment({})
        self.assertEqual(RunMode.HEADLESS, config.mode)
        self.assertEqual(QWEN_TTS_MODEL, config.tts.model_id)
        self.assertEqual(PARAKEET_STT_MODEL, config.stt.model_id)
        self.assertEqual(QWEN_TEXT_MODEL, config.text.model_id)
        self.assertEqual(config.repository / ".models", config.models_dir)

    def test_environment_overrides_are_typed_once(self) -> None:
        config = RuntimeConfig.from_environment(
            {
                "SIMO_MODE": "live",
                "SIMO_MODELS_DIR": "/tmp/simo-test-models",
                "SIMO_CORE_LIBRARY": "/tmp/libsimo-test.dylib",
                "SIMO_QUEUE_CAPACITY": "12",
                "SIMO_MAX_SEGMENTS": "7",
                "SIMO_TTS_MODEL": "example/tts",
            }
        )
        self.assertEqual(RunMode.LIVE, config.mode)
        self.assertEqual(12, config.queue_capacity)
        self.assertEqual(7, config.max_segments)
        self.assertEqual(Path("/tmp/libsimo-test.dylib"), config.core_library)
        self.assertEqual(Path("/tmp/simo-test-models/tts"), config.tts.local_path)

    def test_invalid_capacity_fails_before_runtime_start(self) -> None:
        for value in ("0", "-1", "many"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    RuntimeConfig.from_environment({"SIMO_QUEUE_CAPACITY": value})


if __name__ == "__main__":
    unittest.main()
