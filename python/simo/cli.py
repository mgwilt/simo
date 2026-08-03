"""Simo command-line lifecycle boundary."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import yaml

# Keep the default CLI event stream machine-readable. Pipecat uses Loguru and
# operators may opt into its separate diagnostics explicitly in future modes.
os.environ.setdefault("LOGURU_AUTOINIT", "False")
os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[2] / ".cache" / "nltk_data"),
)

from simo.config import RunMode, RuntimeConfig
from simo.conversation import PersistedConversationRuntime
from simo.doctor import DoctorReport, inspect_runtime
from simo.operations import JsonEventSink
from simo.persistence import SimoDataError, SimoStore
from simo.runtime import HeadlessRuntime, LiveRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simo")
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="override the platform application-data directory",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    alias = subcommands.add_parser("alias", help="manage persisted conversational aliases")
    alias_commands = alias.add_subparsers(dest="alias_command", required=True)
    alias_create = alias_commands.add_parser("create", help="create a persisted alias")
    alias_create.add_argument("display_name")
    alias_create.add_argument(
        "--summary",
        default="A curious, attentive conversational partner.",
        help="initial persona summary",
    )
    alias_create.add_argument(
        "--instructions",
        default="Speak naturally, listen closely, and preserve continuity.",
        help="initial persona instructions",
    )
    alias_create.add_argument("--json", action="store_true", dest="as_json")
    alias_list = alias_commands.add_parser("list", help="list persisted aliases")
    alias_list.add_argument("--json", action="store_true", dest="as_json")
    alias_show = alias_commands.add_parser("show", help="show an alias and its versions")
    alias_show.add_argument("alias_id")
    alias_show.add_argument("--json", action="store_true", dest="as_json")
    persona = alias_commands.add_parser(
        "revise-persona", help="create and activate a persona version"
    )
    persona.add_argument("alias_id")
    persona.add_argument("--summary", required=True)
    persona.add_argument("--instructions", required=True)
    persona.add_argument("--json", action="store_true", dest="as_json")
    profile = alias_commands.add_parser(
        "revise-profile", help="create and activate a runtime profile version"
    )
    profile.add_argument("alias_id")
    profile.add_argument("profile_json", type=Path)
    profile.add_argument("--json", action="store_true", dest="as_json")
    alias_export = alias_commands.add_parser("export", help="export an alias bundle")
    alias_export.add_argument("alias_id")
    alias_export.add_argument("destination", type=Path)
    alias_export.add_argument("--json", action="store_true", dest="as_json")
    alias_import = alias_commands.add_parser("import", help="import an alias bundle")
    alias_import.add_argument("source", type=Path)
    alias_import.add_argument("--json", action="store_true", dest="as_json")

    conversation = subcommands.add_parser("conversation", help="manage persisted conversations")
    conversation_commands = conversation.add_subparsers(dest="conversation_command", required=True)
    conversation_create = conversation_commands.add_parser(
        "create", help="create a conversation for an alias"
    )
    conversation_create.add_argument("--alias", required=True, dest="alias_id")
    conversation_create.add_argument("--title")
    conversation_create.add_argument("--json", action="store_true", dest="as_json")
    conversation_list = conversation_commands.add_parser(
        "list", help="list persisted conversations"
    )
    conversation_list.add_argument("--alias", dest="alias_id")
    conversation_list.add_argument("--json", action="store_true", dest="as_json")
    conversation_show = conversation_commands.add_parser(
        "show", help="show participants and ordered events"
    )
    conversation_show.add_argument("conversation_id")
    conversation_show.add_argument("--json", action="store_true", dest="as_json")
    conversation_resume = conversation_commands.add_parser(
        "resume", help="mark a persisted conversation active and record resumption"
    )
    conversation_resume.add_argument("conversation_id")
    conversation_resume.add_argument("--alias", dest="alias_id")
    conversation_resume.add_argument("--json", action="store_true", dest="as_json")
    conversation_export = conversation_commands.add_parser(
        "export", help="export conversation events and primary transcript as JSON"
    )
    conversation_export.add_argument("conversation_id")
    conversation_export.add_argument("destination", type=Path)
    conversation_export.add_argument("--json", action="store_true", dest="as_json")
    conversation_delete = conversation_commands.add_parser(
        "delete", help="permanently delete a conversation and derived records"
    )
    conversation_delete.add_argument("conversation_id")
    conversation_delete.add_argument("--yes", action="store_true")
    conversation_delete.add_argument("--json", action="store_true", dest="as_json")

    memory = subcommands.add_parser("memory", help="inspect and govern private learned claims")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_list = memory_commands.add_parser("list", help="list an alias's retained claims")
    memory_list.add_argument("--alias", required=True, dest="alias_id")
    memory_list.add_argument("--subject", dest="subject_id")
    memory_list.add_argument("--status", choices=("active", "superseded", "rejected"))
    memory_list.add_argument("--json", action="store_true", dest="as_json")
    memory_show = memory_commands.add_parser("show", help="show a learned claim and provenance")
    memory_show.add_argument("claim_id")
    memory_show.add_argument("--json", action="store_true", dest="as_json")
    memory_correct = memory_commands.add_parser(
        "correct", help="supersede an active claim with an operator correction"
    )
    memory_correct.add_argument("claim_id")
    memory_correct.add_argument("content")
    memory_correct.add_argument("--json", action="store_true", dest="as_json")
    memory_forget = memory_commands.add_parser(
        "forget", help="permanently remove a claim and its materialized content"
    )
    memory_forget.add_argument("claim_id")
    memory_forget.add_argument("--yes", action="store_true")
    memory_forget.add_argument("--json", action="store_true", dest="as_json")

    talk = subcommands.add_parser(
        "talk", help="run and persist synthetic turns through Pipecat and Flecs"
    )
    talk.add_argument("--alias", required=True, dest="alias_id")
    talk.add_argument("--conversation", dest="conversation_id")
    talk.add_argument(
        "--turn",
        action="append",
        required=True,
        help="synthetic final user turn; repeat for a multi-turn conversation",
    )
    talk.add_argument("--complete", action="store_true")
    talk.add_argument("--json", action="store_true", dest="as_json")

    doctor = subcommands.add_parser("doctor", help="inspect runtime prerequisites")
    doctor.add_argument("--mode", choices=tuple(RunMode), default=RunMode.HEADLESS)
    doctor.add_argument("--json", action="store_true", dest="as_json")

    headless = subcommands.add_parser(
        "headless", help="run the deterministic no-model context path"
    )
    headless.add_argument(
        "--transcript",
        action="append",
        default=[],
        help="final user transcript to enqueue; repeat for multiple turns",
    )
    subcommands.add_parser(
        "live",
        help="run the local microphone/speaker MLX voice agent",
    )
    proof = subcommands.add_parser(
        "prove-models",
        help="execute the selected local models without opening audio devices",
    )
    proof.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path(".artifacts/model-proof"),
        help="ignored directory for the synthetic TTS WAV",
    )
    subcommands.add_parser(
        "calibrate-mic",
        help="interactively recommend a threshold using audible cues",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command: str = args.command  # pyright: ignore[reportAny]
    try:
        if command in {"alias", "conversation", "memory"}:
            return _run_data_command(args)
        requested_mode = (
            RunMode.MODELS
            if command == "prove-models"
            else (
                RunMode.LIVE
                if command in {"live", "calibrate-mic"}
                else getattr(args, "mode", RunMode.HEADLESS)
            )
        )
        config = RuntimeConfig.from_environment(mode=requested_mode)
        if args.command == "doctor":
            report = inspect_runtime(config)
            _print_report(report, args.as_json)
            return 0 if report.ready else 1
        if args.command == "headless":
            report = inspect_runtime(config)
            if not report.ready:
                _print_report(report, False)
                return 1
            result = asyncio.run(
                HeadlessRuntime(config, events=JsonEventSink(sys.stderr)).run(args.transcript)
            )
            print(
                json.dumps(
                    {
                        "snapshot": result.snapshot,
                        "stats": result.stats,
                        "pipeline": result.pipeline,
                        "knowledge": result.knowledge,
                        "operations": result.operations,
                    }
                )
            )
            return 0
        if command == "talk":
            report = inspect_runtime(config)
            if not report.ready:
                _print_report(report, False)
                return 1
            store = SimoStore(_arg_optional_path(args, "data_dir"))
            result = asyncio.run(
                PersistedConversationRuntime(store, config).run(
                    _arg_str(args, "alias_id"),
                    _arg_str_list(args, "turn"),
                    conversation_id=_arg_optional_str(args, "conversation_id"),
                    complete=_arg_bool(args, "complete"),
                )
            )
            _print_structured(result.as_dict(), _arg_bool(args, "as_json"))
            return 0
        if args.command == "live":
            report = inspect_runtime(config)
            if not report.ready:
                _print_report(report, False)
                return 1
            result = asyncio.run(LiveRuntime(config, events=JsonEventSink(sys.stderr)).run())
            print(json.dumps({"operations": result.operations}))
            return 0
        if args.command == "prove-models":
            report = inspect_runtime(config)
            if not report.ready:
                _print_report(report, False)
                return 1
            from simo.model_proof import prove_models

            result = asyncio.run(prove_models(config, args.artifacts_dir))
            print(json.dumps(result))
            return 0
        if args.command == "calibrate-mic":
            from simo.audio_diagnostics import run_interactive_calibration

            print(
                "Wait quietly for one tone, then speak normally until two tones.",
                file=sys.stderr,
            )
            result = run_interactive_calibration(
                configured_start_rms=config.vad_start_rms,
                input_device_index=config.audio_input_device_index,
                output_device_index=config.audio_output_device_index,
            )
            print(json.dumps(result))
            return 0 if result["ready"] else 1
    except KeyboardInterrupt:
        print("simo: interrupted", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, SimoDataError, ValueError) as error:
        print(f"simo: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command: {args.command}")


def _run_data_command(args: argparse.Namespace) -> int:
    store = SimoStore(_arg_optional_path(args, "data_dir"))
    command = _arg_str(args, "command")
    if command == "alias":
        return _run_alias_command(store, args)
    if command == "conversation":
        return _run_conversation_command(store, args)
    if command == "memory":
        return _run_memory_command(store, args)
    raise AssertionError(f"unhandled data command: {command}")


def _run_alias_command(store: SimoStore, args: argparse.Namespace) -> int:
    command = _arg_str(args, "alias_command")
    as_json = _arg_bool(args, "as_json")
    if command == "create":
        alias = store.create_alias(
            _arg_str(args, "display_name"),
            persona_summary=_arg_str(args, "summary"),
            persona_instructions=_arg_str(args, "instructions"),
        )
        _print_structured(alias.as_dict(), as_json)
        return 0
    if command == "list":
        _print_structured([alias.as_dict() for alias in store.list_aliases()], as_json)
        return 0
    if command == "show":
        alias_id = _arg_str(args, "alias_id")
        payload: dict[str, object] = {
            "alias": store.get_alias(alias_id).as_dict(),
            "personas": [item.as_dict() for item in store.list_persona_versions(alias_id)],
            "runtime_profiles": [
                item.as_dict() for item in store.list_runtime_profile_versions(alias_id)
            ],
        }
        _print_structured(payload, as_json)
        return 0
    if command == "revise-persona":
        persona = store.revise_persona(
            _arg_str(args, "alias_id"),
            _arg_str(args, "summary"),
            _arg_str(args, "instructions"),
        )
        _print_structured(persona.as_dict(), as_json)
        return 0
    if command == "revise-profile":
        profile = store.revise_runtime_profile(
            _arg_str(args, "alias_id"),
            _load_json_file(_arg_path(args, "profile_json")),
        )
        _print_structured(profile.as_dict(), as_json)
        return 0
    if command == "export":
        alias_id = _arg_str(args, "alias_id")
        path = store.export_alias(alias_id, _arg_path(args, "destination"))
        _print_structured({"alias_id": alias_id, "path": str(path)}, as_json)
        return 0
    if command == "import":
        alias = store.import_alias(_arg_path(args, "source"))
        _print_structured(alias.as_dict(), as_json)
        return 0
    raise AssertionError(f"unhandled alias command: {command}")


def _run_conversation_command(store: SimoStore, args: argparse.Namespace) -> int:
    command = _arg_str(args, "conversation_command")
    as_json = _arg_bool(args, "as_json")
    if command == "create":
        conversation = store.create_conversation(
            _arg_str(args, "alias_id"),
            title=_arg_optional_str(args, "title"),
        )
        _print_structured(conversation.as_dict(), as_json)
        return 0
    if command == "list":
        conversations = store.list_conversations(_arg_optional_str(args, "alias_id"))
        _print_structured([item.as_dict() for item in conversations], as_json)
        return 0
    if command == "show":
        conversation_id = _arg_str(args, "conversation_id")
        conversation = store.get_conversation(conversation_id)
        payload = conversation.as_dict()
        payload["transcript"] = [item.as_dict() for item in store.transcript(conversation_id)]
        _print_structured(payload, as_json)
        return 0
    if command == "resume":
        conversation = store.resume_conversation(
            _arg_str(args, "conversation_id"),
            alias_id=_arg_optional_str(args, "alias_id"),
        )
        _print_structured(conversation.as_dict(), as_json)
        return 0
    if command == "export":
        conversation_id = _arg_str(args, "conversation_id")
        path = store.export_conversation(conversation_id, _arg_path(args, "destination"))
        _print_structured({"conversation_id": conversation_id, "path": str(path)}, as_json)
        return 0
    if command == "delete":
        if not _arg_bool(args, "yes"):
            raise ValueError("conversation delete requires --yes")
        conversation_id = _arg_str(args, "conversation_id")
        store.delete_conversation(conversation_id)
        _print_structured({"conversation_id": conversation_id, "deleted": True}, as_json)
        return 0
    raise AssertionError(f"unhandled conversation command: {command}")


def _run_memory_command(store: SimoStore, args: argparse.Namespace) -> int:
    command = _arg_str(args, "memory_command")
    as_json = _arg_bool(args, "as_json")
    if command == "list":
        claims = store.list_memory_claims(
            _arg_str(args, "alias_id"),
            subject_id=_arg_optional_str(args, "subject_id"),
            status=_arg_optional_str(args, "status"),
        )
        _print_structured([claim.as_dict() for claim in claims], as_json)
        return 0
    if command == "show":
        _print_structured(store.get_memory_claim(_arg_str(args, "claim_id")).as_dict(), as_json)
        return 0
    if command == "correct":
        claim = store.correct_memory_claim(
            _arg_str(args, "claim_id"),
            _arg_str(args, "content"),
        )
        _print_structured(claim.as_dict(), as_json)
        return 0
    if command == "forget":
        if not _arg_bool(args, "yes"):
            raise ValueError("memory forget requires --yes")
        claim = store.forget_memory_claim(_arg_str(args, "claim_id"))
        _print_structured({"claim_id": claim.claim_id, "forgotten": True}, as_json)
        return 0
    raise AssertionError(f"unhandled memory command: {command}")


def _load_json_file(path: Path) -> dict[str, object]:
    try:
        value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON profile: {path}") from error
    if not isinstance(value, dict):
        raise TypeError("runtime profile JSON must be an object")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError("runtime profile JSON keys must be strings")
    return {cast(str, key): item for key, item in mapping.items()}


def _print_structured(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True, ensure_ascii=False))
        return
    print(yaml.safe_dump(value, sort_keys=False, allow_unicode=True).rstrip())


def _arg_value(args: argparse.Namespace, name: str) -> object:
    return cast(object, getattr(args, name))


def _arg_str(args: argparse.Namespace, name: str) -> str:
    value = _arg_value(args, name)
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _arg_optional_str(args: argparse.Namespace, name: str) -> str | None:
    value = _arg_value(args, name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or null")
    return value


def _arg_path(args: argparse.Namespace, name: str) -> Path:
    value = _arg_value(args, name)
    if not isinstance(value, Path):
        raise TypeError(f"{name} must be a path")
    return value


def _arg_optional_path(args: argparse.Namespace, name: str) -> Path | None:
    value = _arg_value(args, name)
    if value is None:
        return None
    if not isinstance(value, Path):
        raise TypeError(f"{name} must be a path or null")
    return value


def _arg_bool(args: argparse.Namespace, name: str) -> bool:
    value = _arg_value(args, name)
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value


def _arg_str_list(args: argparse.Namespace, name: str) -> list[str]:
    value = _arg_value(args, name)
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list")
    selected: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise TypeError(f"{name} entries must be strings")
        selected.append(item)
    return selected


def _print_report(report: DoctorReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.as_dict()))
        return
    print(f"Simo {report.mode.value}: {'ready' if report.ready else 'not ready'}")
    for check in report.checks:
        marker = "ok" if check.ok else "missing"
        requirement = "required" if check.required else "optional"
        print(f"- [{marker}] {check.name} ({requirement}): {check.detail}")
