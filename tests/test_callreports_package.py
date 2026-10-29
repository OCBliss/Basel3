"""Independent structured-data use and ZIP-to-schedule preparation contracts."""

from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import pandas as pd

from callreports import (
    CallReport_031, CallReport_051, QuarterCache,
    convert_txt_to_csv, merge_schedules, prepare_archive,
)


def quarter_files(stamp="03312024"):
    return {
        "FFIEC CDR Call Bulk POR " + stamp + ".txt":
            "IDRSSD\tFDIC Certificate Number\n101\t10\n202\t20\n",
        "FFIEC CDR Call Schedule ENT " + stamp + ".txt":
            "IDRSSD\tRCON9999\tRCON9224\n\tREPORT DATE\tBANK NAME\n202\t20240331\tBank B\n101\t20240331\tBank A\n",
        "FFIEC CDR Call Schedule RC " + stamp + ".txt":
            "IDRSSD\tRCON2170\tRCFD2170\tRCON3545\tRCFD3545\tRCONJA22\tRCON3123\tRCFDJA22\tRCFD3123\n\tASSETS\tASSETS\tTRADING\tTRADING\tADJUSTMENT\tALLOWANCE\tADJUSTMENT\tALLOWANCE\n101\t100\t200\t10\t40\t0\t0\t0\t0\n202\t500\t1000\t50\t200\t0\t0\t0\t0\n",
        "FFIEC CDR Call Schedule RCK " + stamp + ".txt":
            "IDRSSD\tRCONEXTRA\n\tANOTHER SCHEDULE\n101\t7\n202\t8\n",
        "Readme.txt": "FFIEC archive documentation, not a reporting schedule.\n",
    }


def write_zip(path, files=None):
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in (quarter_files() if files is None else files).items():
            archive.writestr(name, contents)
    return path


class StructuredCallReportTests(unittest.TestCase):
    def test_bank_row_supports_independent_user_selected_ratios_and_forms(self):
        row = {"IDRSSD": 101, "RCON9999": 20240331,
               "RCON2170": 100, "RCFD2170": 200,
               "RCONJA22": 5, "RCON3123": 10, "RCFDJA22": 10, "RCFD3123": 20,
               "RCON3545": 10, "RCFD3545": 40}
        for report_type, expected in [(CallReport_051, 10 / 105), (CallReport_031, 40 / 210)]:
            report = report_type(row)
            self.assertEqual(expected, report.BalanceSheet.TradingAssets(date="P0") /
                             report.BalanceSheet.TotalAssets(date="P0"))
        with self.assertRaises(KeyError):
            CallReport_051({"RCON9999": 20240331}).BalanceSheet.TotalAssets()

    def test_calendar_history_is_explicit_and_matches_banks_across_row_orders(self):
        current = pd.Series({"IDRSSD": 101, "RCON9999": 20240331, "RCON2170": 100,
                             "RCONJA22": 0, "RCON3123": 0})
        previous = pd.DataFrame({"IDRSSD": [202, 101], "RCON9999": [20231231] * 2,
                                 "RCON2170": [999, 80], "RCONJA22": [0, 0], "RCON3123": [0, 0]})
        history = QuarterCache(frames={20231231: previous})
        with mock.patch("pandas.read_csv", side_effect=AssertionError("unexpected filesystem dependency")):
            self.assertEqual(80, CallReport_051(current, history).BalanceSheet.TotalAssets(date="P1Q"))
            self.assertTrue(pd.isna(CallReport_051(current).BalanceSheet.TotalAssets(date="P1Q")))
        self.assertEqual(20230331, history.resolve(20240331, "P1Y"))
        self.assertEqual(20231231, history.resolve(20240630, "P2Q"))
        self.assertEqual(1, history.quarter(20240331))
        self.assertIsNone(history.resolve(20240229, "P1Q"))

    def test_historical_files_can_use_prepared_quarter_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quarter = root / "20231231"
            quarter.mkdir()
            pd.DataFrame({"IDRSSD": [101], "RCON9999": [20231231], "RCON2170": [80],
                          "RCONJA22": [0], "RCON3123": [0]}).to_csv(
                quarter / "Cleaned_Call_Report_20231231.csv", index=False)
            report = CallReport_051({"IDRSSD": 101, "RCON9999": 20240331, "RCON2170": 100,
                                     "RCONJA22": 0, "RCON3123": 0},
                                    QuarterCache(data_dir=root))
            self.assertEqual(80, report.BalanceSheet.TotalAssets(date="P1Q"))


class LocalBulkPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = write_zip(self.root / "quarter.zip")

    def test_zip_to_api_includes_all_schedules_and_joins_by_bank_identifier(self):
        before = self.archive.read_bytes()
        path = prepare_archive(self.archive, self.root / "prepared")
        table = pd.read_csv(path)
        self.assertEqual([202, 101], table["IDRSSD"].tolist())
        self.assertEqual([20, 10], table["FDIC Certificate Number"].tolist())
        self.assertEqual([500, 100], table["RCON2170"].tolist())
        self.assertEqual([8, 7], table["RCONEXTRA"].tolist())
        self.assertNotIn("RCON9224", table)
        self.assertEqual([20240331, 20240331], table["RCON9999"].tolist())
        self.assertEqual(500, CallReport_051(table.iloc[0]).BalanceSheet.TotalAssets())
        self.assertEqual(before, self.archive.read_bytes())
        with self.assertRaises(FileExistsError):
            prepare_archive(self.archive, self.root / "prepared")
        self.assertEqual([500, 100], pd.read_csv(path)["RCON2170"].tolist())

    def test_extracted_txt_can_be_converted_and_merged_separately(self):
        txt, schedules = self.root / "txt", self.root / "schedules"
        txt.mkdir()
        for name, value in quarter_files().items():
            (txt / name).write_text(value)
        self.assertEqual(3, len(convert_txt_to_csv(txt, schedules)))
        table = merge_schedules(schedules)
        self.assertEqual([500, 100], table["RCON2170"].tolist())
        self.assertEqual(2, len(table))

    def test_missing_por_and_duplicate_schedule_banks_fail_without_publishing(self):
        for kind in ("missing_por", "duplicate"):
            with self.subTest(kind=kind):
                files = quarter_files()
                if kind == "missing_por":
                    del files["FFIEC CDR Call Bulk POR 03312024.txt"]
                else:
                    files["FFIEC CDR Call Schedule RC 03312024.txt"] += "101\t300\t600\t30\t120\n"
                write_zip(self.archive, files)
                destination = self.root / kind
                with self.assertRaises(ValueError):
                    prepare_archive(self.archive, destination)
                self.assertFalse((destination / "20240331").exists())
                self.assertEqual([], list(destination.iterdir()))

    def test_zip_member_traversal_links_and_mixed_quarters_are_rejected(self):
        for kind in ("traversal", "link", "mixed"):
            with self.subTest(kind=kind):
                write_zip(self.archive)
                with zipfile.ZipFile(self.archive, "a") as archive:
                    if kind == "traversal":
                        archive.writestr("../escaped.txt", "invalid")
                    elif kind == "link":
                        member = zipfile.ZipInfo("link.txt")
                        member.create_system = 3
                        member.external_attr = (stat.S_IFLNK | 0o777) << 16
                        archive.writestr(member, "target")
                    else:
                        archive.writestr("FFIEC CDR Call Schedule RCO 06302024.txt", "IDRSSD\n101\n")
                destination = self.root / kind
                with self.assertRaises(ValueError):
                    prepare_archive(self.archive, destination)
                self.assertFalse((destination / "20240331").exists())
                self.assertFalse((self.root / "escaped.txt").exists())

    def test_module_cli_runs_from_an_unrelated_working_directory(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        completed = subprocess.run(
            [sys.executable, "-I", "-m", "callreports", "prepare", str(self.archive),
             "--output-dir", str(self.root / "cli")],
            cwd=elsewhere, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        result = pd.read_csv(completed.stdout.strip())
        self.assertEqual([500, 100], result["RCON2170"].tolist())

    def test_corrupt_zip_fails_without_publishing_a_quarter(self):
        payload = bytearray(self.archive.read_bytes())
        position = payload.index(b"IDRSSD\tFDIC Certificate Number")
        payload[position] ^= 1
        self.archive.write_bytes(payload)
        destination = self.root / "corrupt"
        with self.assertRaises(zipfile.BadZipFile):
            prepare_archive(self.archive, destination)
        self.assertEqual([], list(destination.iterdir()))



if __name__ == "__main__":
    unittest.main()
