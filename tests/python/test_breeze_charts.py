from __future__ import annotations

import math
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET  # noqa: S405 -- only parses this test's generated SVG

from scripts import render_breeze_benchmarks as charts


class BreezeChartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = charts.read(charts.OUTPUT / "measurements.json")
        self.cohorts = charts.cohort_map(self.data)

    def test_nearest_rank_and_invalid_inputs(self) -> None:
        self.assertEqual(charts.p95([float(n) for n in range(1, 31)]), 29)
        self.assertEqual(charts.p95([float(n) for n in range(1, 19)]), 18)
        self.assertEqual(charts.p95([3, 1, 2]), 3)
        for values in ([], [math.nan], [math.inf]):
            with self.assertRaises(ValueError):
                charts.p95(values)
        for value in (True, "3", math.nan):
            with self.assertRaises(ValueError):
                charts.number(value)

    def test_all_selected_rows_and_provenance_present(self) -> None:
        self.assertEqual(len(self.cohorts), 18)
        self.assertEqual(sum(len(charts.rows(c["samples"])) for c in self.cohorts.values()), 397)
        for cohort in self.cohorts.values():
            receipt = charts.obj(cohort["receipt"])
            self.assertRegex(str(receipt["sha256"]), r"^[a-f0-9]{64}$")
            self.assertGreater(charts.number(receipt["bytes"]), 0)
            self.assertTrue(str(receipt["path"]).startswith(".artifacts/breeze-performance/"))
            for sample in charts.rows(cohort["samples"]):
                self.assertGreater(charts.number(sample["audio_s"]), 0)
                self.assertGreater(charts.number(sample["first_pcm_s"]), 0)
                self.assertAlmostEqual(
                    charts.number(sample["total_s"]) / charts.number(sample["audio_s"]),
                    charts.number(sample["total_rtf"]),
                )
                self.assertIsNone(sample.get("failure"))
        self.assertNotIn(
            "/Users/", (charts.OUTPUT / "measurements.json").read_text(encoding="utf-8")
        )

    def test_missing_baseline_fields_are_not_invented(self) -> None:
        for name in ("reference", "cached"):
            self.assertIsNone(charts.obj(self.cohorts[name]["clock"])["value"])
        reference = self.cohorts["reference"]
        self.assertEqual(charts.obj(reference["identity"])["runtime"], {})
        for sample in charts.rows(reference["samples"]):
            self.assertNotIn("steady_rtf", sample)
            self.assertNotIn("seed", sample)
        self.assertAlmostEqual(charts.metric(reference, "total_rtf"), 9.95428494418796)
        self.assertAlmostEqual(charts.metric(reference, "first_pcm_s"), 49.16518591699423)

    def test_later_short_inputs_match_but_outputs_change(self) -> None:
        def cases(name: str) -> list[tuple[object, object, object]]:
            return [
                (s["prompt"], s["instruction"], s["seed"])
                for s in charts.rows(self.cohorts[name]["samples"])
            ]

        self.assertEqual(cases("sdpa"), cases("mlx"))
        self.assertEqual(cases("mlx"), cases("https-control-short"))
        self.assertNotEqual(
            [s["audio_s"] for s in charts.rows(self.cohorts["sdpa"]["samples"])],
            [s["audio_s"] for s in charts.rows(self.cohorts["mlx"]["samples"])],
        )

    def test_precision_pairs_flags_and_reduction(self) -> None:
        reference = charts.rows(self.cohorts["precision-bf16"]["samples"])
        for arm, errors in zip(charts.ARMS, (3, 5, 6, 7), strict=True):
            cohort = self.cohorts[f"precision-{arm}"]
            samples = charts.rows(cohort["samples"])
            self.assertEqual(len(samples), 18)
            self.assertEqual(cohort["warmups"], 3)
            self.assertEqual(cohort["asr_screen"], {"word_errors": errors, "reference_words": 189})
            self.assertEqual(
                sum(charts.number(charts.obj(s["asr_screen"])["word_errors"]) for s in samples),
                errors,
            )
            for left, right in zip(reference, samples, strict=True):
                for key in ("prompt", "seed", "instruction"):
                    self.assertEqual(left[key], right[key])
                self.assertIs(right["completed"], True)
                self.assertIs(right["eos_reached"], True)
        reduction = 1 - charts.metric(self.cohorts["precision-int8"], "steady_rtf") / charts.metric(
            self.cohorts["precision-bf16"], "steady_rtf"
        )
        self.assertAlmostEqual(reduction * 100, 36.72, places=2)

    def test_weight_inventory_is_selected_bytes_not_process_memory(self) -> None:
        settings = charts.obj(charts.obj(self.cohorts["precision-int8"]["identity"])["settings"])
        backbone = charts.obj(settings["backbone_quantization"])
        depth = charts.obj(settings["depth_quantization"])
        self.assertEqual(
            charts.number(backbone["record_count"]) + charts.number(depth["record_count"]), 280
        )
        original = charts.number(backbone["covered_original_bytes"]) + charts.number(
            depth["covered_original_bytes"]
        )
        packed = charts.number(backbone["packed_bytes"]) + charts.number(depth["packed_bytes"])
        self.assertEqual(original, 3485466624)
        self.assertEqual(packed, 1851654144)
        self.assertEqual((1 - packed / original) * 100, 46.875)

    def test_https_counts_cache_and_resident_pairs(self) -> None:
        total = 0
        values: list[float] = []
        for suite in ("short", "long", "warm-companion", "bright-guide", "grounded-mentor"):
            control = self.cohorts[f"https-control-{suite}"]
            resident = self.cohorts[f"https-resident-{suite}"]
            for cohort in (control, resident):
                samples = charts.rows(cohort["samples"])
                total += len(samples)
                self.assertEqual(len(samples), 6 if suite == "long" else 30)
                values.append(charts.metric(cohort, "steady_rtf"))
                for sample in samples:
                    self.assertEqual(sample["cache"], "BYPASS")
                    self.assertIs(sample["completed"], True)
                    self.assertIs(sample["cancelled"], False)
            for left, right in zip(
                charts.rows(control["samples"]), charts.rows(resident["samples"]), strict=True
            ):
                for key in ("prompt", "instruction", "seed", "pcm_sha256"):
                    self.assertEqual(left[key], right[key])
        self.assertEqual(total, 252)
        self.assertAlmostEqual(min(values), 0.685239, places=6)
        self.assertAlmostEqual(max(values), 0.698114, places=6)

    def test_startup_population_is_separate(self) -> None:
        cycles = charts.rows(charts.obj(self.data["startup"])["cycles"])
        self.assertEqual(len(cycles), 3)
        kinds = [request["kind"] for cycle in cycles for request in charts.rows(cycle["requests"])]
        self.assertEqual(kinds.count("first"), 3)
        self.assertEqual(kinds.count("warm"), 9)
        https = charts.obj(charts.obj(self.cohorts["https-control-short"]["identity"])["runtime"])
        self.assertNotEqual(cycles[0]["runtime_fingerprint"], https["runtime_fingerprint"])

    def test_generated_files_are_current_and_svg_is_self_contained(self) -> None:
        for name, content in charts.render(self.data).items():
            self.assertEqual((charts.OUTPUT / name).read_text(encoding="utf-8"), content)
            if name.endswith(".svg"):
                root = ET.fromstring(content)  # noqa: S314 -- trusted in-process generated XML
                self.assertEqual(root.attrib["role"], "img")
                self.assertEqual(root.attrib["viewBox"].split()[2], "1120")
                self.assertIsNotNone(root.find("{http://www.w3.org/2000/svg}desc"))
                self.assertNotIn("<script", content)
                self.assertNotIn("href=", content)

    def test_local_readme_links_exist_and_flecs_copy_removed(self) -> None:
        for path in (charts.ROOT / "README.md", charts.OUTPUT / "README.md"):
            content = path.read_text(encoding="utf-8")
            if path == charts.ROOT / "README.md":
                self.assertNotIn("flecs", content.lower())
            for match in re.finditer(r"\]\(([^)]+)\)", content):
                target = match.group(1)
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(), target)

    def test_check_rejects_missing_products_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with (
                patch.object(charts, "OUTPUT", output),
                patch.object(charts, "read", return_value=self.data),
                patch("sys.argv", ["render_breeze_benchmarks.py", "--check"]),
                self.assertRaisesRegex(SystemExit, "Stale benchmark artifact"),
            ):
                charts.main()
            self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
