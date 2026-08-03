from __future__ import annotations

import unittest
from pathlib import Path

from simo.config import (
    PARAKEET_STT_MODEL,
    PARAKEET_STT_REVISION,
    QWEN_TEXT_MODEL,
    QWEN_TEXT_REVISION,
    QWEN_TTS_MODEL,
    QWEN_TTS_REVISION,
    RunMode,
    RuntimeConfig,
)


class RuntimeConfigTests(unittest.TestCase):
    def test_defaults_are_mac_native_selected_models(self) -> None:
        config = RuntimeConfig.from_environment({})
        self.assertEqual(RunMode.HEADLESS, config.mode)
        self.assertEqual(QWEN_TTS_MODEL, config.tts.model_id)
        self.assertEqual(QWEN_TTS_REVISION, config.tts.revision)
        self.assertEqual(PARAKEET_STT_MODEL, config.stt.model_id)
        self.assertEqual(PARAKEET_STT_REVISION, config.stt.revision)
        self.assertEqual(QWEN_TEXT_MODEL, config.text.model_id)
        self.assertEqual(QWEN_TEXT_REVISION, config.text.revision)
        self.assertEqual(config.repository / ".models", config.models_dir)
        self.assertEqual(8_000, config.context_max_chars)
        self.assertEqual(1_000, config.context_max_age_ms)
        self.assertEqual(48, config.text_max_tokens)
        self.assertIsNone(config.audio_input_device_index)
        self.assertIsNone(config.audio_output_device_index)
        self.assertEqual(0.1, config.vad_confidence)
        self.assertEqual(0.02, config.vad_start_rms)
        self.assertEqual(32, config.vad_start_ms)
        self.assertEqual(320, config.vad_stop_ms)
        self.assertEqual(200, config.vad_pre_roll_ms)
        self.assertEqual(30.0, config.max_utterance_s)
        self.assertEqual("Aiden", config.tts_voice)
        self.assertEqual(0.24, config.tts_streaming_interval_s)

    def test_environment_overrides_are_typed_once(self) -> None:
        config = RuntimeConfig.from_environment(
            {
                "SIMO_MODE": "live",
                "SIMO_MODELS_DIR": "/tmp/simo-test-models",
                "SIMO_CORE_LIBRARY": "/tmp/libsimo-test.dylib",
                "SIMO_QUEUE_CAPACITY": "12",
                "SIMO_MAX_SEGMENTS": "7",
                "SIMO_CONTEXT_MAX_CHARS": "500",
                "SIMO_CONTEXT_MAX_AGE_MS": "250",
                "SIMO_TEXT_MAX_TOKENS": "32",
                "SIMO_TTS_MODEL": "example/tts",
                "SIMO_TTS_REVISION": "revision-1",
                "SIMO_TTS_VOICE": "Ryan",
                "SIMO_TTS_STREAMING_INTERVAL_S": "0.5",
                "SIMO_AUDIO_INPUT_DEVICE_INDEX": "0",
                "SIMO_AUDIO_OUTPUT_DEVICE_INDEX": "3",
                "SIMO_VAD_CONFIDENCE": "0.4",
                "SIMO_VAD_START_RMS": "0.04",
                "SIMO_VAD_START_MS": "80",
                "SIMO_VAD_STOP_MS": "600",
                "SIMO_VAD_PRE_ROLL_MS": "250",
                "SIMO_MAX_UTTERANCE_S": "20",
            }
        )
        self.assertEqual(RunMode.LIVE, config.mode)
        self.assertEqual(12, config.queue_capacity)
        self.assertEqual(7, config.max_segments)
        self.assertEqual(500, config.context_max_chars)
        self.assertEqual(250, config.context_max_age_ms)
        self.assertEqual(32, config.text_max_tokens)
        self.assertEqual(Path("/tmp/libsimo-test.dylib"), config.core_library)
        self.assertEqual(Path("/tmp/simo-test-models/tts"), config.tts.local_path)
        self.assertEqual("revision-1", config.tts.revision)
        self.assertEqual("Ryan", config.tts_voice)
        self.assertEqual(0.5, config.tts_streaming_interval_s)
        self.assertEqual(0, config.audio_input_device_index)
        self.assertEqual(3, config.audio_output_device_index)
        self.assertEqual(0.4, config.vad_confidence)
        self.assertEqual(0.04, config.vad_start_rms)
        self.assertEqual(80, config.vad_start_ms)
        self.assertEqual(600, config.vad_stop_ms)
        self.assertEqual(250, config.vad_pre_roll_ms)
        self.assertEqual(20.0, config.max_utterance_s)

    def test_invalid_capacity_fails_before_runtime_start(self) -> None:
        for value in ("0", "-1", "many"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    RuntimeConfig.from_environment({"SIMO_QUEUE_CAPACITY": value})

    def test_invalid_tts_settings_fail_before_runtime_start(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            RuntimeConfig.from_environment({"SIMO_TTS_VOICE": "  "})
        for value in ("0", "-0.1", "soon"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive number"):
                    RuntimeConfig.from_environment({"SIMO_TTS_STREAMING_INTERVAL_S": value})
        with self.assertRaisesRegex(ValueError, "must not exceed 1"):
            RuntimeConfig.from_environment({"SIMO_VAD_START_RMS": "1.1"})
        with self.assertRaisesRegex(ValueError, "must not exceed 1"):
            RuntimeConfig.from_environment({"SIMO_VAD_CONFIDENCE": "1.1"})
        for value in ("-1", "device"):
            with self.subTest(device=value):
                with self.assertRaisesRegex(ValueError, "non-negative integer"):
                    RuntimeConfig.from_environment({"SIMO_AUDIO_INPUT_DEVICE_INDEX": value})


if __name__ == "__main__":
    unittest.main()
