from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.setup_live_data import install_archive, is_installed


def make_archive(member: str = "punkt_tab/english/abbrev_types.txt") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(member, "test-data")
    return output.getvalue()


class LiveDataSetupTests(unittest.TestCase):
    def test_checksum_verified_archive_installs_expected_tree(self) -> None:
        data = make_archive()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tokenizers" / "punkt_tab"
            install_archive(
                data,
                target,
                expected_sha256=hashlib.sha256(data).hexdigest(),
            )

            self.assertTrue(is_installed(target))
            self.assertEqual(
                "test-data",
                (target / "english" / "abbrev_types.txt").read_text(),
            )

    def test_rejects_checksum_mismatch_and_path_traversal(self) -> None:
        data = make_archive()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "punkt_tab"
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                install_archive(data, target, expected_sha256="0" * 64)

        unsafe = make_archive("../outside.txt")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "punkt_tab"
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                install_archive(
                    unsafe,
                    target,
                    expected_sha256=hashlib.sha256(unsafe).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
