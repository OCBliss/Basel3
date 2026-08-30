"""Regression tests for the function-driven Call Report ratio builder."""

import math
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CALL_REPORT_DIR = PROJECT_ROOT / "src" / "call reports"
sys.path.insert(0, str(CALL_REPORT_DIR))

import Call_Report as functions  # noqa: E402
import Call_Report_v2_1 as builder  # noqa: E402


class RecordingRow:
    """Mapping that records source columns while supplying numeric defaults."""

    def __init__(self, values=None):
        self.values = {
            "IDRSSD": 1,
            "RCON9999": 20240331,
            "FDIC Certificate Number": 100,
        }
        if values:
            self.values.update(values)
        self.columns = set()

    def __getitem__(self, column):
        self.columns.add(column)
        return self.values.get(column, 10.0)


def complete_source_row(values=None):
    recorder = RecordingRow(values)
    domestic = functions.CallReport_031(recorder)
    builder.build_report_features(domestic, domestic)
    builder.build_report_features(functions.CallReport_051(recorder), domestic)
    complete = {column: 10.0 for column in recorder.columns}
    complete.update(recorder.values)
    if values:
        complete.update(values)
    return complete


class CallReportFunctionLayerTests(unittest.TestCase):
    def test_both_presentations_have_one_canonical_schema(self):
        row = RecordingRow()
        domestic = functions.CallReport_031(row)
        domestic_features = builder.build_report_features(domestic, domestic)
        consolidated_features = builder.build_report_features(
            functions.CallReport_051(row), domestic
        )

        self.assertEqual(79, len(builder.FEATURE_COLUMNS))
        self.assertEqual(builder.FEATURE_COLUMNS, tuple(domestic_features))
        self.assertEqual(builder.FEATURE_COLUMNS, tuple(consolidated_features))
        self.assertIn("RC-Item10-Item12", consolidated_features)
        self.assertNotIn("RCB-0213-0111", consolidated_features)

    def test_consolidated_treasury_and_intangible_ratios_are_not_shifted(self):
        row = RecordingRow(
            {
                "RCFD0211": 10.0,
                "RCFD0213": 30.0,
                "RCFD2143": 20.0,
                "RCFD2170": 100.0,
                "RCFDJA22": 10.0,
                "RCFD3123": 5.0,
            }
        )
        domestic = functions.CallReport_031(row)
        result = builder.build_report_features(functions.CallReport_051(row), domestic)

        self.assertEqual(3.0, result["RCB-0213-0211"])
        self.assertAlmostEqual(20.0 / 95.0, result["RC-Item10-Item12"])

    def test_mortgage_components_use_schedule_functions(self):
        row = RecordingRow(
            {"RCONG300": 1.0, "RCONG304": 2.0, "RCONG308": 3.0}
        )
        report = functions.CallReport_031(row)
        result = builder.build_report_features(report, report)

        self.assertEqual(1.0 / 6.0, result["RCB-G300-item4a"])
        self.assertEqual(2.0 / 6.0, result["RCB-G304-Item4a"])
        self.assertEqual(3.0 / 6.0, result["RCB-G308-Item4a"])

    def test_selector_uses_consolidated_values_when_domestic_is_missing(self):
        values = {
            "RCONHT53": math.nan,
            "RCFDHT53": 5.0,
            "RCFD0211": 4.0,
            "RCFD0213": 12.0,
        }
        selected = builder.select_report_features(complete_source_row(values))

        self.assertIsNotNone(selected)
        self.assertEqual(3.0, selected["RCB-0213-0211"])

    def test_dataframe_processing_deduplicates_ids_and_preserves_schema(self):
        first = complete_source_row({"IDRSSD": 7, "FDIC Certificate Number": 70})
        second = dict(first)
        second["RCONHT53"] = math.nan
        frame = pd.DataFrame([first, second])

        result = builder.process_dataframe(frame)

        self.assertEqual(1, len(result))
        self.assertEqual(list(builder.FEATURE_COLUMNS), result.columns.tolist())
        self.assertEqual(7, result.iloc[0]["IDRSSD"])

    def test_file_processing_is_explicit_and_testable(self):
        frame = pd.DataFrame([complete_source_row()])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv"
            output = root / "output" / "result.csv"
            frame.to_csv(source, index=False)

            written = builder.process_file(source, output)
            result = pd.read_csv(written)

        self.assertEqual(list(builder.FEATURE_COLUMNS), result.columns.tolist())
        self.assertEqual(1, len(result))


if __name__ == "__main__":
    unittest.main()
