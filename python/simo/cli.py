"""Simo command-line lifecycle boundary."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

# Keep the default CLI event stream machine-readable. Pipecat uses Loguru and
# operators may opt into its separate diagnostics explicitly in future modes.
os.environ.setdefault("LOGURU_AUTOINIT", "False")
os.environ.setdefault(
    "NLTK_DATA",
    str(Path(__file__).resolve().parents[2] / ".cache" / "nltk_data"),
)

from simo.config import RunMode, RuntimeConfig
from simo.doctor import DoctorReport, inspect_runtime
from simo.operations import JsonEventSink
from simo.runtime import HeadlessRuntime, LiveRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simo")
    subcommands = parser.add_subparsers(dest="command", required=True)

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
    calibration = subcommands.add_parser(
        "calibrate-mic",
        help="recommend a speech threshold from aggregate microphone levels",
    )
    calibration.add_argument("--ambient-seconds", type=float, default=2.0)
    calibration.add_argument("--speech-seconds", type=float, default=3.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        requested_mode = (
            RunMode.LIVE
            if args.command in {"live", "prove-models", "calibrate-mic"}
            else getattr(args, "mode", RunMode.HEADLESS)
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
                HeadlessRuntime(config, events=JsonEventSink(sys.stderr)).run(
                    args.transcript
                )
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
        if args.command == "live":
            report = inspect_runtime(config)
            if not report.ready:
                _print_report(report, False)
                return 1
            result = asyncio.run(
                LiveRuntime(config, events=JsonEventSink(sys.stderr)).run()
            )
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
            from simo.audio_diagnostics import calibration_result, capture_rms_blocks

            print(
                f"Remain quiet for {args.ambient_seconds:g} seconds...",
                file=sys.stderr,
            )
            ambient = capture_rms_blocks(
                args.ambient_seconds,
                device_index=config.audio_input_device_index,
            )
            print(
                f"Speak continuously for {args.speech_seconds:g} seconds...",
                file=sys.stderr,
            )
            speech = capture_rms_blocks(
                args.speech_seconds,
                device_index=config.audio_input_device_index,
            )
            result = calibration_result(
                ambient,
                speech,
                configured_start_rms=config.vad_start_rms,
            )
            print(json.dumps(result))
            return 0 if result["ready"] else 1
    except KeyboardInterrupt:
        print("simo: interrupted", file=sys.stderr)
        return 130
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"simo: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command: {args.command}")


def _print_report(report: DoctorReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.as_dict()))
        return
    print(f"Simo {report.mode.value}: {'ready' if report.ready else 'not ready'}")
    for check in report.checks:
        marker = "ok" if check.ok else "missing"
        requirement = "required" if check.required else "optional"
        print(f"- [{marker}] {check.name} ({requirement}): {check.detail}")
