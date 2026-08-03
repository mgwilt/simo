from __future__ import annotations

import asyncio
import io
import json
import unittest
from array import array
from contextlib import redirect_stdout
from typing import cast
from unittest.mock import AsyncMock, patch

from simo.cli import main
from simo.livekit_probe import (
    TwoProcessWebRTCProbe,
    WebRTCParticipantProbe,
    _synthetic_speech_shaped_pcm,
    run_two_process_probe,
)


def participant(role: str, process_id: int, local_sid: str) -> WebRTCParticipantProbe:
    return WebRTCParticipantProbe(
        role=role,
        process_id=process_id,
        local_identity=f"simo-{role}",
        local_participant_sid=local_sid,
        remote_identity="simo-remote",
        remote_participant_sids=("PA_remote",),
        received_frames=30,
        received_samples=9_600,
        received_peak=4_000,
        self_echo_frames=0,
        unexpected_identity_frames=0,
        published_samples=21_600,
        elapsed_ms=1_500,
    )


class LiveKitProbeTests(unittest.TestCase):
    def test_synthetic_signal_is_bounded_voiced_pcm(self) -> None:
        first = _synthetic_speech_shaped_pcm(marker=1)
        second = _synthetic_speech_shaped_pcm(marker=2)
        samples = array("h")
        samples.frombytes(first)

        self.assertEqual(21_600, len(samples))
        self.assertGreater(max(samples), 1_000)
        self.assertLess(min(samples), -1_000)
        self.assertNotEqual(first, second)

    def test_runner_fails_closed_without_server_binary(self) -> None:
        with patch("simo.livekit_probe.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "livekit-server is required"):
                asyncio.run(run_two_process_probe())

    def test_structured_cli_returns_probe_contract(self) -> None:
        expected = TwoProcessWebRTCProbe(
            "livekit-server version 1.13.5",
            "simo-probe-test",
            (
                participant("initiator", 100, "PA_a"),
                participant("responder", 101, "PA_b"),
            ),
            True,
            True,
            0,
            0,
            False,
        )
        output = io.StringIO()
        with (
            patch(
                "simo.livekit_probe.run_two_process_probe",
                new=AsyncMock(return_value=expected),
            ),
            redirect_stdout(output),
        ):
            status = main(["lab", "prove-webrtc", "--json"])

        payload = cast(dict[str, object], cast(object, json.loads(output.getvalue())))
        self.assertEqual(0, status)
        self.assertTrue(payload["processes_distinct"])
        self.assertEqual(0, payload["self_echo_frames"])
        self.assertFalse(payload["raw_audio_retained"])


if __name__ == "__main__":
    unittest.main()
