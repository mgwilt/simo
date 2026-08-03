from __future__ import annotations

import unittest

from simo.audio_diagnostics import calibration_result, summarize_levels


class AudioDiagnosticsTests(unittest.TestCase):
    def test_calibration_recommends_threshold_between_ambient_and_speech(self) -> None:
        result = calibration_result(
            [0.009, 0.01, 0.011, 0.01],
            [0.04, 0.05, 0.06, 0.05],
            configured_start_rms=0.02,
        )

        self.assertTrue(result["ready"])
        recommendation = result["recommended_start_rms"]
        self.assertGreater(recommendation, result["ambient"]["p95_rms"])
        self.assertLess(recommendation, result["speech"]["median_rms"])
        self.assertEqual(
            f"SIMO_VAD_START_RMS={recommendation}",
            result["environment"],
        )

    def test_calibration_fails_closed_without_speech_separation(self) -> None:
        result = calibration_result(
            [0.01, 0.011, 0.012],
            [0.011, 0.012, 0.013],
            configured_start_rms=0.02,
        )

        self.assertFalse(result["ready"])
        self.assertIsNone(result["recommended_start_rms"])
        self.assertIsNone(result["environment"])

    def test_level_summary_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            summarize_levels([])


if __name__ == "__main__":
    unittest.main()
