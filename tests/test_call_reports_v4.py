"""Explicit v4 ratio calls through the installed CallReports API."""

import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src/call reports/Call_Reports_v4_0.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("explicit_call_reports_v4", SCRIPT)
v4 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v4
SPEC.loader.exec_module(v4)

# Source columns exercised by the original 76-ratio catalogue across its date
# branches. Keep fixture availability independent of the new implementation.
SOURCE_COLUMNS = """
RCFAA223 RCFAP840 RCFAP859 RCFD0071 RCFD0081 RCFD0211 RCFD0213
RCFD0426 RCFD1287 RCFD1289 RCFD1290 RCFD1293 RCFD1294 RCFD1295 RCFD1298
RCFD1754 RCFD1773 RCFD2143 RCFD2170 RCFD2930 RCFD2948 RCFD3123 RCFD3163
RCFD3190 RCFD3545 RCFD3548 RCFD5369 RCFD8496 RCFD8497 RCFD8499
RCFDA549 RCFDA550 RCFDA551 RCFDA552 RCFDA553 RCFDA554 RCFDA555 RCFDA556
RCFDA557 RCFDA558 RCFDA559 RCFDA560 RCFDB529 RCFDB696 RCFDB995 RCFDG105
RCFDG300 RCFDG301 RCFDG303 RCFDG304 RCFDG305 RCFDG307 RCFDG308 RCFDG309
RCFDG311 RCFDG312 RCFDG313 RCFDG315 RCFDG316 RCFDG317 RCFDG319 RCFDG320
RCFDG321 RCFDG323 RCFDG324 RCFDG325 RCFDG328 RCFDG329 RCFDHT50 RCFDHT51
RCFDHT53 RCFDJA22 RCFDJJ34 RCFDK142 RCFDK143 RCFDK146 RCFDK147 RCFDK150
RCFDK151 RCFDK154 RCFDK155 RCOAA223 RCOAP840 RCOAP859 RCON0071 RCON0081
RCON0211 RCON0213 RCON0352 RCON0426 RCON1287 RCON1289 RCON1290 RCON1293
RCON1294 RCON1295 RCON1298 RCON1754 RCON1773 RCON2143 RCON2170 RCON2200
RCON2202 RCON2203 RCON2213 RCON2215 RCON2216 RCON2385 RCON2930 RCON2948
RCON3123 RCON3163 RCON3190 RCON3545 RCON3548 RCON5369 RCON6648 RCON6810
RCON8496 RCON8497 RCON8499 RCONA549 RCONA550 RCONA551 RCONA552 RCONA553
RCONA554 RCONA555 RCONA556 RCONA557 RCONA558 RCONA559 RCONA560 RCONA579
RCONA580 RCONA581 RCONA582 RCONB529 RCONB549 RCONB550 RCONB551 RCONB696
RCONB993 RCONB995 RCOND962 RCOND967 RCOND987 RCONG105 RCONG300 RCONG301
RCONG303 RCONG304 RCONG305 RCONG307 RCONG308 RCONG309 RCONG311 RCONG312
RCONG313 RCONG315 RCONG316 RCONG317 RCONG319 RCONG320 RCONG321 RCONG323
RCONG324 RCONG325 RCONG328 RCONG329 RCONHK07 RCONHK08 RCONHK09 RCONHK10
RCONHT50 RCONHT51 RCONHT53 RCONJ473 RCONJ474 RCONJA22 RCONJJ34 RCONK142
RCONK143 RCONK146 RCONK147 RCONK150 RCONK151 RCONK154 RCONK155
""".split()


