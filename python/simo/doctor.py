"""Truthful, side-effect-free runtime capability checks."""

from __future__ import annotations

import importlib.util
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from simo.config import RunMode, RuntimeConfig
from simo.context import find_core_library


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    required: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    mode: RunMode
    ready: bool
    checks: tuple[Check, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ready": self.ready,
            "checks": [asdict(check) for check in self.checks],
        }


def inspect_runtime(config: RuntimeConfig) -> DoctorReport:
    """Inspect prerequisites without importing ML runtimes or loading weights."""

    is_live = config.mode is RunMode.LIVE
    checks = [
        Check(
            "platform",
            sys.platform == "darwin",
            True,
            f"{platform.system()} {platform.release()}",
        ),
        Check(
            "architecture",
            platform.machine() == "arm64",
            True,
            _apple_hardware_detail(),
        ),
        _core_check(config),
    ]
    if is_live:
        mlx_module_checks = [
            _module_check(name, module)
            for name, module in (
                ("MLX-Audio", "mlx_audio"),
                ("Parakeet MLX", "parakeet_mlx"),
                ("MLX-LM", "mlx_lm"),
            )
        ]
        audio_module_check = _module_check("PyAudio", "pyaudio")
        checks.extend(mlx_module_checks)
        checks.append(audio_module_check)
        checks.append(
            _mlx_metal_check()
            if all(check.ok for check in mlx_module_checks)
            else Check(
                "MLX Metal device",
                False,
                True,
                "not tested until all MLX runtime modules are installed",
            )
        )
        checks.append(
            _local_audio_device_check(config)
            if audio_module_check.ok
            else Check(
                "local audio devices",
                False,
                True,
                "not tested until PyAudio is installed",
            )
        )
        checks.append(_nltk_data_check())
        checks.extend(
            _model_check(name, model.local_path)
            for name, model in (
                ("TTS model", config.tts),
                ("STT model", config.stt),
                ("text model", config.text),
            )
        )
    ready = all(check.ok for check in checks if check.required)
    return DoctorReport(config.mode, ready, tuple(checks))


def _core_check(config: RuntimeConfig) -> Check:
    try:
        path = find_core_library(config.core_library)
    except FileNotFoundError as error:
        return Check("native core", False, True, str(error))
    return Check("native core", True, True, str(path))


def _module_check(name: str, module: str) -> Check:
    found = importlib.util.find_spec(module) is not None
    detail = f"Python module {module} {'found' if found else 'not installed'}"
    return Check(name, found, True, detail)


def _model_check(name: str, path: Path) -> Check:
    found = path.is_dir() and any(path.iterdir())
    detail = str(path) if found else f"not downloaded at {path}"
    return Check(name, found, True, detail)


def _mlx_metal_check() -> Check:
    result = subprocess.run(
        [sys.executable, "-c", "import mlx.core; print('available')"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Check("MLX Metal device", True, True, "available to this process")
    detail_lines = (result.stderr or result.stdout).strip().splitlines()
    detail = detail_lines[-1] if detail_lines else f"process exited {result.returncode}"
    return Check("MLX Metal device", False, True, detail[:240])


def _nltk_data_check() -> Check:
    try:
        spec = importlib.util.find_spec("nltk")
        if spec is None:
            raise LookupError
        import nltk

        location = nltk.data.find("tokenizers/punkt_tab")
    except (ImportError, LookupError):
        return Check(
            "Pipecat sentence data",
            False,
            True,
            "NLTK punkt_tab not installed; run: python -m nltk.downloader punkt_tab",
        )
    return Check("Pipecat sentence data", True, True, str(location))


def _local_audio_device_check(config: RuntimeConfig) -> Check:
    script = """
import json
import pyaudio
import sys
p = pyaudio.PyAudio()
try:
    input_index = int(sys.argv[1]) if sys.argv[1] else None
    output_index = int(sys.argv[2]) if sys.argv[2] else None
    input_info = (
        p.get_device_info_by_index(input_index)
        if input_index is not None
        else p.get_default_input_device_info()
    )
    output_info = (
        p.get_device_info_by_index(output_index)
        if output_index is not None
        else p.get_default_output_device_info()
    )
    if int(input_info.get("maxInputChannels", 0)) < 1:
        raise RuntimeError("selected input device has no input channels")
    if int(output_info.get("maxOutputChannels", 0)) < 1:
        raise RuntimeError("selected output device has no output channels")
    value = {
        "input": input_info.get("name", "unknown"),
        "output": output_info.get("name", "unknown"),
    }
    print(json.dumps(value))
finally:
    p.terminate()
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            ""
            if config.audio_input_device_index is None
            else str(config.audio_input_device_index),
            ""
            if config.audio_output_device_index is None
            else str(config.audio_output_device_index),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        try:
            devices = json.loads(result.stdout)
            detail = f"input={devices['input']}; output={devices['output']}"
        except (json.JSONDecodeError, KeyError, TypeError):
            detail = "default input and output are available"
        return Check("local audio devices", True, True, detail)
    detail_lines = (result.stderr or result.stdout).strip().splitlines()
    detail = detail_lines[-1] if detail_lines else "no default input/output available"
    return Check("local audio devices", False, True, detail[:240])


def _apple_hardware_detail() -> str:
    profiler = _system_profiler_hardware()
    if profiler:
        name = profiler.get("machine_name", "Mac")
        chip = profiler.get("chip_type", "Apple Silicon")
        memory = profiler.get("physical_memory", "unknown memory")
        return f"{platform.machine()}, {name}, {chip}, {memory} unified memory"
    chip = _sysctl("machdep.cpu.brand_string") or platform.processor() or "unknown chip"
    memory = _sysctl("hw.memsize")
    if memory and memory.isdigit():
        gibibytes = int(memory) / (1024**3)
        return f"{platform.machine()}, {chip}, {gibibytes:.0f} GiB unified memory"
    return f"{platform.machine()}, {chip}"


def _system_profiler_hardware() -> dict[str, str] | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/sbin/system_profiler", "SPHardwareDataType", "-json"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        hardware = payload["SPHardwareDataType"][0]
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
    ):
        return None
    allowed = ("machine_name", "chip_type", "physical_memory")
    return {key: str(hardware[key]) for key in allowed if key in hardware}


def _sysctl(name: str) -> str | None:
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", name],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None
