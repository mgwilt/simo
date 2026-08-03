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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        requested_mode = (
            RunMode.LIVE
            if args.command == "live"
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