def source_row(date=20241231, rssd=11, **changes):
    row = dict.fromkeys(SOURCE_COLUMNS, 1.0)
    row.update({
        "IDRSSD": rssd, "RCON9999": date, "FDIC Certificate Number": rssd + 1000,
        "RCON0211": 12.0, "RCON0213": 18.0, "RCON1754": 40.0, "RCON1773": 60.0,
        "RCFD0211": 28.0, "RCFD0213": 35.0, "RCFD1754": 70.0,
        "RCONB549": 9.0, "RCON2215": 30.0, "RCON2200": 100.0,
        "RCFDB549": 900.0, "RCFD2215": 1000.0, "RCFD2200": 10000.0,
        "RCON2948": 180.0, "RCON3123": 20.0,
        "RCFD2948": 360.0, "RCFD3123": 40.0,
        "RCOAA223": 1000.0, "RCOAP840": 120.0, "RCOAP859": 100.0,
        "RCFAA223": 2000.0, "RCFAP840": 300.0, "RCFAP859": 260.0,
        "RCOND987": 400.0, "RCOND962": 30.0, "RCOND967": 20.0,
    })
    for prefix, first, values in (
        ("RCONA", 549, (1, 2, 3, 4, 5, 6)),
        ("RCFDA", 549, (5, 4, 3, 2, 1, 6)),
        ("RCONA", 555, (6, 5, 4, 3, 2, 1)),
        ("RCFDA", 555, (3, 1, 2, 4, 5, 6)),
    ):
        row.update({prefix + str(first + offset): float(value)
                    for offset, value in enumerate(values)})
    row.update(changes)
    return row


def root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


