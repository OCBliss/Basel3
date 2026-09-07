"""Exercise the calculation CLI with explicit PMFs and expected comparisons."""

import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "src/jsd/calculation/Material_events_JSD_basel3.py"
PAIRS = ("survivors_vs_failures", "survivors_vs_mergers", "mergers_vs_failures")


def write_pmfs(material, horizon, width):
    """Use different bin order, an extra zero bin, and pair-specific columns."""
    tables = {
        "Survivors": pd.DataFrame({
            "Bin": ["low", "high"], "ratio_q0": [2, 0],
            "zero": [0, 0], "only_survivors_failures": [1, 0],
            "survivors_only": [1, 0], "coerced": ["invalid", 2],
        }),
        "Failures": pd.DataFrame({
            "Bin": ["high", "low", "extra"], "ratio_q0": [3, 0, 0],
            "zero": [0, 0, 0], "only_survivors_failures": [1, 0, 0],
            "failures_only": [1, 0, 0], "coerced": [4, 0, None],
        }),
        "Mergers": pd.DataFrame({
            "Bin": ["low", "high"], "ratio_q0": [5, 0],
            "zero": [0, 0], "mergers_only": [1, 0], "coerced": [0, 8],
        }),
    }
    for group, table in tables.items():
        folder = material / group / "JS Divergence" / ("Basel III T+%d" % horizon) / "Probabilities"
        folder.mkdir(parents=True, exist_ok=True)
        filename = "probabilities_Peer_Group_%s_Basel3_t%d_binned_%d.csv" % (group, horizon, width)
        table.to_csv(folder / filename, index=False)


class JSDCalculationTests(unittest.TestCase):
    def run_script(self, material, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--material-dir", str(material), *args],
            capture_output=True, text=True, timeout=30,
        )

    def test_selected_horizons_and_widths_exclude_stale_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory) / "Material Events"
            for horizon in (1, 3):
                for width in (20, 50):
                    write_pmfs(material, horizon, width)
                for group in ("Survivors", "Failures", "Mergers"):
                    folder = material / group / "JS Divergence" / ("Basel III T+%d" % horizon) / "Probabilities"
                    # These would fail if an unselected suffix were read.
                    for width in (30, 100, 120):
                        (folder / ("probabilities_stale_binned_%d.csv" % width)).write_text("not,a,PMF\n")
            result = self.run_script(material, "--horizons", "3", "1", "--bins", "20", "50")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected = {
                "BASEL III T+%d/JSD_%s_%d.csv" % (horizon, pair, width)
                for horizon in (1, 3) for pair in PAIRS for width in (20, 50)
            }
            actual = {str(path.relative_to(material / "JSD")) for path in (material / "JSD").rglob("*.csv")}
            self.assertEqual(actual, expected)
            for horizon in (1, 3):
                for width in (20, 50):
                    output = material / "JSD" / ("BASEL III T+%d" % horizon)
                    sf = pd.read_csv(output / ("JSD_survivors_vs_failures_%d.csv" % width))
                    self.assertEqual(sf.columns.tolist(),
                                     ["Bin", "ratio_q0", "zero", "only_survivors_failures", "coerced"])
                    self.assertEqual(sf["Bin"].tolist(), ["JSD"])
                    self.assertAlmostEqual(sf.loc[0, "ratio_q0"], math.sqrt(math.log(2)), places=12)
                    self.assertAlmostEqual(sf.loc[0, "only_survivors_failures"], math.sqrt(math.log(2)), places=12)
                    self.assertEqual(sf.loc[0, "zero"], 0)
                    self.assertEqual(sf.loc[0, "coerced"], 0)
                    sm = pd.read_csv(output / ("JSD_survivors_vs_mergers_%d.csv" % width))
                    mf = pd.read_csv(output / ("JSD_mergers_vs_failures_%d.csv" % width))
                    self.assertEqual(sm.columns.tolist(), ["Bin", "ratio_q0", "zero", "coerced"])
                    self.assertEqual(mf.columns.tolist(), ["Bin", "ratio_q0", "zero", "coerced"])
                    self.assertEqual(sm.loc[0, "ratio_q0"], 0)
                    self.assertAlmostEqual(mf.loc[0, "ratio_q0"], math.sqrt(math.log(2)), places=12)

    def test_single_custom_width_and_zero_pmf_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory) / "Material Events"
            write_pmfs(material, 2, 7)
            folder = material / "Failures/JS Divergence/Basel III T+2/Probabilities"
            target = next(folder.glob("*.csv"))
            failure = pd.read_csv(target)
            failure["ratio_q0"] = 0
            failure.to_csv(target, index=False)
            result = self.run_script(material, "--horizons", "2", "--bins", "7")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            files = list((material / "JSD").rglob("*.csv"))
            self.assertEqual(len(files), 3)
            output = pd.read_csv(material / "JSD/BASEL III T+2/JSD_survivors_vs_failures_7.csv")
            # The existing routine keeps a zero vector zero, then clamps only
            # inside KL. It does not replace that vector with a uniform PMF.
            self.assertAlmostEqual(output.loc[0, "ratio_q0"], math.sqrt(math.log(2) / 2), places=12)
            self.assertEqual(output.loc[0, "zero"], 0)

    def test_width_must_be_present_in_all_three_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory) / "Material Events"
            write_pmfs(material, 4, 20)
            write_pmfs(material, 4, 30)
            merger = material / "Mergers/JS Divergence/Basel III T+4/Probabilities"
            next(merger.glob("*_binned_30.csv")).unlink()
            result = self.run_script(material, "--horizons", "4", "--bins", "20", "30")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual({p.name for p in (material / "JSD").rglob("*.csv")},
                             {"JSD_%s_20.csv" % pair for pair in PAIRS})

    def test_required_selection_and_validation_precede_writes(self):
        invalid = (
            (), ("--horizons", "1"), ("--bins", "20"),
            ("--horizons", "0", "--bins", "20"),
            ("--horizons", "5", "--bins", "20"),
            ("--horizons", "1", "--bins", "0"),
            ("--horizons", "1", "--bins", "-1"),
            ("--horizons", "1", "--bins", "1.5"),
        )
        for args in invalid:
            with self.subTest(args=args), tempfile.TemporaryDirectory() as directory:
                material = Path(directory) / "Material Events"
                result = self.run_script(material, *args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse(material.exists())
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory) / "Material Events"
            result = self.run_script(material, "--help")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for option in ("--horizons", "--bins", "--material-dir"):
                self.assertIn(option, result.stdout)
            self.assertFalse(material.exists())


if __name__ == "__main__":
    unittest.main()
