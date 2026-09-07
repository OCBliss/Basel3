"""Check bin boundaries, unchanged normalization, and selected CLI outputs."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BINNING_FILE = ROOT / "src/jsd/binning/Material_events_JSD_binning_basel3.py"
PMF_FILE = ROOT / "src/jsd/pmf/Material_events_JSD_probabilities_basel3.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


binning = load_module("basel3_binning_test", BINNING_FILE)
pmf = load_module("basel3_pmf_test", PMF_FILE)


def boundary_frame():
    values = [-1, 0, 1, np.nextafter(2.0, 0), 2, np.nextafter(2.0, np.inf), np.nan]
    return pd.DataFrame({
        "CERT": [101] * len(values), "RCON9999": [20200331] * len(values),
        "ratio": values, "empty_ratio": [np.nan] * len(values),
    })


class JsdBinningTests(unittest.TestCase):
    def run_cli(self, script, arguments, cwd):
        result = subprocess.run([sys.executable, str(script), *arguments],
                                cwd=cwd, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_all_four_bin_counts_preserve_boundary_mass_without_empty_interval(self):
        for count in (20, 30, 50, 100):
            with self.subTest(bins1=count):
                result = binning.bin_ratios(boundary_frame(), binning.make_bin_edges(count))
                self.assertEqual(len(result), count + 5 + 1)
                self.assertEqual(result.columns.tolist(), ["ratio", "empty_ratio"])
                self.assertEqual(result["ratio"].sum(), 6)
                self.assertEqual(result["empty_ratio"].sum(), 0)
                expected = np.zeros(count + 6, dtype=int)
                expected[0] = 1                       # -1
                expected[count // 2] = 1              # 0
                expected[count] = 1                  # 1
                expected[-2] = 1                     # immediately below 2
                expected[-1] = 2                     # exactly 2 and immediately above 2
                np.testing.assert_array_equal(result["ratio"].values, expected)
                self.assertNotIn("[2.00, 2.00)", result.index)
                self.assertEqual(result.index[-1], "[2.00, inf)")

    def test_second_region_count_is_configurable(self):
        frame = pd.DataFrame({"CERT": [1, 2, 3], "RCON9999": [20200331] * 3,
                              "ratio": [1.1, 1.75, 2.0]})
        result = binning.bin_ratios(frame, binning.make_bin_edges(20, bins2=2, bins3=1))
        self.assertEqual(len(result), 23)
        self.assertEqual(result["ratio"].iloc[-3:].tolist(), [1, 1, 1])
        self.assertEqual(result["ratio"].sum(), 3)

    def test_pmf_normalizes_each_column_and_retains_zero_total_columns(self):
        source = pd.DataFrame({"Bin": ["a", "b", "c"],
                               "one": [2, 0, 6], "two": [0, 3, 1], "empty": [0, 0, 0]})
        with contextlib.redirect_stdout(io.StringIO()):
            actual = pmf.normalize_counts(source, "fixture.csv")
        expected = pd.DataFrame({"Bin": ["a", "b", "c"],
                                 "one": [0.25, 0, 0.75], "two": [0, 0.75, 0.25], "empty": [0, 0, 0]})
        pd.testing.assert_frame_equal(actual, expected)

    def test_cli_runs_t1_t3_and_ignores_unselected_bin_files(self):
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory) / "Material Events"
            frame = boundary_frame()
            # Use decimal values that survive CSV parsing on both sides of 2;
            # the in-memory boundary test checks the adjacent floating values.
            frame.loc[3, "ratio"] = 1.9
            frame.loc[5, "ratio"] = 2.1
            for group in ("Mergers", "Failures", "Survivors"):
                source_dir = material / group / "Horizons"
                source_dir.mkdir(parents=True)
                for horizon in (1, 3):
                    frame.to_csv(source_dir / f"Peer_Group_{group}_Basel3_t{horizon}.csv", index=False)
            self.run_cli(BINNING_FILE, ["--horizons", "1", "3", "--bins1", "20", "50",
                                       "--material-dir", str(material)], directory)
            self.assertEqual(len(list(material.glob("*/JS Divergence/*/Binned/*.csv"))), 12)
            for group in ("Mergers", "Failures", "Survivors"):
                for horizon in (1, 3):
                    binned_dir = material / group / "JS Divergence" / f"Basel III T+{horizon}" / "Binned"
                    # A nonselected suffix must not be mistaken for bins20 or opened.
                    (binned_dir / "unselected_binned_120.csv").write_text("invalid CSV", encoding="utf-8")
            self.run_cli(PMF_FILE, ["--horizons", "1", "3", "--bins", "20",
                                   "--material-dir", str(material)], directory)
            self.assertEqual(len(list(material.glob("*/JS Divergence/*/Probabilities/*.csv"))), 6)
            self.run_cli(PMF_FILE, ["--horizons", "1", "3", "--bins", "20", "50",
                                   "--material-dir", str(material)], directory)
            files = list(material.glob("*/JS Divergence/*/Probabilities/*.csv"))
            self.assertEqual(len(files), 12)
            for filename in files:
                result = pd.read_csv(filename)
                count = int(filename.stem.split("_")[-1])
                self.assertEqual(len(result), count + 6)
                self.assertAlmostEqual(result["ratio"].sum(), 1)
                self.assertEqual(result["empty_ratio"].sum(), 0)
                self.assertAlmostEqual(result["ratio"].iloc[-1], 2 / 6)
            for group in ("Mergers", "Failures", "Survivors"):
                for horizon in (2, 4):
                    self.assertFalse((material / group / "JS Divergence" / f"Basel III T+{horizon}").exists())

    def test_missing_selected_bin_is_not_satisfied_by_another_bin_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "peer_binned_120.csv").write_text("invalid CSV", encoding="utf-8")
            with self.assertRaisesRegex(FileNotFoundError, r"\[20\]"):
                pmf.selected_files(source, {20})

    def test_invalid_or_missing_selections_fail_before_writing(self):
        cases = [
            (BINNING_FILE, ["--bins1", "20"]),
            (BINNING_FILE, ["--horizons", "1"]),
            (BINNING_FILE, ["--horizons", "5", "--bins1", "20"]),
            (BINNING_FILE, ["--horizons", "1", "--bins1", "0"]),
            (BINNING_FILE, ["--horizons", "1", "--bins1", "20", "--bins2", "0"]),
            (BINNING_FILE, ["--horizons", "1", "--bins1", "20", "--bins3", "2"]),
            (PMF_FILE, ["--horizons", "1"]),
            (PMF_FILE, ["--bins", "20"]),
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            for script, arguments in cases:
                with self.subTest(script=script.name, arguments=arguments):
                    result = subprocess.run([sys.executable, str(script), *arguments,
                                             "--material-dir", str(output)],
                                            cwd=directory, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
