"""Tests for current-to-prior-quarter Call Report changes."""

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "ratios" / "Call_Reports_Dynamic_Ratios.py"
SPEC = importlib.util.spec_from_file_location("dynamic_ratios", MODULE_PATH)
dynamic_ratios = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dynamic_ratios)


class DynamicRatiosTests(unittest.TestCase):
    def test_builds_available_quarter_changes_in_lag_order(self):
        distributed = pd.DataFrame(
            {
                "CERT": [10, 20],
                "ratio": [2.0, 5.0],
                "ratio_20240331": [1.0, 0.0],
                "ratio_20231231": [4.0, 10.0],
            }
        )

        result = dynamic_ratios.build_dynamic_report(
            distributed, ["20240331", "20231231", "20230930"]
        )

        self.assertEqual(
            ["CERT", "CERT_q0", "ratio_q0", "ratio_q0q1", "ratio_q0q2"],
            result.columns.tolist(),
        )
        self.assertEqual([1.0, 0.0], result["ratio_q0q1"].tolist())
        self.assertEqual([-0.5, -0.5], result["ratio_q0q2"].tolist())

    def test_extracts_three_prior_quarters_from_filename(self):
        quarters = ["20240630", "20240331", "20231231", "20230930"]

        current, prior = dynamic_ratios.previous_quarters(
            "Distributed_Cleaned_Call_Report_20240630.csv", quarters
        )

        self.assertEqual("20240630", current)
        self.assertEqual(["20240331", "20231231", "20230930"], prior)


if __name__ == "__main__":
    unittest.main()
