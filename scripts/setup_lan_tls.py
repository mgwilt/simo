#!/usr/bin/env python3
"""Plan or explicitly create a trusted local certificate for Simo's LAN site."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
from pathlib import Path

from simo.lan_site import discover_lan_ip


class _Args(argparse.Namespace):
    accept_install: bool
    hostname: str | None
    node_ip: str | None
    output_dir: Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a trusted Simo LAN certificate")
    parser.add_argument("--accept-install", action="store_true")
    parser.add_argument("--hostname")
    parser.add_argument("--node-ip")
    parser.add_argument("--output-dir", type=Path, default=Path(".artifacts/lan-tls"))
    args = parser.parse_args(namespace=_Args())
    hostname = args.hostname or f"{socket.gethostname().split('.', 1)[0]}.local"
    node_ip = args.node_ip or discover_lan_ip()
    certificate = args.output_dir / "simo-lan.pem"
    private_key = args.output_dir / "simo-lan-key.pem"
    payload = {
        "hostname": hostname,
        "node_ip": node_ip,
        "certificate": str(certificate),
        "private_key": str(private_key),
        "requires_explicit_flag": "--accept-install",
    }
    print(json.dumps(payload, indent=2))
    if not args.accept_install:
        return 0
    binary = shutil.which("mkcert")
    if binary is None:
        raise RuntimeError("mkcert is required; install it with Homebrew")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([binary, "-install"], check=True)
    subprocess.run(
        [
            binary,
            "-cert-file",
            str(certificate),
            "-key-file",
            str(private_key),
            hostname,
            node_ip,
            "localhost",
            "127.0.0.1",
        ],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
