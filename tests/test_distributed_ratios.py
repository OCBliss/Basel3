"""Tests for the distributed-lag report builder."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    PROJECT_ROOT / "src" / "ratios" / "Call_Reports_Distributed_Ratios.py"
)
SPEC = importlib.util.spec_from_file_location("distributed_ratios", MODULE_PATH)
distributed_ratios = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distributed_ratios)


class DistributedRatiosTests(unittest.TestCase):
    def test_builds_four_quarter_window(self):
        quarters = ["20241231", "20240930", "20240630", "20240331"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "interleaved"
            output_dir = root / "distributed"
            input_dir.mkdir()
            quarters_file = root / "quarters.csv"
            pd.DataFrame({"Quarters": quarters}).to_csv(quarters_file, index=False)

            for index, quarter in enumerate(quarters):
                pd.DataFrame(
                    {"CERT": [1, 2], "ratio": [index + 0.1, index + 0.2]}
                ).to_csv(
                    input_dir / f"Cleaned_Call_Report_{quarter}.csv", index=False
                )

            written = distributed_ratios.build_distributed_reports(
                input_dir, output_dir, quarters_file
            )

            self.assertEqual(1, len(written))
            result = pd.read_csv(written[0])
            self.assertEqual(
                [
                    "CERT",
                    "ratio",
                    "ratio_20240930",
                    "ratio_20240630",
                    "ratio_20240331",
                ],
                result.columns.tolist(),
            )
            self.assertEqual([0.1, 0.2], result["ratio"].tolist())
            self.assertEqual([3.1, 3.2], result["ratio_20240331"].tolist())

    def test_rejects_duplicate_certificate_keys(self):
        quarters = ["20241231", "20240930", "20240630", "20240331"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "interleaved"
            input_dir.mkdir()
            quarters_file = root / "quarters.csv"
            pd.DataFrame({"Quarters": quarters}).to_csv(quarters_file, index=False)
            for quarter in quarters:
                pd.DataFrame({"CERT": [1, 1], "ratio": [0.1, 0.2]}).to_csv(
                    input_dir / f"Cleaned_Call_Report_{quarter}.csv", index=False
                )

            with self.assertRaises(pd.errors.MergeError):
                distributed_ratios.build_distributed_reports(
                    input_dir, root / "output", quarters_file
                )

    def test_writes_partial_window_when_comparison_files_are_missing(self):
        quarters = ["20241231", "20240930", "20240630", "20240331"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "interleaved"
            input_dir.mkdir()
            quarters_file = root / "quarters.csv"
            pd.DataFrame({"Quarters": quarters}).to_csv(quarters_file, index=False)
            pd.DataFrame({"CERT": [1], "ratio": [0.5]}).to_csv(
                input_dir / "Cleaned_Call_Report_20241231.csv", index=False
            )

            written = distributed_ratios.build_distributed_reports(
                input_dir, root / "output", quarters_file
            )
            result = pd.read_csv(written[0])

        self.assertEqual(1, len(written))
        self.assertEqual(["CERT", "ratio"], result.columns.tolist())
        self.assertEqual(0.5, result.iloc[0]["ratio"])


if __name__ == "__main__":
    unittest.main()
