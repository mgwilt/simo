"""Truthful, side-effect-free runtime capability checks."""

from __future__ import annotations

import http.client
import importlib.util
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any, cast
from urllib.parse import urlparse

from simo.config import ModelConfig, RunMode, RuntimeConfig, TTSBackend
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

    requires_models = config.mode in (RunMode.MODELS, RunMode.LIVE)
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
    livekit_checks: list[Check] = []
    if requires_models:
        mlx_modules = [
            ("Parakeet MLX", "parakeet_mlx"),
            ("MLX-LM", "mlx_lm"),
        ]
        if config.tts_backend is TTSBackend.QWEN:
            mlx_modules.insert(0, ("MLX-Audio", "mlx_audio"))
        mlx_module_checks = [_module_check(name, module) for name, module in mlx_modules]
        checks.extend(mlx_module_checks)
        if is_live:
            livekit_checks = [
                _module_check("LiveKit Agents", "livekit.agents"),
                _module_check("LiveKit Silero", "livekit.plugins.silero"),
            ]
            checks.extend(livekit_checks)
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
        if is_live:
            checks.append(
                _local_audio_device_check(config)
                if all(check.ok for check in livekit_checks)
                else Check(
                    "local audio devices",
                    False,
                    True,
                    "not tested until the LiveKit runtime is installed",
                )
            )
        else:
            checks.append(_nltk_data_check())
        checks.extend(
            _model_check(name, model)
            for name, model in (
                ("TTS model", config.tts),
                ("STT model", config.stt),
                ("text model", config.text),
            )
        )
        if config.tts_backend is TTSBackend.BREEZE:
            checks.append(_breeze_service_check(config))
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


def _breeze_service_check(config: RuntimeConfig) -> Check:
    health_url = config.tts_endpoint.rsplit("/", 3)[0] + "/health"
    parsed = urlparse(health_url)
    if parsed.hostname is None:
        return Check("Breeze service", False, True, "health URL has no host")
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=1.0)
    try:
        connection.request("GET", parsed.path)
        response = connection.getresponse()
        raw = cast(object, json.loads(response.read(65_536)))
    except (OSError, json.JSONDecodeError) as error:
        return Check("Breeze service", False, True, f"unavailable at {health_url}: {error}")
    finally:
        connection.close()
    if not isinstance(raw, dict):
        return Check("Breeze service", False, True, "health response is not an object")
    payload = {str(key): value for key, value in cast(dict[object, object], raw).items()}
    ready = payload.get("status") == "ready"
    return Check(
        "Breeze service",
        ready,
        True,
        f"{payload.get('device', 'unknown')} {payload.get('dtype', 'unknown')} at {health_url}",
    )


def _model_check(name: str, model: ModelConfig) -> Check:
    path = model.local_path
    if not path.is_dir():
        return Check(name, False, True, f"not downloaded at {path}")
    missing = [relative for relative in model.required_paths if not (path / relative).is_file()]
    if missing:
        return Check(name, False, True, f"incomplete at {path}; missing {', '.join(missing)}")
    marker_path = path / ".simo-model.json"
    try:
        marker = json.loads(marker_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return Check(name, False, True, f"unverified at {path}; run scripts/setup_models.py")
    if marker.get("model_id") != model.model_id or marker.get("revision") != model.revision:
        return Check(
            name,
            False,
            True,
            f"model marker does not match configured revision at {path}",
        )
    return Check(name, True, True, f"{path} @ {model.revision[:12]}")


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
import sys
from livekit import rtc

p = rtc.PlatformAudio()
try:
    input_index = int(sys.argv[1]) if sys.argv[1] else None
    output_index = int(sys.argv[2]) if sys.argv[2] else None
    inputs = p.recording_devices()
    outputs = p.playout_devices()
    input_info = next(
        (device for device in inputs if device.index == input_index),
        inputs[0] if input_index is None and inputs else None,
    )
    output_info = next(
        (device for device in outputs if device.index == output_index),
        outputs[0] if output_index is None and outputs else None,
    )
    if input_info is None or output_info is None:
        raise RuntimeError("selected LiveKit audio device is unavailable")
    value = {"input": input_info.name, "output": output_info.name}
    print(json.dumps(value))
finally:
    p.close()
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "" if config.audio_input_device_index is None else str(config.audio_input_device_index),
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
