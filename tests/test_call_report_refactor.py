"""Regression tests for the explicit, date-aware Call Report ratio creator."""

import ast
import math
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import callreports as functions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CALL_REPORT_DIR = PROJECT_ROOT / "src" / "call reports"
sys.path.insert(0, str(CALL_REPORT_DIR))

import Call_Reports_v4_0 as ratios  # noqa: E402


class RecordingRow:
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
    ratios.create_ratio_entries(recorder)
    row = {column: 10.0 for column in recorder.columns}
    row.update(recorder.values)
    if values:
        row.update(values)
    return row


class ImportedRatioCreatorTests(unittest.TestCase):
    def test_ratio_creator_imports_domain_classes_and_defines_none(self):
        source_path = CALL_REPORT_DIR / "Call_Reports_v4_0.py"
        tree = ast.parse(source_path.read_text())
        class_definitions = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "callreports"
            for alias in node.names
        }

        self.assertEqual([], class_definitions)
        self.assertEqual(
            {"CallReport_031", "CallReport_051", "QuarterCache", "safe_divide"},
            imported_names,
        )

    def test_form_names_match_domestic_and_consolidated_columns(self):
        domestic_row = RecordingRow({"RCON0211": 4.0})
        consolidated_row = RecordingRow({"RCFD0211": 6.0})

        domestic = functions.CallReport_051(domestic_row)
        consolidated = functions.CallReport_031(consolidated_row)

        self.assertEqual(4.0, domestic.Securities.USTreasuries("htm", "ac"))
        self.assertEqual(6.0, consolidated.Securities.USTreasuries("htm", "ac"))
        self.assertIn("RCON0211", domestic_row.columns)
        self.assertIn("RCFD0211", consolidated_row.columns)

    def test_both_explicit_entries_have_the_canonical_schema(self):
        entry1, entry2 = ratios.create_ratio_entries(RecordingRow())

        self.assertEqual(79, len(ratios.FEATURE_COLUMNS))
        self.assertEqual(ratios.FEATURE_COLUMNS, tuple(entry1))
        self.assertEqual(ratios.FEATURE_COLUMNS, tuple(entry2))
        self.assertIn("RC-Item10-Item12", entry2)
        self.assertNotIn("RCB-0213-0111", entry2)

    def test_both_forms_use_the_domestic_rc_e_schedule(self):
        row = RecordingRow(
            {
                "RCONB549": 5.0,
                "RCON2215": 20.0,
                "RCFDB549": 99.0,
                "RCFD2215": 100.0,
            }
        )

        entry1, entry2 = ratios.create_ratio_entries(row)

        self.assertEqual(0.25, entry1["RCE-B549-2215"])
        self.assertEqual(0.25, entry2["RCE-B549-2215"])
        self.assertNotIn("RCFDB549", row.columns)
        self.assertNotIn("RCFD2215", row.columns)

    def test_missingness_uses_pandas_scalar_rules(self):
        self.assertTrue(ratios.is_missing(pd.NA))
        self.assertTrue(ratios.is_missing(pd.NaT))
        self.assertTrue(ratios.is_missing(math.nan))
        self.assertFalse(ratios.is_missing(0.0))
        self.assertFalse(ratios.is_missing(""))

    def test_consolidated_treasury_and_intangible_ratios_are_correct(self):
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
        _, entry2 = ratios.create_ratio_entries(row)

        self.assertEqual(3.0, entry2["RCB-0213-0211"])
        self.assertAlmostEqual(20.0 / 95.0, entry2["RC-Item10-Item12"])

    def test_mortgage_ratio_calls_imported_schedule_functions(self):
        row = RecordingRow(
            {"RCONG300": 1.0, "RCONG304": 2.0, "RCONG308": 3.0}
        )
        entry1, _ = ratios.create_ratio_entries(row)

        self.assertEqual(1.0 / 6.0, entry1["RCB-G300-item4a"])
        self.assertEqual(2.0 / 6.0, entry1["RCB-G304-Item4a"])
        self.assertEqual(3.0 / 6.0, entry1["RCB-G308-Item4a"])

    def test_processing_uses_consolidated_entry_when_domestic_is_missing(self):
        values = {
            "RCONHT53": math.nan,
            "RCFDHT53": 5.0,
            "RCFD0211": 4.0,
            "RCFD0213": 12.0,
        }
        result = ratios.process_dataframe(
            pd.DataFrame([complete_source_row(values)])
        )
        selected = None if result.empty else result.iloc[0]

        self.assertIsNotNone(selected)
        self.assertEqual(3.0, selected["RCB-0213-0211"])

    def test_processing_uses_domestic_entry_when_consolidated_is_missing(self):
        values = {
            "RCONHT53": 5.0,
            "RCFDHT53": math.nan,
            "RCON0211": 4.0,
            "RCON0213": 12.0,
        }

        result = ratios.process_dataframe(
            pd.DataFrame([complete_source_row(values)])
        )
        selected = None if result.empty else result.iloc[0]

        self.assertIsNotNone(selected)
        self.assertEqual(3.0, selected["RCB-0213-0211"])

    def test_processing_keeps_domestic_entry_when_missing_counts_tie(self):
        values = {
            "RCON0211": 4.0,
            "RCON0213": 12.0,
            "RCFD0211": 4.0,
            "RCFD0213": 8.0,
        }

        result = ratios.process_dataframe(
            pd.DataFrame([complete_source_row(values)])
        )
        selected = result.iloc[0]

        self.assertEqual(3.0, selected["RCB-0213-0211"])

    def test_processing_does_not_use_ht53_as_a_form_gate(self):
        values = {
            "RCONHT53": math.nan,
            "RCFDHT53": math.nan,
        }

        result = ratios.process_dataframe(
            pd.DataFrame([complete_source_row(values)])
        )
        selected = None if result.empty else result.iloc[0]

        self.assertIsNotNone(selected)

    def test_processing_discards_row_when_no_ratio_is_usable(self):
        row = complete_source_row()
        identity = {"IDRSSD", "RCON9999", "FDIC Certificate Number"}
        for column in row:
            if column not in identity:
                row[column] = math.nan

        result = ratios.process_dataframe(pd.DataFrame([row]))

        self.assertTrue(result.empty)
        self.assertEqual(list(ratios.FEATURE_COLUMNS), result.columns.tolist())

    def test_dataframe_processing_preserves_schema_and_deduplicates(self):
        first = complete_source_row({"IDRSSD": 7, "FDIC Certificate Number": 70})
        second = dict(first)
        second["RCONHT53"] = math.nan

        result = ratios.process_dataframe(pd.DataFrame([first, second]))

        self.assertEqual(1, len(result))
        self.assertEqual(list(ratios.FEATURE_COLUMNS), result.columns.tolist())
        self.assertEqual(7, result.iloc[0]["IDRSSD"])

    def test_file_processing_writes_one_canonical_row(self):
        frame = pd.DataFrame([complete_source_row()])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv"
            output = root / "output.csv"
            frame.to_csv(source, index=False)

            result = pd.read_csv(ratios.process_file(source, output))

        self.assertEqual(1, len(result))
        self.assertEqual(list(ratios.FEATURE_COLUMNS), result.columns.tolist())


if __name__ == "__main__":
    unittest.main()
