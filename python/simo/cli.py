"""Simo command-line lifecycle boundary."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from simo.config import RunMode, RuntimeConfig
from simo.doctor import DoctorReport, inspect_runtime
from simo.runtime import HeadlessRuntime


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = RuntimeConfig.from_environment(mode=getattr(args, "mode", "headless"))
        if args.command == "doctor":
            report = inspect_runtime(config)
            _print_report(report, args.as_json)
            return 0 if report.ready else 1
        if args.command == "headless":
            report = inspect_runtime(config)
            if not report.ready:
                _print_report(report, False)
                return 1
            result = HeadlessRuntime(config).run(args.transcript)
            print(json.dumps({"snapshot": result.snapshot, "stats": result.stats}))
            return 0
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
