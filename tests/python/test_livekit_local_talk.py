from __future__ import annotations

import unittest
from typing import cast

from livekit import rtc
from simo.livekit_local_talk import LocalTalkDevices, LocalTalkResult, _select_device
from simo.livekit_runtime import LiveKitAliasRunResult


class LiveKitLocalTalkTests(unittest.TestCase):
    def test_device_selection_defaults_and_rejects_unavailable_index(self) -> None:
        devices = [
            rtc.AudioDeviceInfo(0, "default (Headset)", "default"),
            rtc.AudioDeviceInfo(2, "Headset", "headset"),
        ]

        self.assertEqual("default", _select_device(devices, None, "recording").id)
        self.assertEqual("headset", _select_device(devices, 2, "recording").id)
        with self.assertRaisesRegex(ValueError, "available: 0:default.*2:Headset"):
            _select_device(devices, 4, "recording")

    def test_result_exposes_room_devices_and_persisted_runtime(self) -> None:
        run = LiveKitAliasRunResult(
            "alias-a",
            "conversation-a",
            "alias-transport",
            "PA-alias",
            "human-transport",
            8,
            4,
            2,
            4,
            "participant_disconnected",
            False,
            {"accepted": 7, "dropped": 0, "processed": 7, "failed": 0, "queued": 0},
        )
        result = LocalTalkResult(
            "livekit-server version 1.13.5",
            "simo-talk-example",
            "PA-human",
            LocalTalkDevices("Headset microphone", "Headset speakers"),
            run,
        )

        payload = result.as_dict()
        run_payload = cast(dict[str, object], payload["run"])

        self.assertEqual("PA-human", payload["human_participant_sid"])
        self.assertEqual("conversation-a", run_payload["conversation_id"])
        self.assertFalse(run_payload["raw_audio_retained"])


if __name__ == "__main__":
    unittest.main()
