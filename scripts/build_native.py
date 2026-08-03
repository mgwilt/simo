"""Build and exercise Simo's native core with the macOS system toolchain."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".build/simo"))
    parser.add_argument("--skip-test", action="store_true")
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[1]
    output = (repository / args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    clang = _tool("clang")
    clangxx = _tool("clang++")
    common = ["-Wall", "-Wextra", "-Wpedantic", "-Werror"]

    _run(
        clang,
        "-std=c17",
        "-fPIC",
        "-DFLECS_STATIC",
        *common,
        "-I",
        repository / "vendor/flecs/include",
        "-c",
        repository / "vendor/flecs/distr/flecs.c",
        "-o",
        output / "flecs.o",
    )
    objects = [output / "flecs.o"]
    for source in ("context_engine.cpp", "context_engine_c.cpp"):
        object_path = output / f"{Path(source).stem}.o"
        _run(
            clangxx,
            "-std=c++20",
            "-fPIC",
            "-DSIMO_CORE_BUILD",
            *common,
            "-I",
            repository / "include",
            "-I",
            repository / "vendor/flecs/include",
            "-c",
            repository / "src" / source,
            "-o",
            object_path,
        )
        objects.append(object_path)

    library = output / "libsimo_core.dylib"
    _run(
        clangxx,
        "-dynamiclib",
        "-Wl,-install_name,@rpath/libsimo_core.dylib",
        *objects,
        "-o",
        library,
    )
    if not args.skip_test:
        test = output / "simo_context_engine_test"
        _run(
            clangxx,
            "-std=c++20",
            *common,
            "-I",
            repository / "include",
            repository / "tests/native/context_engine_test.cpp",
            "-L",
            output,
            "-lsimo_core",
            "-Wl,-rpath,@loader_path",
            "-o",
            test,
        )
        _run(test)
    print(library)
    return 0


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    xcrun = shutil.which("xcrun")
    if xcrun:
        result = subprocess.run(
            [xcrun, "--find", name], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    raise RuntimeError(f"required compiler not found: {name}")


def _run(*command: str | Path) -> None:
    subprocess.run([str(value) for value in command], check=True)


if __name__ == "__main__":
    raise SystemExit(main())
