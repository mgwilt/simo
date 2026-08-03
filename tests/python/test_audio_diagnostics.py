from __future__ import annotations

import unittest

from simo.audio_diagnostics import (
    calibration_result,
    collect_interactive_levels,
    summarize_levels,
)


class AudioDiagnosticsTests(unittest.TestCase):
    def test_calibration_recommends_threshold_between_ambient_and_speech(self) -> None:
        result = calibration_result(
            [0.009, 0.01, 0.011, 0.01],
            [0.04, 0.05, 0.06, 0.05],
            configured_start_rms=0.02,
        )

        self.assertTrue(result["ready"])
        recommendation = result["recommended_start_rms"]
        self.assertGreater(recommendation, result["ambient"]["peak_rms"])
        self.assertLess(recommendation, result["speech"]["p95_rms"])
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

    def test_calibration_accepts_speech_modulation_above_a_high_noise_floor(
        self,
    ) -> None:
        result = calibration_result(
            [0.0118, 0.0121, 0.0127, 0.0131],
            [0.0127, 0.0130, 0.0159, 0.0176],
            configured_start_rms=0.02,
        )

        self.assertTrue(result["ready"])
        self.assertGreater(result["recommended_start_rms"], 0.0131)
        self.assertLess(result["recommended_start_rms"], 0.0176)

    def test_level_summary_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            summarize_levels([])

    def test_interactive_calibration_cues_and_detects_speech_onset(self) -> None:
        values = iter([0.01] * 4 + [0.011, 0.012] + [0.03, 0.04, 0.05] + [0.05, 0.04])
        cues: list[str] = []

        ambient, speech, trigger = collect_interactive_levels(
            lambda: next(values),
            cues.append,  # type: ignore[arg-type]
            ambient_blocks=4,
            speech_blocks=5,
            onset_timeout_blocks=8,
        )

        self.assertEqual([0.01] * 4, ambient)
        self.assertEqual([0.03, 0.04, 0.05, 0.05, 0.04], speech)
        self.assertEqual(["start", "finish"], cues)
        self.assertGreater(trigger, 0.01)

    def test_interactive_calibration_fails_when_no_onset_arrives(self) -> None:
        values = iter([0.01] * 8)
        cues: list[str] = []

        with self.assertRaisesRegex(RuntimeError, "no speech onset"):
            collect_interactive_levels(
                lambda: next(values),
                cues.append,  # type: ignore[arg-type]
                ambient_blocks=4,
                speech_blocks=3,
                onset_timeout_blocks=4,
            )

        self.assertEqual(["start", "failed"], cues)


if __name__ == "__main__":
    unittest.main()