class ExplicitV4SourceTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SCRIPT.read_text())
        self.creator = next(node for node in self.tree.body
                            if isinstance(node, ast.FunctionDef)
                            and node.name == "create_ratio_entries")
        self.entries = {}
        for node in self.creator.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.entries[target.id] = node.value

    def test_both_complete_literal_entries_preserve_the_76_ratio_schema(self):
        self.assertEqual({"entry_051", "entry_031"}, set(self.entries))
        self.assertEqual(79, len(v4.FEATURE_COLUMNS))
        self.assertEqual(("IDRSSD", "RCON9999", "CERT"), v4.FEATURE_COLUMNS[:3])
        for name, entry in self.entries.items():
            with self.subTest(entry=name):
                self.assertTrue(all(isinstance(key, ast.Constant) for key in entry.keys))
                keys = tuple(key.value for key in entry.keys)
                self.assertEqual(v4.FEATURE_COLUMNS, keys)
                self.assertEqual(79, len(set(keys)))
        self.assertEqual(152, sum(len(entry.keys) - 3 for entry in self.entries.values()))

    def test_every_ratio_names_its_form_and_the_original_domestic_route(self):
        for entry_name, entry in self.entries.items():
            for key, expression in zip(entry.keys, entry.values):
                expected = {"report_051"} if entry_name == "entry_051" else {"report_031"}
                if entry_name == "entry_031" and key.value.startswith("RCE-"):
                    expected = {"report_051"}
                elif entry_name == "entry_031" and key.value == "RC-2200-Item21":
                    expected = {"report_051", "report_031"}
                calls = [node for node in ast.walk(expression)
                         if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
                roots = {root_name(node.func) for node in calls}
                with self.subTest(entry=entry_name, ratio=key.value):
                    self.assertEqual(expected, roots)
                    for call in calls:
                        self.assertTrue(any(keyword.arg == "date"
                                            and isinstance(keyword.value, ast.Name)
                                            and keyword.value.id == "date"
                                            for keyword in call.keywords))
        for node in ast.walk(self.creator):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.assertIn(target.id, {"row", "report_051", "report_031", "entry_051", "entry_031"})
                        if target.id == "row":
                            self.assertEqual("dict", node.value.func.id)
                            self.assertEqual("row", node.value.args[0].id)
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id.startswith("build_entry")
                             for node in ast.walk(self.creator)))

    def test_caller_imports_the_existing_api_without_embedding_it(self):
        self.assertFalse(any(isinstance(node, ast.ClassDef) for node in ast.walk(self.tree)))
        imported_api = {
            alias.name
            for node in ast.walk(self.tree)
            if isinstance(node, ast.ImportFrom) and node.module == "callreports"
            for alias in node.names
        }
        self.assertTrue({"CallReport_031", "CallReport_051", "QuarterCache", "safe_divide"}.issubset(imported_api))
        allowed = {"argparse", "pathlib", "sys", "pandas", "callreports", "__future__"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(0, node.level)
                self.assertIn(node.module.split(".")[0], allowed)
            elif isinstance(node, ast.FunctionDef):
                self.assertNotIn("dynamic", node.name.lower())
                self.assertNotIn(node.name, {"safe_divide", "_row_value", "_init_lags", "get_row"})
        api = sys.modules["callreports"]
        self.assertEqual("callreports.definitions", api.CallReport_031.__module__)
        self.assertIs(api.CallReport_031, v4.CallReport_031)
        self.assertIs(api.CallReport_051, v4.CallReport_051)
        self.assertIs(api.QuarterCache, v4.QuarterCache)
        self.assertIs(api.safe_divide, v4.safe_divide)


class V4NumericalTests(unittest.TestCase):
    def test_forms_keep_separate_securities_maturities_and_capital(self):
        domestic, consolidated = v4.create_ratio_entries(source_row())
        expected = (
            {"RCB-0211-1754": 12 / 40, "RCB-0213-0211": 18 / 12,
             "RCB-A549-itemM2a": 1 / 21, "RCB-A555-itemM2b": 6 / 21,
             "RCRI-P840-A223": 120 / 1000, "RCRI-P859-A223": 100 / 1000,
             "RCRI-P840-RWA+": 120 / 1002.31, "RCRI-P859-RWA+": 100 / 1002.31,
             "RCRI-ZRWA-A223": 400 / 1000, "RCRI-ZRWA-RWA": 400 / 1002.31,
             "RCRI-ZRWA-RWA+": 393 / 1002.31, "RCRI-ZRWA-RWA++": 7 / 400},
            {"RCB-0211-1754": 28 / 70, "RCB-0213-0211": 35 / 28,
             "RCB-A549-itemM2a": 5 / 21, "RCB-A555-itemM2b": 3 / 21,
             "RCRI-P840-A223": 300 / 2000, "RCRI-P859-A223": 260 / 2000,
             "RCRI-P840-RWA+": 300 / 2002.88, "RCRI-P859-RWA+": 260 / 2002.88,
             "RCRI-ZRWA-A223": 400 / 2000, "RCRI-ZRWA-RWA": 400 / 2002.88,
             "RCRI-ZRWA-RWA+": 391 / 2002.88, "RCRI-ZRWA-RWA++": 9 / 400},
        )
        for form, entry, values in zip(("051", "031"), (domestic, consolidated), expected):
            for ratio, value in values.items():
                with self.subTest(form=form, ratio=ratio):
                    self.assertAlmostEqual(value, entry[ratio])

    def test_consolidated_entry_uses_domestic_deposits_and_consolidated_liabilities(self):
        domestic, consolidated = v4.create_ratio_entries(source_row())
        self.assertAlmostEqual(9 / 30, domestic["RCE-B549-2215"])
        self.assertAlmostEqual(9 / 30, consolidated["RCE-B549-2215"])
        self.assertNotEqual(900 / 1000, consolidated["RCE-B549-2215"])
        self.assertAlmostEqual(100 / 200, domestic["RC-2200-Item21"])
        self.assertAlmostEqual(100 / 400, consolidated["RC-2200-Item21"])
        self.assertNotEqual(10000 / 400, consolidated["RC-2200-Item21"])

    def test_historical_calls_keep_the_bank_quarter_and_each_forms_values(self):
        current = source_row()
        prior = source_row(20240930, RCON0211=8.0, RCFD0211=7.0, RCONB549=3.0)
        other_bank = source_row(20240930, rssd=22, RCON0211=999.0, RCFD0211=888.0)
        history = v4.QuarterCache(
            map_file=pd.DataFrame([{"P0": 20241231, "P1Q": 20240930}]),
            frames={20240930: pd.DataFrame([other_bank, prior])},
        )
        lagged = v4.create_ratio_entries(current, history=history, date="P1Q")
        for entry in lagged:
            self.assertEqual((11, 20240930, 1011), tuple(entry[key] for key in v4.FEATURE_COLUMNS[:3]))
            self.assertAlmostEqual(3 / 30, entry["RCE-B549-2215"])
        self.assertAlmostEqual(8 / 40, lagged[0]["RCB-0211-1754"])
        self.assertAlmostEqual(7 / 70, lagged[1]["RCB-0211-1754"])
        self.assertEqual(20241231, current["RCON9999"])
        for form in (v4.CallReport_031, v4.CallReport_051):
            report = form(current, history=history)
            self.assertIs(current, report.get_row("P0"))
            self.assertIs(report.get_row("P1Q"), report.get_row("P1Q"))

    def test_historical_date_selects_its_own_deposit_reporting_rule(self):
        current = source_row(20170331, RCONHK07=25.0, RCONA579=90.0, RCON6648=40.0, RCONJ473=60.0)
        prior = source_row(20161231, RCONHK07=70.0, RCONA579=3.0, RCON6648=40.0, RCONJ473=60.0)
        history = v4.QuarterCache(
            map_file=pd.DataFrame([{"P0": 20170331, "P1Q": 20161231}]),
            frames={20161231: pd.DataFrame([prior])},
        )
        for entry in v4.create_ratio_entries(current, history=history):
            self.assertAlmostEqual(25 / 100, entry["RCE-HK07-savings"])
        for entry in v4.create_ratio_entries(current, history=history, date="P1Q"):
            self.assertAlmostEqual(3 / 100, entry["RCE-HK07-savings"])

    def test_zero_denominator_and_missing_numerator_remain_distinct(self):
        self.assertEqual(0.0, v4.safe_divide(12.0, 0.0))
        self.assertTrue(pd.isna(v4.safe_divide(float("nan"), 0.0)))
        entries = v4.create_ratio_entries(source_row(RCON1754=0.0, RCFD0211=float("nan")))
        self.assertEqual(0.0, entries[0]["RCB-0211-1754"])
        self.assertTrue(pd.isna(entries[1]["RCB-0211-1754"]))

    def test_copied_caller_runs_with_the_installed_package_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "src/call reports/Call_Reports_v4_0.py"
            script.parent.mkdir(parents=True)
            shutil.copyfile(SCRIPT, script)
            inputs = root / "input"
            outputs = root / "output"
            elsewhere = root / "elsewhere"
            inputs.mkdir()
            elsewhere.mkdir()
            name = "Cleaned_Call_Report_20241231.csv"
            pd.DataFrame([source_row()]).to_csv(inputs / name, index=False)
            pre2014_name = "Cleaned_Call_Report_20130630.csv"
            pre2014 = source_row(20130630)
            for column in (
                "RCOAA223", "RCOAP840", "RCOAP859", "RCFAA223", "RCFAP840", "RCFAP859",
            ):
                del pre2014[column]
            pd.DataFrame([pre2014]).to_csv(inputs / pre2014_name, index=False)
            original_input = (inputs / pre2014_name).read_bytes()
            calendar = root / "quarter_flag.csv"
            pd.DataFrame([{"P0": 20241231, "P1Q": 20240930, "Quarter": 4}]).to_csv(calendar, index=False)
            completed = subprocess.run(
                [sys.executable, "-I", str(script), "--input-dir", str(inputs),
                 "--output-dir", str(outputs), "--quarter-map", str(calendar)],
                cwd=elsewhere, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            result = pd.read_csv(outputs / name)
            self.assertEqual(list(v4.FEATURE_COLUMNS), list(result.columns))
            self.assertEqual([11], result["IDRSSD"].tolist())
            self.assertEqual([20241231], result["RCON9999"].tolist())
            self.assertEqual([1011], result["CERT"].tolist())
            pre2014_result = pd.read_csv(outputs / pre2014_name)
            self.assertEqual(list(v4.FEATURE_COLUMNS), list(pre2014_result.columns))
            self.assertEqual([20130630], pre2014_result["RCON9999"].tolist())
            self.assertTrue(pre2014_result.filter(like="RCRI-").isna().all().all())
            other_ratios = [column for column in v4.FEATURE_COLUMNS[3:] if not column.startswith("RCRI-")]
            self.assertEqual(68, len(other_ratios))
            self.assertTrue(pre2014_result[other_ratios].notna().all().all())
            self.assertEqual(original_input, (inputs / pre2014_name).read_bytes())
            self.assertEqual({script}, set(root.rglob("*.py")))


if __name__ == "__main__":
    unittest.main()
