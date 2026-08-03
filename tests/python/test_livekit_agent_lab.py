from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

from simo.cli import main
from simo.livekit_agent_lab import (
    AgentLabParticipant,
    TwoAgentLabResult,
    _inspect_transcript,
    _validate_result,
)
from simo.livekit_runtime import LiveKitAliasRunResult
from simo.persistence import ConversationEventType, SimoStore


def run_result(
    alias_id: str, conversation_id: str, identity: str, sid: str
) -> LiveKitAliasRunResult:
    return LiveKitAliasRunResult(
        alias_id,
        conversation_id,
        identity,
        sid,
        "remote",
        7,
        4,
        2,
        4,
        "max_spoken_turns",
        False,
        {"accepted": 6, "dropped": 0, "processed": 6, "failed": 0, "queued": 0},
    )


class LiveKitAgentLabTests(unittest.TestCase):
    def test_persisted_transcript_audit_detects_identity_and_duplicate_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = SimoStore(temporary)
            alias = store.create_alias("Ada")
            detail = store.create_conversation(alias.alias_id)
            conversation_id = detail.conversation.conversation_id
            local_id = f"alias:{alias.alias_id}"
            store.bind_participant_transport(conversation_id, local_id, "lk-ada")
            store.add_participant(
                conversation_id,
                "alias:bea",
                kind="external",
                display_name="Bea",
                transport_participant_id="lk-bea",
            )
            store.append_event(
                conversation_id,
                ConversationEventType.USER_TRANSCRIPT_FINAL,
                participant_id="alias:bea",
                text="Hello Ada",
                metadata={"transport_participant_id": "lk-bea"},
            )
            store.append_event(
                conversation_id,
                ConversationEventType.ASSISTANT_SPOKEN,
                participant_id=local_id,
                text="Hello Bea",
                persona_version=1,
                runtime_profile_version=1,
            )

            checks = _inspect_transcript(
                store,
                conversation_id,
                local_participant_id=local_id,
                local_transport_identity="lk-ada",
                remote_participant_id="alias:bea",
                remote_transport_identity="lk-bea",
            )

            self.assertEqual(0, checks.self_echo_turns)
            self.assertEqual(0, checks.unexpected_identity_turns)
            self.assertEqual(0, checks.attribution_errors)
            self.assertEqual(0, checks.duplicate_turns)
            self.assertEqual(0, checks.incomplete_generated_turns)
            self.assertEqual(0, checks.interrupted_spoken_turns)
            self.assertEqual(1, checks.user_turns)
            self.assertTrue(checks.reviewable)

    def test_result_gate_requires_real_audio_turns_and_isolation(self) -> None:
        first_run = run_result("a", "ca", "lk-a", "PA-a")
        second_run = run_result("b", "cb", "lk-b", "PA-b")
        result = TwoAgentLabResult(
            "livekit-server version 1.13.5",
            "room",
            "/tmp/artifacts",
            (
                AgentLabParticipant("initiator", 10, "/tmp/a", first_run),
                AgentLabParticipant("responder", 11, "/tmp/b", second_run),
            ),
            True,
            True,
            0,
            0,
            0,
            0,
            0,
            0,
            False,
            3,
            True,
            1_000,
        )

        _validate_result(result, turns_per_alias=2)
        with self.assertRaisesRegex(RuntimeError, "identity isolation"):
            _validate_result(
                replace(result, self_echo_turns=1),
                turns_per_alias=2,
            )
        with self.assertRaisesRegex(RuntimeError, "incomplete voice turn"):
            _validate_result(
                replace(result, incomplete_generated_turns=1),
                turns_per_alias=2,
            )

    def test_structured_cli_exposes_reviewable_agent_lab_artifacts(self) -> None:
        first_run = run_result("a", "ca", "lk-a", "PA-a")
        second_run = run_result("b", "cb", "lk-b", "PA-b")
        expected = TwoAgentLabResult(
            "livekit-server version 1.13.5",
            "room",
            "/tmp/artifacts",
            (
                AgentLabParticipant("initiator", 10, "/tmp/a", first_run),
                AgentLabParticipant("responder", 11, "/tmp/b", second_run),
            ),
            True,
            True,
            0,
            0,
            0,
            0,
            0,
            0,
            False,
            3,
            True,
            1_000,
        )
        output = io.StringIO()
        with (
            patch(
                "simo.livekit_agent_lab.run_two_agent_lab",
                new=AsyncMock(return_value=expected),
            ),
            redirect_stdout(output),
        ):
            status = main(
                [
                    "lab",
                    "converse",
                    "--artifacts-dir",
                    str(Path("/tmp/lab")),
                    "--json",
                ]
            )

        payload = cast(dict[str, object], cast(object, json.loads(output.getvalue())))
        self.assertEqual(0, status)
        self.assertTrue(payload["transcripts_reviewable"])
        self.assertEqual("/tmp/artifacts", payload["artifacts_dir"])


if __name__ == "__main__":
    unittest.main()
