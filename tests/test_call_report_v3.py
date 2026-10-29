"""Regression tests for the installed, date-aware CallReports API and ratios."""

import ast
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import pandas as pd

import callreports as dated


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CALL_REPORT_DIR = PROJECT_ROOT / "src" / "call reports"
sys.path.insert(0, str(CALL_REPORT_DIR))

import Call_Reports_v4_0 as dated_ratios  # noqa: E402


class RecordingRow:
    """Return a harmless value while recording every requested source column."""

    def __init__(self, values=None):
        self.values = {
            "IDRSSD": 1,
            "RCON9999": 20241231,
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
    dated_ratios.create_ratio_entries(recorder)
    row = {column: 10.0 for column in recorder.columns}
    row.update(recorder.values)
    if values:
        row.update(values)
    return row


def report_row(
    reporting_date,
    trading_assets,
    treasury,
    deposit_numerator=5.0,
    deposit_denominator=20.0,
    rssd=11,
):
    values = {
        "IDRSSD": rssd,
        "RCON9999": reporting_date,
        "FDIC Certificate Number": rssd + 1000,
        "RCON3545": trading_assets,
        "RCFD3545": trading_assets + 0.5,
        "RCON0211": treasury,
        "RCFD0211": treasury + 1.0,
        "RCONB549": deposit_numerator,
        "RCON2215": deposit_denominator,
        "RCOAA223": trading_assets * 10.0,
    }
    for code in range(549, 561):
        values["RCONA{}".format(code)] = trading_assets + code - 548
    return complete_source_row(values)


def augmented_risk_weighted_assets(row, maturity_prefix, capital_prefix):
    values = [
        row["{}{}".format(maturity_prefix, code)]
        for code in range(549, 561)
    ]
    return row["{}A223".format(capital_prefix)] + (
        0.15 * values[5]
        + 0.10 * values[4]
        + 0.08 * values[3]
        + 0.15 * values[11]
        + 0.10 * values[10]
        + 0.08 * values[9]
    )


class DatedCallReportFixture(unittest.TestCase):
    def setUp(self):
        self.rows = {
            20241231: report_row(20241231, 40.0, 400.0, 9.0, 10.0),
            20240930: report_row(20240930, 30.0, 300.0, 5.0, 20.0),
            20240630: report_row(20240630, 20.0, 200.0, 4.0, 20.0),
            20240331: report_row(20240331, 10.0, 100.0, 3.0, 20.0),
            20231231: report_row(20231231, 8.0, 80.0, 2.0, 20.0),
            20230930: report_row(20230930, 6.0, 60.0, 1.0, 20.0),
        }
        other_bank = report_row(
            20240930,
            999.0,
            9990.0,
            rssd=22,
        )
        frames = {
            date: pd.DataFrame([row])
            for date, row in self.rows.items()
            if date != 20241231
        }
        frames[20240930] = pd.DataFrame(
            [self.rows[20240930], other_bank]
        )

        quarter_map = pd.DataFrame(
            [
                (20241231, 20240930, 20240630, 20240331, 20231231, 4),
                (20240930, 20240630, 20240331, 20231231, 20230930, 3),
                (20240630, 20240331, 20231231, 20230930, 20230630, 2),
                (20240331, 20231231, 20230930, 20230630, 20230331, 1),
            ],
            columns=("P0", "P1Q", "P2Q", "P3Q", "P1Y", "Quarter"),
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.map_file = Path(self.temp_dir.name) / "quarter_map.csv"
        quarter_map.to_csv(self.map_file, index=False)
        self.history = dated.QuarterCache(
            map_file=self.map_file,
            frames=frames,
        )


class CallReportSourceAuditTests(unittest.TestCase):
    @staticmethod
    def domain_classes(tree):
        roots = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        required = ("CallReport_051", "CallReport_031")

        def walk(node, prefix):
            qualified = prefix + node.name
            yield qualified, node
            for child in node.body:
                if isinstance(child, ast.ClassDef):
                    for item in walk(child, qualified + "."):
                        yield item

        classes = []
        for name in required:
            if name not in roots:
                raise AssertionError("Missing domain class {}".format(name))
            classes.extend(walk(roots[name], ""))

        qualified_names = {name for name, _ in classes}
        for report_name in required:
            for schedule_name in ("Maturities", "RegulatoryCapital"):
                expected = report_name + "." + schedule_name
                if expected not in qualified_names:
                    raise AssertionError(
                        "Missing per-form domain class {}".format(expected)
                    )
        return classes

    @staticmethod
    def has_forwarded_date(call):
        return any(
            keyword.arg == "date"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "date"
            for keyword in call.keywords
        )

    def test_every_domain_method_has_the_date_contract(self):
        tree = ast.parse((PROJECT_ROOT / "src/callreports/definitions.py").read_text())
        classes = self.domain_classes(tree)
        methods = [
            method
            for _, class_node in classes
            for method in class_node.body
            if isinstance(method, ast.FunctionDef)
            and method.name != "__init__"
        ]
        self.assertGreater(len(classes), 20)
        self.assertGreater(len(methods), 200)

        failures = []
        for class_name, class_node in classes:
            for method in class_node.body:
                if not isinstance(method, ast.FunctionDef):
                    continue
                if method.name == "__init__":
                    continue

                keyword_names = [arg.arg for arg in method.args.kwonlyargs]
                date_default = None
                if "date" in keyword_names:
                    date_default = method.args.kw_defaults[
                        keyword_names.index("date")
                    ]
                if isinstance(date_default, ast.Constant):
                    default_value = date_default.value
                elif isinstance(date_default, ast.Str):
                    default_value = date_default.s
                else:
                    default_value = None
                default_is_p0 = default_value == "P0"
                if (
                    method.args.vararg is None
                    or method.args.kwarg is None
                    or not default_is_p0
                ):
                    failures.append(
                        "{}.{}:{}".format(
                            class_name,
                            method.name,
                            method.lineno,
                        )
                    )

        self.assertEqual([], failures)

    def test_domain_values_do_not_read_a_bound_row_directly(self):
        tree = ast.parse((PROJECT_ROOT / "src/callreports/definitions.py").read_text())
        failures = []
        for class_name, class_node in self.domain_classes(tree):
            for method in class_node.body:
                if not isinstance(method, ast.FunctionDef):
                    continue
                if method.name == "__init__":
                    continue
                for node in ast.walk(method):
                    if not isinstance(node, ast.Attribute):
                        continue
                    if not isinstance(node.ctx, ast.Load):
                        continue
                    if node.attr != "row":
                        continue

                    root = node.value
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    if isinstance(root, ast.Name) and root.id == "self":
                        failures.append(
                            "{}.{}:{}".format(
                                class_name,
                                method.name,
                                node.lineno,
                            )
                        )

        self.assertEqual([], failures)

    def test_internal_domain_calls_forward_the_active_date(self):
        tree = ast.parse((PROJECT_ROOT / "src/callreports/definitions.py").read_text())
        classes = self.domain_classes(tree)
        method_names = {
            method.name
            for _, class_node in classes
            for method in class_node.body
            if isinstance(method, ast.FunctionDef)
            and method.name != "__init__"
        }
        failures = []
        for class_name, class_node in classes:
            for method in class_node.body:
                if not isinstance(method, ast.FunctionDef):
                    continue
                if method.name == "__init__":
                    continue
                for call in ast.walk(method):
                    if not isinstance(call, ast.Call):
                        continue
                    if not isinstance(call.func, ast.Attribute):
                        continue
                    if call.func.attr not in method_names:
                        continue
                    if not self.has_forwarded_date(call):
                        failures.append(
                            "{}.{} -> {}:{}".format(
                                class_name,
                                method.name,
                                call.func.attr,
                                call.lineno,
                            )
                        )

        self.assertEqual([], failures)

    def test_ratio_domain_calls_all_name_their_date(self):
        tree = ast.parse(
            (CALL_REPORT_DIR / "Call_Reports_v4_0.py").read_text()
        )
        creator = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "create_ratio_entries"
        )
        entries = {
            target.id: node.value
            for node in creator.body
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.assertEqual({"entry_051", "entry_031"}, set(entries))
        self.assertEqual(152, sum(len(entry.keys) - 3 for entry in entries.values()))
        for entry in entries.values():
            self.assertEqual(dated_ratios.FEATURE_COLUMNS, tuple(key.value for key in entry.keys))
        domain_calls = [
            node
            for entry in entries.values()
            for node in ast.walk(entry)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        ]
        failures = [
            "{}:{}".format(call.func.attr, call.lineno)
            for call in domain_calls
            if not self.has_forwarded_date(call)
        ]

        self.assertGreater(len(domain_calls), 200)
        self.assertEqual([], failures)

    def test_ratio_caller_has_no_form_selection_branch(self):
        tree = ast.parse(
            (CALL_REPORT_DIR / "Call_Reports_v4_0.py").read_text()
        )
        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }

        self.assertNotIn("select_report_entry", function_names)
        self.assertNotIn("build_entry", function_names)
        self.assertTrue({"use_031", "use_051"}.isdisjoint(loaded_names))

    def test_domain_and_caller_do_not_import_obsolete_versions(self):
        forbidden = {"Call_Report_v2_1", "Call_Report_v3", "Call_Reports_v3_1"}

        def imported_modules(source_path):
            tree = ast.parse(source_path.read_text())
            modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(
                        alias.name.split(".")[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module.split(".")[0])
            return modules

        domain_imports = imported_modules(PROJECT_ROOT / "src/callreports/definitions.py")
        caller_imports = imported_modules(
            CALL_REPORT_DIR / "Call_Reports_v4_0.py"
        )

        self.assertTrue(forbidden.isdisjoint(domain_imports))
        self.assertTrue(forbidden.isdisjoint(caller_imports))
        self.assertIn("callreports", caller_imports)


class DatedCallReportTests(DatedCallReportFixture):
    def test_p0_methods_match_the_unchanged_domain_formulas(self):
        row = self.rows[20241231]
        forms = (
            (
                dated.CallReport_051,
                "RCON",
                "RCONA",
                "RCOA",
            ),
            (
                dated.CallReport_031,
                "RCFD",
                "RCFDA",
                "RCFA",
            ),
        )
        for report_class, prefix, maturity_prefix, capital_prefix in forms:
            report = report_class(row, history=self.history)

            self.assertEqual(row["IDRSSD"], report.RSSDID(date="P0"))
            self.assertEqual(row["RCON9999"], report.ReportingDate(date="P0"))
            expected_assets = (
                row["{}2170".format(prefix)]
                - row["{}JA22".format(prefix)]
                + row["{}3123".format(prefix)]
            )
            self.assertEqual(
                expected_assets,
                report.BalanceSheet.TotalAssets(date="P0"),
            )
            self.assertEqual(
                row["{}0211".format(prefix)],
                report.Securities.USTreasuries(
                    "htm",
                    valuation="ac",
                    date="P0",
                ),
            )
            self.assertEqual(
                augmented_risk_weighted_assets(
                    row,
                    maturity_prefix,
                    capital_prefix,
                ),
                report.RegulatoryCapital.AugmentedRiskWeightedAssets(
                    date="P0"
                ),
            )

    def test_relative_dates_are_anchored_to_each_rows_p0(self):
        q4_report = dated.CallReport_051(
            self.rows[20241231],
            history=self.history,
        )
        q3_report = dated.CallReport_051(
            self.rows[20240930],
            history=self.history,
        )

        self.assertEqual(20240930, q4_report.ReportingDate(date="P1Q"))
        self.assertEqual(20240630, q4_report.ReportingDate(date="P2Q"))
        self.assertEqual(20231231, q4_report.ReportingDate(date="P1Y"))
        self.assertEqual(20240630, q3_report.ReportingDate(date="P1Q"))
        self.assertEqual(20240331, q3_report.ReportingDate(date="P2Q"))
        self.assertEqual(20230930, q3_report.ReportingDate(date="P1Y"))

    def test_history_lookup_keeps_the_bank_and_caches_native_reports(self):
        report = dated.CallReport_051(
            self.rows[20241231],
            history=self.history,
        )

        first = report.get_row("P1Q")
        second = report.get_row("P1Q")
        self.assertIs(first, second)
        self.assertEqual(11, report.RSSDID(date="P1Q"))
        self.assertEqual(30.0, report.BalanceSheet.TradingAssets(date="P1Q"))
        self.assertNotEqual(
            999.0,
            report.BalanceSheet.TradingAssets(date="P1Q"),
        )

    def test_missing_bank_history_remains_missing_instead_of_zero(self):
        current = report_row(20241231, 70.0, 700.0, rssd=77)
        report = dated.CallReport_051(current, history=self.history)

        lagged = report.get_row("P1Q")
        raw_value = lagged["RCON3545"]
        proxied_value = report.BalanceSheet.TradingAssets(date="P1Q")

        self.assertEqual(77, report.RSSDID(date="P1Q"))
        self.assertEqual(20240930, report.ReportingDate(date="P1Q"))
        self.assertTrue(pd.isna(raw_value))
        self.assertTrue(pd.isna(proxied_value))
        self.assertNotEqual(0, raw_value)

    def test_missing_anchor_date_does_not_leak_p0_into_history(self):
        current = report_row(20241231, 123.0, 700.0, rssd=77)
        current["RCON9999"] = pd.NA
        report = dated.CallReport_051(current, history=self.history)

        lagged = report.get_row("P1Q")

        self.assertIs(report.get_row("P0"), current)
        self.assertIsNot(lagged, current)
        self.assertTrue(pd.isna(lagged["RCON3545"]))
        self.assertTrue(
            pd.isna(report.BalanceSheet.TradingAssets(date="P1Q"))
        )

    def test_nested_calls_and_method_arguments_use_the_dated_native_object(self):
        report = dated.CallReport_051(
            self.rows[20241231],
            history=self.history,
        )
        expected_lagged = augmented_risk_weighted_assets(
            self.rows[20240930],
            "RCONA",
            "RCOA",
        )
        expected_current = augmented_risk_weighted_assets(
            self.rows[20241231],
            "RCONA",
            "RCOA",
        )

        lagged_composite = (
            report.RegulatoryCapital.AugmentedRiskWeightedAssets(date="P1Q")
        )
        self.assertEqual(
            expected_lagged,
            lagged_composite,
        )
        self.assertNotEqual(
            expected_current,
            lagged_composite,
        )
        self.assertEqual(
            300.0,
            report.Securities.USTreasuries(
                "htm",
                valuation="ac",
                date="P1Q",
            ),
        )

    def test_global_changes_are_relative_to_the_requested_anchor(self):
        report = dated.CallReport_051(
            self.rows[20241231],
            history=self.history,
        )
        global_uc = dated.Global_uc(report)
        trading_assets = report.BalanceSheet.TradingAssets

        self.assertAlmostEqual(
            (40.0 - 30.0) / 30.0,
            global_uc.CHANGE1Q(trading_assets, date="P0"),
        )
        self.assertAlmostEqual(
            (30.0 - 20.0) / 20.0,
            global_uc.CHANGE1Q(trading_assets, date="P1Q"),
        )
        self.assertAlmostEqual(
            (40.0 - 8.0) / 8.0,
            global_uc.CHANGE1Y(trading_assets, date="P0"),
        )
        self.assertAlmostEqual(
            (400.0 - 300.0) / 300.0,
            global_uc.CHANGE1Q(
                report.Securities.USTreasuries,
                "htm",
                valuation="ac",
                date="P0",
            ),
        )

    def test_cavg_window_uses_the_resolved_anchors_calendar_quarter(self):
        report = dated.CallReport_051(
            self.rows[20241231],
            history=self.history,
        )
        global_uc = dated.Global_uc(report)
        trading_assets = report.BalanceSheet.TradingAssets

        self.assertEqual(
            25.0,
            global_uc.CAVG04X(trading_assets, date="P0"),
        )
        self.assertEqual(
            20.0,
            global_uc.CAVG04X(trading_assets, date="P1Q"),
        )

    def test_global_math_preserves_missing_history_and_values(self):
        absent_bank = report_row(
            20241231,
            70.0,
            700.0,
            rssd=77,
        )
        report = dated.CallReport_051(absent_bank, history=self.history)
        global_uc = dated.Global_uc(report)
        trading_assets = report.BalanceSheet.TradingAssets

        for change in (
            global_uc.CHANGE1Q,
            global_uc.CHANGE2Q,
            global_uc.CHANGE3Q,
            global_uc.CHANGE1Y,
        ):
            self.assertTrue(pd.isna(change(trading_assets, date="P0")))
        self.assertTrue(
            pd.isna(global_uc.CAVG04X(trading_assets, date="P0"))
        )

        frames = {
            date: pd.DataFrame([row])
            for date, row in self.rows.items()
            if date != 20241231
        }
        missing_prior_value = dict(self.rows[20240930])
        missing_prior_value["RCON3545"] = float("nan")
        frames[20240930] = pd.DataFrame([missing_prior_value])
        incomplete_history = dated.QuarterCache(
            map_file=self.map_file,
            frames=frames,
        )
        report = dated.CallReport_051(
            self.rows[20241231],
            history=incomplete_history,
        )
        global_uc = dated.Global_uc(report)
        trading_assets = report.BalanceSheet.TradingAssets
        self.assertTrue(pd.isna(global_uc.CHANGE1Q(trading_assets)))
        self.assertTrue(pd.isna(global_uc.CAVG04X(trading_assets)))

        missing_current = dict(self.rows[20241231])
        missing_current["RCON3545"] = float("nan")
        report = dated.CallReport_051(
            missing_current,
            history=self.history,
        )
        global_uc = dated.Global_uc(report)
        trading_assets = report.BalanceSheet.TradingAssets
        total_assets = report.BalanceSheet.TotalAssets
        self.assertTrue(pd.isna(global_uc.ANN(trading_assets)))
        self.assertTrue(
            pd.isna(global_uc.PCTANN(trading_assets, total_assets))
        )
        self.assertTrue(
            pd.isna(global_uc.PCTOFANN(trading_assets, total_assets))
        )
        self.assertTrue(
            pd.isna(global_uc.PCTOF(trading_assets, total_assets))
        )
        self.assertTrue(pd.isna(global_uc.PCT(trading_assets, total_assets)))

        self.assertEqual(0.0, global_uc._zero(None))
        self.assertEqual(0.0, global_uc._zero(float("nan")))

    def test_one_calculation_can_mix_current_and_lagged_periods(self):
        report = dated.CallReport_051(
            self.rows[20241231],
            history=self.history,
        )

        result = dated.safe_divide(
            report.BalanceSheet.TradingAssets(date="P0"),
            report.BalanceSheet.TradingAssets(date="P1Q"),
        )

        self.assertAlmostEqual(40.0 / 30.0, result)

    def test_ratio_caller_uses_051_deposits_and_keeps_031_native_values(self):
        current = self.rows[20241231]
        row_031 = dict(current)
        row_031.update(
            {
                "RCON2200": 80.0,
                "RCONB549": 4.0,
                "RCON2202": 6.0,
                "RCON2203": 8.0,
                "RCONB551": 10.0,
                "RCON2213": 12.0,
                "RCON2216": 14.0,
                "RCON2215": 20.0,
                "RCONB550": 3.0,
                "RCON2385": 12.0,
                "RCONJ473": 6.0,
                "RCFD0211": 6.0,
                "RCFD1754": 12.0,
                "RCFD2948": 180.0,
                "RCFD3123": 20.0,
            }
        )
        for column in (
            "2200",
            "B549",
            "2202",
            "2203",
            "B551",
            "2213",
            "2216",
            "2215",
        ):
            row_031["RCFD" + column] = 999.0

        report_051 = dated.CallReport_051(current, history=self.history)
        report_031 = dated.CallReport_031(row_031, history=self.history)
        self.assertIsNot(
            report_051.DepositLiabilities,
            report_031.DepositLiabilities,
        )

        transaction_031 = report_031.DepositLiabilities.TransactionDeposits
        self.assertEqual(80.0, report_031.DepositLiabilities.ReportedTotal())
        self.assertEqual(4.0, transaction_031.Individuals())
        self.assertEqual(6.0, transaction_031.USGovt())
        self.assertEqual(8.0, transaction_031.StatesAndPolitical())
        self.assertEqual(10.0, transaction_031.CommercialBanks())
        self.assertEqual(12.0, transaction_031.ForeignBanks())
        self.assertEqual(14.0, transaction_031.ForeignGovt())
        self.assertEqual(20.0, transaction_031.ReportedTotal())

        with mock.patch.object(
            dated_ratios,
            "CallReport_051",
            return_value=report_051,
        ), mock.patch.object(
            dated_ratios,
            "CallReport_031",
            return_value=report_031,
        ):
            actual_p0 = dated_ratios.create_ratio_entries(
                current,
                history=self.history,
                date="P0",
            )
        self.assertEqual(dated_ratios.FEATURE_COLUMNS, tuple(actual_p0[0]))
        self.assertEqual(dated_ratios.FEATURE_COLUMNS, tuple(actual_p0[1]))
        self.assertEqual(20241231, actual_p0[0]["RCON9999"])
        expected_treasury = dated.safe_divide(
            report_051.Securities.USTreasuries(
                "htm", "ac", date="P0"
            ),
            report_051.Securities.Total("htm", "ac", date="P0"),
        )
        self.assertEqual(
            expected_treasury,
            actual_p0[0]["RCB-0211-1754"],
        )
        self.assertEqual(0.9, actual_p0[0]["RCE-B549-2215"])
        expected_domestic_deposits = {
            "RCE-B549-2215": 0.9,
            "RCE-2202-2215": 1.0,
            "RCE-2203-2215": 1.0,
            "RCE-B551-2215": 1.0,
            "RCE-2213-2215": 1.0,
            "RCE-2216-2215": 1.0,
            "RCE-2215-2200": 1.0,
            "RCE-B550-2385": 1.0,
            "RCE-2385-2200": 1.0,
            "RCE-itemM2a-2385": 2.0,
            "RCE-6648-2385": 1.0,
            "RCE-J473-2385": 1.0,
            "RCE-J474-2385": 1.0,
            "RCE-HK07-savings": 0.5,
            "RCE-HK08-savings": 0.5,
            "RCE-HK09-savings": 0.5,
            "RCE-HK10-savings": 0.5,
        }
        self.assertEqual(17, len(expected_domestic_deposits))
        for feature, expected in expected_domestic_deposits.items():
            with self.subTest(feature=feature):
                self.assertAlmostEqual(expected, actual_p0[0][feature])
                self.assertAlmostEqual(expected, actual_p0[1][feature])
        self.assertEqual(6.0 / 12.0, actual_p0[1]["RCB-0211-1754"])
        self.assertNotEqual(actual_p0[0]["RCB-0211-1754"], actual_p0[1]["RCB-0211-1754"])
        self.assertEqual(10.0 / 20.0, actual_p0[0]["RC-2200-Item21"])
        self.assertEqual(10.0 / 200.0, actual_p0[1]["RC-2200-Item21"])
        self.assertNotEqual(80.0 / 200.0, actual_p0[1]["RC-2200-Item21"])

        actual_p1q = dated_ratios.create_ratio_entries(
            current,
            history=self.history,
            date="P1Q",
        )
        self.assertEqual(20240930, actual_p1q[0]["RCON9999"])
        self.assertEqual(20240930, actual_p1q[1]["RCON9999"])
        self.assertEqual(0.25, actual_p1q[0]["RCE-B549-2215"])
        self.assertEqual(0.25, actual_p1q[1]["RCE-B549-2215"])
        self.assertNotEqual(0.9, actual_p1q[1]["RCE-B549-2215"])


if __name__ == "__main__":
    unittest.main()
