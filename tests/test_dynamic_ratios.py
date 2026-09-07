"""Tests for direct date-aware Call Report changes."""

import importlib.util
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "ratios" / "Dynamic_Ratios.py"
SPEC = importlib.util.spec_from_file_location("dynamic_ratios", MODULE_PATH)
dynamic_ratios = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dynamic_ratios)


class CertificateHistory:
    dates = {
        "P1Q": 20240930,
        "P2Q": 20240630,
        "P3Q": 20240331,
    }

    def __init__(self, frames=None):
        if frames is None:
            frames = {
                20240930: self._frame(101, 10),
                20240630: self._frame(102, 10),
                20240331: self._frame(103, 10),
            }
        self.frames = frames

    @staticmethod
    def _frame(rssd, certificate):
        return pd.DataFrame(
            {"FDIC Certificate Number": [certificate]},
            index=pd.Index([rssd], name="IDRSSD"),
        )

    def resolve(self, anchor, date):
        if int(anchor) != 20241231:
            return None
        return self.dates.get(date)

    def frame(self, actual):
        return self.frames.get(actual)


class DynamicRatiosTests(unittest.TestCase):
    def test_builds_existing_column_names_and_merges_on_cert(self):
        current = pd.DataFrame(
            {
                "CERT": [10, 20],
                "RCON9999": [20241231, 20241231],
                "ratio": [2.0, 5.0],
            }
        )
        p1q = pd.DataFrame({"CERT": [20, 10], "ratio": [0.0, 1.0]})
        p2q = pd.DataFrame({"CERT": [10, 20], "ratio": [4.0, 10.0]})
        p3q = pd.DataFrame({"CERT": [10, 20], "ratio": [1.0, 2.5]})

        result = dynamic_ratios.build_dynamic_report(
            current,
            p1q,
            p2q,
            p3q,
            ratio_columns=("ratio",),
        )

        self.assertEqual(
            [
                "CERT",
                "RCON9999",
                "ratio_q0",
                "ratio_q0q1",
                "ratio_q0q2",
                "ratio_q0q3",
            ],
            result.columns.tolist(),
        )
        self.assertEqual([1.0, 0.0], result["ratio_q0q1"].tolist())
        self.assertEqual([-0.5, -0.5], result["ratio_q0q2"].tolist())
        self.assertEqual([1.0, 1.0], result["ratio_q0q3"].tolist())

    def test_missing_history_remains_missing(self):
        current = pd.DataFrame(
            {
                "CERT": [10],
                "RCON9999": [20241231],
                "ratio": [2.0],
            }
        )
        missing = pd.DataFrame(columns=("CERT", "ratio"))

        result = dynamic_ratios.build_dynamic_report(
            current,
            missing,
            missing,
            missing,
            ratio_columns=("ratio",),
        )

        self.assertTrue(math.isnan(result.loc[0, "ratio_q0q1"]))
        self.assertTrue(math.isnan(result.loc[0, "ratio_q0q2"]))
        self.assertTrue(math.isnan(result.loc[0, "ratio_q0q3"]))

    def test_rejects_duplicate_certificate_keys(self):
        current = pd.DataFrame(
            {
                "CERT": [10],
                "RCON9999": [20241231],
                "ratio": [2.0],
            }
        )
        duplicate = pd.DataFrame(
            {"CERT": [10, 10], "ratio": [1.0, 2.0]}
        )
        valid = pd.DataFrame({"CERT": [10], "ratio": [1.0]})

        with self.assertRaises(pd.errors.MergeError):
            dynamic_ratios.build_dynamic_report(
                current,
                duplicate,
                valid,
                valid,
                ratio_columns=("ratio",),
            )

    def test_maps_certificate_to_the_historical_rssd(self):
        source = pd.DataFrame(
            {
                "IDRSSD": [900],
                "RCON9999": [20241231],
                "FDIC Certificate Number": [10],
            }
        )
        historical = pd.DataFrame(
            {"FDIC Certificate Number": [20, 10]},
            index=pd.Index([900, 123], name="IDRSSD"),
        )
        history = CertificateHistory({20240930: historical})

        roots = dynamic_ratios._certificate_roots(
            source,
            history,
            "P1Q",
        )

        self.assertEqual([123], roots["IDRSSD"].tolist())
        self.assertEqual([20241231], roots["RCON9999"].tolist())
        self.assertEqual(
            [10],
            roots["FDIC Certificate Number"].tolist(),
        )

    def test_unmapped_certificate_does_not_create_a_zero_history_row(self):
        source = pd.DataFrame(
            {
                "IDRSSD": [900],
                "RCON9999": [20241231],
                "FDIC Certificate Number": [10],
            }
        )
        history = CertificateHistory(
            {20240930: CertificateHistory._frame(900, 20)}
        )

        roots = dynamic_ratios._certificate_roots(
            source,
            history,
            "P1Q",
        )

        self.assertTrue(roots.empty)

    def test_pipeline_calls_all_three_dates_and_writes_306_columns(self):
        feature_columns = dynamic_ratios.FEATURE_COLUMNS
        ratio_columns = dynamic_ratios.RATIO_COLUMNS
        current_row = {
            "IDRSSD": 11,
            "RCON9999": 20241231,
            "CERT": 10,
        }
        current_row.update({column: 4.0 for column in ratio_columns})

        calls = []

        def dated_report(frame, history=None, date="P0"):
            calls.append(
                (
                    date,
                    frame.iloc[0]["IDRSSD"],
                    frame.iloc[0]["RCON9999"],
                )
            )
            denominator = {"P1Q": 2.0, "P2Q": 1.0, "P3Q": 0.0}[date]
            row = dict(current_row)
            row["RCON9999"] = {
                "P1Q": 20240930,
                "P2Q": 20240630,
                "P3Q": 20240331,
            }[date]
            row.update({column: denominator for column in ratio_columns})
            return pd.DataFrame([row], columns=feature_columns)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cleaned = root / "Cleaned"
            interleaved = root / "Interleaved"
            output = root / "Dynamic"
            cleaned.mkdir()
            interleaved.mkdir()
            filename = "Cleaned_Call_Report_20241231.csv"
            pd.DataFrame(
                [
                    {
                        "IDRSSD": 11,
                        "RCON9999": 20241231,
                        "FDIC Certificate Number": 10,
                    }
                ]
            ).to_csv(
                cleaned / filename,
                index=False,
            )
            pd.DataFrame([current_row], columns=feature_columns).to_csv(
                interleaved / filename,
                index=False,
            )

            with mock.patch.object(
                dynamic_ratios,
                "process_dataframe",
                side_effect=dated_report,
            ):
                written = dynamic_ratios.build_dynamic_reports(
                    cleaned,
                    interleaved,
                    output,
                    history=CertificateHistory(),
                )

            result = pd.read_csv(written[0])

        expected_columns = ["CERT", "RCON9999"]
        expected_columns.extend(
            "{}_q0".format(column) for column in ratio_columns
        )
        for lag in (1, 2, 3):
            expected_columns.extend(
                "{}_q0q{}".format(column, lag)
                for column in ratio_columns
            )

        self.assertEqual(
            [
                ("P1Q", 101, 20241231),
                ("P2Q", 102, 20241231),
                ("P3Q", 103, 20241231),
            ],
            calls,
        )
        self.assertEqual(306, len(result.columns))
        self.assertEqual(expected_columns, result.columns.tolist())
        self.assertNotIn("IDRSSD", result.columns)
        self.assertNotIn("ACQ_CERT", result.columns)
        self.assertNotIn("IN_CERT", result.columns)
        self.assertEqual(
            "Dynamic_Cleaned_Call_Report_20241231.csv",
            written[0].name,
        )
        first_ratio = ratio_columns[0]
        self.assertEqual(1.0, result.loc[0, first_ratio + "_q0q1"])
        self.assertEqual(3.0, result.loc[0, first_ratio + "_q0q2"])
        self.assertEqual(0.0, result.loc[0, first_ratio + "_q0q3"])

    def test_ratio_dictionary_is_imported_not_recreated(self):
        source = MODULE_PATH.read_text()

        self.assertIn("from Call_Reports_v4_0 import", source)
        self.assertNotIn('"RCB-', source)
        self.assertNotIn("safe_divide", source)


if __name__ == "__main__":
    unittest.main()
