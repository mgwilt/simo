#!/usr/bin/env python3
"""Install small, checksum-pinned live runtime data without model weights."""

from __future__ import annotations

import hashlib
import shutil
import ssl
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

import certifi

PUNKT_TAB_URL = (
    "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt_tab.zip"
)
PUNKT_TAB_SHA256 = "e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106"
PUNKT_TAB_MAX_DOWNLOAD_BYTES = 8_000_000
PUNKT_TAB_MAX_UNPACKED_BYTES = 12_000_000


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    target = repository / ".cache" / "nltk_data" / "tokenizers" / "punkt_tab"
    if is_installed(target):
        print(f"punkt_tab already installed: {target}")
        return 0
    archive = download_archive(PUNKT_TAB_URL)
    install_archive(archive, target, expected_sha256=PUNKT_TAB_SHA256)
    print(f"punkt_tab installed: {target}")
    return 0


def download_archive(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "simo-setup/1"})
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, context=context, timeout=30) as response:
        archive = response.read(PUNKT_TAB_MAX_DOWNLOAD_BYTES + 1)
    if len(archive) > PUNKT_TAB_MAX_DOWNLOAD_BYTES:
        raise RuntimeError("punkt_tab archive exceeds the configured download bound")
    return archive


def install_archive(
    archive: bytes,
    target: Path,
    *,
    expected_sha256: str,
) -> None:
    digest = hashlib.sha256(archive).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(
            f"punkt_tab checksum mismatch: expected {expected_sha256}, received {digest}"
        )
    if target.exists():
        raise FileExistsError(f"refusing to replace existing punkt_tab data: {target}")

    with tempfile.TemporaryDirectory(prefix="simo-punkt-") as directory:
        temporary = Path(directory)
        archive_path = temporary / "punkt_tab.zip"
        archive_path.write_bytes(archive)
        unpacked = temporary / "unpacked"
        with zipfile.ZipFile(archive_path) as bundle:
            members = bundle.infolist()
            if sum(member.file_size for member in members) > PUNKT_TAB_MAX_UNPACKED_BYTES:
                raise RuntimeError("punkt_tab archive exceeds the configured unpacked bound")
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("punkt_tab",):
                    raise RuntimeError(f"unsafe punkt_tab archive member: {member.filename}")
            bundle.extractall(unpacked)
        source = unpacked / "punkt_tab"
        if not is_installed(source):
            raise RuntimeError("punkt_tab archive is missing the English tokenizer data")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)


def is_installed(target: Path) -> bool:
    return (target / "english" / "abbrev_types.txt").is_file()


if __name__ == "__main__":
    raise SystemExit(main())
