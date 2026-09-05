"""Export recorded benchmark scalars and render deterministic, dependency-free SVGs.

No model imports, inference, network, browser, or audio access. --extract requires
the original local receipts; ordinary rendering uses only checked-in measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks/breeze"
ARTIFACTS = ROOT / ".artifacts/breeze-performance"
TIMELINE = ("reference", "cached", "sdpa", "mlx", "https-control-short")
ARMS = ("bf16", "int8-backbone-bf16-depth", "bf16-backbone-int8-depth", "int8")


def obj(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object")
    return cast("dict[str, object]", value)


def rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise TypeError("Expected a JSON array")
    return [obj(item) for item in cast("list[object]", value)]


def number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return float(value)


def read(path: Path) -> dict[str, object]:
    return obj(cast("object", json.loads(path.read_text(encoding="utf-8"))))


def p95(values: list[float]) -> float:
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("Percentiles require nonempty finite samples")
    return sorted(values)[math.ceil(len(values) * 0.95) - 1]


def receipt(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }


def select(source: dict[str, object], keys: str) -> dict[str, object]:
    return {key: source[key] for key in keys.split() if key in source}


def settings(source: dict[str, object]) -> dict[str, object]:
    """Retain effective settings, compacting only per-weight inventory records."""
    result = dict(source)
    for name in ("backbone_quantization", "depth_quantization"):
        if isinstance(result.get(name), dict):
            quant = dict(obj(result[name]))
            records = quant.pop("records", None)
            if records is not None:
                quant["record_count"] = len(rows(records))
            result[name] = quant
    return result


def extract_cohort(name: str, filename: str, boundary: str, evidence: str) -> dict[str, object]:
    path = ARTIFACTS / filename
    source = read(path)
    runtime = obj(source.get("runtime", {}))
    warmups = source["warmups"]
    started = source.get("started_unix_ns")
    timestamp = (
        datetime.fromtimestamp(number(started) / 1e9, UTC).isoformat()
        if started is not None
        else source.get("recorded_at")
    )
    samples: list[dict[str, object]] = []
    audio = rows(source.get("audio_artifacts", []))
    for index, sample in enumerate(rows(source["samples"])):
        normalized = select(sample, "prompt seed audio_s steady_rtf pcm_sha256 cache failure")
        normalized["instruction"] = sample.get("instruction", source.get("instruction"))
        normalized["first_pcm_s"] = sample.get("first_pcm_s", sample.get("first_audio_s"))
        normalized["total_rtf"] = sample.get("total_rtf", sample.get("rtf"))
        normalized["total_s"] = sample.get("total_s", sample.get("wall_s"))
        producer = obj(sample.get("producer", sample.get("metrics", {})))
        normalized.update(select(producer, "completed cancelled eos_reached codec_frames"))
        if "pcm_sha256" not in normalized and audio:
            if "samples" in audio[index] and number(audio[index]["samples"]) / 24000 != number(
                sample["audio_s"]
            ):
                raise ValueError("Audio duration does not match receipt order")
            normalized["pcm_sha256"] = audio[index]["pcm_sha256"]
        samples.append(normalized)
    return {
        "id": name,
        "evidence": evidence,
        "receipt": receipt(path),
        "clock": {"value": timestamp, "field": "started_unix_ns" if started else "recorded_at"},
        "boundary": boundary,
        "warmups": len(rows(cast("object", warmups))) if isinstance(warmups, list) else warmups,
        "identity": {
            **select(
                source, "source dependencies model_marker metal_device metal_artifacts compiled"
            ),
            "runtime": select(
                runtime,
                "attention cached_depth_cfg cfg_policy codec_chunk_frames dependencies depth_cache "
                "device dtype engine model_digest model_revision os performance_mode quantization "
                "runtime_fingerprint sample_rate sampling source_digest source_revision "
                "metal_artifacts experimental_recipe release_accepted",
            ),
            "settings": settings(
                obj(source.get("effective_settings", runtime.get("runtime_settings", {})))
            ),
            "cfg_scale": source.get("cfg_scale"),
        },
        "samples": samples,
    }


def extract() -> dict[str, object]:
    cohorts = [
        extract_cohort(
            "reference", "baseline-a38d7d1.json", "HTTP client; full-utterance buffering", "E-002"
        ),
        extract_cohort(
            "cached", "streaming-eager-screen.json", "HTTP client; incremental PCM", "E-002"
        ),
        extract_cohort("sdpa", "sdpa-30-samples.json", "HTTP client; incremental PCM", "E-002"),
        extract_cohort(
            "mlx", "mlx-int8-matched-control-short.json", "in-process producer", "E-011"
        ),
    ]
    for condition in ("control", "resident"):
        for suite in ("short", "long", "warm-companion", "bright-guide", "grounded-mentor"):
            name = f"{condition}-{suite}"
            suffix = "-r2" if name == "resident-long" else ""
            cohorts.append(
                extract_cohort(
                    f"https-{name}",
                    f"mlx-https-v1-{name}{suffix}/report.json",
                    "same-host HTTPS client; uncached PCM16LE",
                    "E-015",
                )
            )
    comparison_path = ARTIFACTS / "mlx-precision-matrix-v1/comparison.json"
    comparison = read(comparison_path)
    for arm in ARMS:
        cohort = extract_cohort(
            f"precision-{arm}",
            f"mlx-precision-matrix-v1/{arm}/report.json",
            "in-process producer; matched precision cases",
            "E-018",
        )
        transcripts = [
            obj(item["transcript"]) for item in rows(comparison["asr_rows"]) if item["arm"] == arm
        ]
        cohort["asr_screen"] = {
            key: sum(int(number(item[key])) for item in transcripts)
            for key in ("word_errors", "reference_words")
        }
        for sample, transcript in zip(rows(cohort["samples"]), transcripts, strict=True):
            if sample["prompt"] != transcript["prompt"] or sample["seed"] != transcript["seed"]:
                raise ValueError("ASR row does not match timed sample")
            sample["asr_screen"] = select(transcript, "word_errors reference_words")
        cohorts.append(cohort)
    startup_path = ARTIFACTS / "startup-v1/report.json"
    startup = read(startup_path)
    return {
        "schema_version": 1,
        "title": "Recorded Breeze-TTS-2 engineering measurements, M3 Ultra",
        "limits": "Historical milestones are not controlled ablations. First PCM is not audible onset. "
        "Precision arms match inputs, not sampled outputs. No perceptual release acceptance.",
        "timeline_order": list(TIMELINE),
        "cohorts": cohorts,
        "precision_comparison_receipt": receipt(comparison_path),
        "startup": {
            "receipt": receipt(startup_path),
            "cycles": [
                {
                    **select(cycle, "launch_to_ready_s launch_unix_ns completed"),
                    "runtime_fingerprint": obj(cycle["ready"])["runtime_fingerprint"],
                    "requests": [
                        select(
                            request,
                            "kind request_to_first_pcm_s audio_s audio_samples pcm_sha256 completed",
                        )
                        for request in rows(cycle["requests"])
                    ],
                }
                for cycle in rows(startup["cycles"])
            ],
        },
    }


def cohort_map(data: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(cohort["id"]): cohort for cohort in rows(data["cohorts"])}


def metric(cohort: dict[str, object], field: str) -> float:
    return p95([number(sample[field]) for sample in rows(cohort["samples"])])


class SVG:
    """Small explicit primitive set; fixed canvas, embedded text, no external assets."""

    def __init__(self, title: str, description: str, height: int) -> None:
        self.parts: list[str] = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="{height}" '
                f'viewBox="0 0 1120 {height}" role="img" aria-labelledby="title desc">'
            ),
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
            f'<rect width="1120" height="{height}" fill="#f8fafc"/>',
        ]

    def text(
        self,
        x: float,
        y: float,
        content: str,
        size: int = 17,
        color: str = "#334155",
        *,
        anchor: str = "start",
    ) -> None:
        self.parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-family="Arial, sans-serif" '
            f'font-size="{size}" text-anchor="{anchor}">{escape(content)}</text>'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str = "#cbd5e1",
        *,
        dash: bool = False,
    ) -> None:
        self.parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{color}" stroke-width="2"'
            + (' stroke-dasharray="6 5"' if dash else "")
            + "/>"
        )

    def dot(self, x: float, y: float, color: str, hollow: bool = False) -> None:
        self.parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" stroke="{color}" '
            f'stroke-width="3" fill="{"#f8fafc" if hollow else color}"/>'
        )

    def bar(self, x: float, y: float, width: float, color: str) -> None:
        self.parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="36" rx="4" fill="{color}"/>'
        )

    def finish(self) -> str:
        return "\n".join([*self.parts, "</svg>", ""])


def progression(data: dict[str, object]) -> str:
    cohorts = cohort_map(data)
    chart = SVG(
        "Breeze performance progression",
        "Historical milestone p95 total RTF and first PCM. Different methods and sample counts; not a controlled ablation.",
        790,
    )
    chart.text(38, 44, "Breeze-TTS-2 / performance progression", 29, "#0f172a")
    chart.text(
        38,
        75,
        "Apple M3 Ultra · warm, uncached runs · lower is better · historical cohorts, not isolated speedups",
        18,
    )
    labels = (
        "Locked reference",
        "Cached streaming",
        "MPS + SDPA",
        "MLX int8 producer",
        "MLX int8 HTTPS",
    )
    clocks = (
        "Clock not recorded",
        "Clock not recorded",
        "Sep 05 · 00:31 UTC*",
        "Sep 05 · 06:56 UTC",
        "Sep 05 · 09:13 UTC",
    )
    xs = [145 + index * 208 for index in range(5)]
    for field, top, maximum, ticks, color, heading in (
        (
            "total_rtf",
            155,
            12.0,
            (0, 2, 4, 6, 8, 10),
            "#2563eb",
            "p95 total RTF · seconds of wall time / second of audio",
        ),
        (
            "first_pcm_s",
            410,
            100.0,
            (0.1, 1, 10, 100),
            "#0f766e",
            "p95 first PCM · seconds · logarithmic axis",
        ),
    ):
        chart.text(38, top - 26, heading, 20, "#0f172a")

        def y(
            value: float, *, metric_name: str = field, origin: int = top, limit: float = maximum
        ) -> float:
            fraction = (
                (math.log10(value) + 1) / 3 if metric_name == "first_pcm_s" else value / limit
            )
            return origin + 175 * (1 - fraction)

        for tick in ticks:
            chart.line(108, y(tick), 1015, y(tick))
            chart.text(90, y(tick) + 5, f"{tick:g}", 16, anchor="end")
        if field == "total_rtf":
            chart.line(108, y(1), 1015, y(1), "#64748b", dash=True)
            chart.text(1008, y(1) - 7, "1.0 = real time", 14, anchor="end")
        values = [metric(cohorts[name], field) for name in TIMELINE]
        for index, (x, value) in enumerate(zip(xs, values, strict=True)):
            if index:
                chart.line(xs[index - 1], y(values[index - 1]), x, y(value), color, dash=True)
            chart.dot(x, y(value), color, hollow=index == 1)
            offset = 27 if field == "total_rtf" and index >= 3 else -14
            chart.text(x, y(value) + offset, f"{value:.3f}", 20, color, anchor="middle")
    for x, name, label, timestamp in zip(xs, TIMELINE, labels, clocks, strict=True):
        cohort = cohorts[name]
        chart.text(x, 635, label, 17, "#0f172a", anchor="middle")
        chart.text(
            x,
            659,
            f"n={len(rows(cohort['samples']))} · {cohort['warmups']} warmups",
            16,
            anchor="middle",
        )
        chart.text(x, 683, timestamp, 14, anchor="middle")
    chart.text(
        38,
        727,
        "Milestones in implementation order; horizontal spacing is not elapsed time. Open point = small n=3 screen.",
        16,
    )
    chart.text(
        38,
        752,
        "Reference buffers the utterance; later runs stream. Inputs, outputs, RNG and transport vary. First PCM ≠ speaker onset.",
        16,
    )
    chart.text(
        38,
        775,
        "* SDPA timestamp is receipt recorded_at; MLX timestamps are run starts. Source rows + hashes: benchmarks/breeze/measurements.json",
        14,
    )
    return chart.finish()


def precision(data: dict[str, object]) -> str:
    cohorts = cohort_map(data)
    chart = SVG(
        "Breeze matched precision comparison",
        "Four precision arms, 18 timed cases each. Int8 lowers steady RTF but ASR flags increase; no listening acceptance.",
        555,
    )
    chart.text(38, 44, "Weight precision / matched input comparison", 29, "#0f172a")
    chart.text(
        38,
        75,
        "18 timed cases + 3 warmups per arm · CFG 4 · BF16 activations / KV · FP32 codec",
        18,
    )
    chart.text(
        38,
        108,
        "Sep 05 · 11:50-11:56 UTC · same prompts, voice instructions and seeds; sampled outputs differ",
        17,
    )
    chart.text(38, 156, "Backbone / depth weights", 17)
    chart.text(325, 156, "p95 steady-state RTF ↓", 19, "#0f172a")
    chart.text(1000, 148, "ASR word errors", 16, anchor="middle")
    chart.text(1000, 170, "screen, not listening", 14, anchor="middle")
    for tick in (0, 0.4, 0.8, 1.2):
        x = 325 + tick * 460
        chart.line(x, 183, x, 427, "#94a3b8" if tick == 0.8 else "#cbd5e1", dash=tick == 0.8)
        chart.text(x, 452, f"{tick:g}", 16, anchor="middle")
    chart.text(325 + 0.8 * 460, 476, "0.8 throughput target", 14, anchor="middle")
    labels = ("BF16 / BF16", "Int8 / BF16", "BF16 / Int8", "Int8 / Int8")
    for index, (arm, label) in enumerate(zip(ARMS, labels, strict=True)):
        cohort = cohorts[f"precision-{arm}"]
        value = metric(cohort, "steady_rtf")
        y = 190 + index * 60
        chart.text(38, y + 25, label, 21, "#0f172a")
        chart.bar(325, y, value * 460, "#0f766e" if arm == "int8" else "#64748b")
        chart.text(337 + value * 460, y + 25, f"{value:.3f}", 20, "#0f172a")
        screen = obj(cohort["asr_screen"])
        chart.text(
            1000,
            y + 25,
            f"{screen['word_errors']} / {screen['reference_words']}",
            20,
            anchor="middle",
        )
    reduction = 1 - metric(cohorts["precision-int8"], "steady_rtf") / metric(
        cohorts["precision-bf16"], "steady_rtf"
    )
    chart.text(
        38,
        513,
        f"Int8 / Int8: {reduction:.1%} lower p95 steady RTF than BF16 / BF16; quality flags remain unresolved.",
        20,
        "#0f766e",
    )
    chart.text(
        38,
        540,
        "Nearest-rank p95 (with n=18, the maximum). These are producer measurements, not end-to-end audible latency.",
        16,
    )
    return chart.finish()


def summary(data: dict[str, object]) -> str:
    lines = [
        "# Recorded measurements",
        "",
        "Generated by `scripts/render_breeze_benchmarks.py`; nearest-rank p95, warmups excluded.",
        "",
        "| Cohort | Timed / warmups | Audio seconds | First PCM p95 (s) | Total RTF p95 | Steady RTF p95 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for cohort in rows(data["cohorts"]):
        samples = rows(cohort["samples"])
        steady = (
            f"{metric(cohort, 'steady_rtf'):.6f}" if "steady_rtf" in samples[0] else "not recorded"
        )
        duration = sum(number(sample["audio_s"]) for sample in samples)
        lines.append(
            f"| {cohort['id']} | {len(samples)} / {cohort['warmups']} | {duration:.2f} | "
            f"{metric(cohort, 'first_pcm_s'):.6f} | {metric(cohort, 'total_rtf'):.6f} | {steady} |"
        )
    cycles = rows(obj(data["startup"])["cycles"])
    lines.extend(["", "## Process startup (ranges, not p95)", ""])
    ready = [number(cycle["launch_to_ready_s"]) for cycle in cycles]
    lines.append(f"- {len(cycles)} launches: {min(ready):.3f}-{max(ready):.3f} s to ready.")
    for kind in ("first", "warm"):
        times = [
            number(request["request_to_first_pcm_s"])
            for cycle in cycles
            for request in rows(cycle["requests"])
            if request["kind"] == kind
        ]
        lines.append(
            f"- {len(times)} {kind} requests: {min(times):.3f}-{max(times):.3f} s to first PCM."
        )
    return "\n".join([*lines, ""])


def render(data: dict[str, object]) -> dict[str, str]:
    return {
        "progression.svg": progression(data),
        "precision.svg": precision(data),
        "results.md": summary(data),
    }


class Options(argparse.Namespace):
    extract: bool = False
    check: bool = False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--extract", action="store_true", help="Re-export original local JSON receipts"
    )
    _ = parser.add_argument("--check", action="store_true", help="Verify outputs without writing")
    args = parser.parse_args(namespace=Options())
    data_path = OUTPUT / "measurements.json"
    data = extract() if args.extract else read(data_path)
    products = render(data)
    if args.extract:
        products["measurements.json"] = (
            json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )
    for name, content in products.items():
        path = OUTPUT / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Stale benchmark artifact: {path}")
        else:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(content, encoding="utf-8")
    print(
        f"{'Verified' if args.check else 'Rendered'} {len(products)} benchmark artifacts; no inference"
    )


if __name__ == "__main__":
    main()
