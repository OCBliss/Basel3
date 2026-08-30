"""Tests for the distributed Call Report cleaner."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "ratios" / "Clean_Distributed_Ratios.py"
SPEC = importlib.util.spec_from_file_location("clean_distributed", MODULE_PATH)
clean_distributed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clean_distributed)


class CleanDistributedRatiosTests(unittest.TestCase):
    def test_fills_missing_values_only_for_populated_bank_rows(self):
        report = pd.DataFrame(
            {
                "IDRSSD": [10, None],
                "CERT": [100, None],
                "ratio": [None, None],
            }
        )

        cleaned = clean_distributed.clean_distributed_frame(report)

        self.assertEqual(0, cleaned.loc[0, "ratio"])
        self.assertTrue(pd.isna(cleaned.loc[1, "ratio"]))
        self.assertTrue(pd.isna(cleaned.loc[1, "CERT"]))

    def test_writes_each_raw_report_with_the_same_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_dir = root / "RAW"
            cleaned_dir = root / "Cleaned"
            raw_dir.mkdir()
            source = raw_dir / "Distributed_Cleaned_Call_Report_20240630.csv"
            pd.DataFrame({"IDRSSD": [10], "ratio": [None]}).to_csv(
                source, index=False
            )

            written = clean_distributed.clean_distributed_reports(
                raw_dir, cleaned_dir
            )
            result = pd.read_csv(written[0])

        self.assertEqual([source.name], [path.name for path in written])
        self.assertEqual(0, result.loc[0, "ratio"])


if __name__ == "__main__":
    unittest.main()
