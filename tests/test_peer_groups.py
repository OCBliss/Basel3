"""Peer-group membership, CSV boundaries and explicit horizon selection."""

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    family: PROJECT_ROOT / "src" / "peer groups" / family / "Material_events_peer_group_basel3.py"
    for family in ("base", "horizons")
}


def load_script(family):
    spec = importlib.util.spec_from_file_location("peer_groups_" + family, SCRIPTS[family])
    module = importlib.util.module_from_spec(spec)
    original_import_path = sys.path[:]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_import_path
    return module


BASE = load_script("base")
HORIZONS = load_script("horizons")


class PeerGroupTests(unittest.TestCase):
    def run_script(self, family, root, arguments):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS[family]), *arguments], cwd=root,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_commands_require_valid_explicit_horizons_before_writing(self):
        for family in SCRIPTS:
            for arguments in ([], ["--horizons", "0"], ["--horizons", "5"]):
                with self.subTest(family=family, arguments=arguments), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS[family]), *arguments,
                         "--material-dir", str(root / "output")],
                        cwd=root, capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                    self.assertIn("--horizons", result.stderr)
                    self.assertEqual([], list(root.iterdir()))

    def test_selected_horizons_preserve_membership_duplicates_and_filename_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            material = root / "Material Events"
            inputs = root / "custom input"
            inputs.mkdir()
            # The first two rows are identical; both event flags are set.
            panel = pd.DataFrame({
                "CERT": [101, 101, 102, 103, 104],
                "RCON9999": [19990101] * 5,
                "ratio": [0.25, 0.25, float("nan"), -1.0, 3.0],
                "FAILURE_T1": [1, 1, 0, float("nan"), 0],
                "MERGER_T1": [1, 1, 0, float("nan"), 1],
                "FAILURE_T3": [0, 0, 1, 0, 1],
                "MERGER_T3": [1, 1, 0, 0, 1],
            })
            included = inputs / "Mergers_Call_Report_20200331.csv"
            excluded = inputs / "Mergers_Call_Report_20200630.csv"
            panel.to_csv(included, index=False)
            panel.assign(CERT=panel["CERT"] + 1000).to_csv(excluded, index=False)
            original_inputs = {path.name: path.read_bytes() for path in inputs.iterdir()}
            calendar = root / "selected quarters.csv"
            pd.DataFrame({"Quarters": [20200331]}).to_csv(calendar, index=False)

            self.run_script("base", root, [
                "--horizons", "1", "3", "--material-dir", str(material),
                "--input-dir", str(inputs),
            ])
            expected_rows = {
                (1, "Failures"): [0, 1], (1, "Mergers"): [0, 1, 4],
                (1, "Survivors"): [2, 3], (3, "Failures"): [2, 4],
                (3, "Mergers"): [0, 1, 4], (3, "Survivors"): [3],
            }
            for (horizon, group), rows in expected_rows.items():
                quarterly = material / group / "Horizons" / ("Basel III T+" + str(horizon))
                actual = pd.read_csv(quarterly / (group + "_Call_Report_20200331.csv"))
                pd.testing.assert_frame_equal(actual, panel.iloc[rows].reset_index(drop=True))
                self.assertTrue((quarterly / (group + "_Call_Report_20200630.csv")).is_file())

            self.run_script("horizons", root, [
                "--horizons", "1", "3", "--material-dir", str(material),
                "--quarter-map", str(calendar),
            ])
            for (horizon, group), rows in expected_rows.items():
                combined = material / group / "Horizons" / ("Peer_Group_{}_Basel3_t{}.csv".format(group, horizon))
                actual = pd.read_csv(combined)
                pd.testing.assert_frame_equal(actual, panel.iloc[rows].reset_index(drop=True))
                # Row dates deliberately disagree: the calendar selects filenames.
                self.assertEqual({19990101}, set(actual["RCON9999"]))
            for group in ("Failures", "Mergers", "Survivors"):
                for horizon in (2, 4):
                    target = material / group / "Horizons"
                    self.assertFalse((target / ("Basel III T+" + str(horizon))).exists())
                    self.assertFalse((target / ("Peer_Group_{}_Basel3_t{}.csv".format(group, horizon))).exists())
            self.assertEqual(original_inputs, {path.name: path.read_bytes() for path in inputs.iterdir()})

    def test_survivor_coercion_is_independent_for_each_group_and_horizon(self):
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory)
            inputs = material / "Mergers" / "Call Reports"
            inputs.mkdir(parents=True)
            pd.DataFrame({
                "CERT": [1, 2, 3], "ratio": [0.5, 1.0, 2.0],
                "FAILURE_T1": ["1", "unknown", "0"], "MERGER_T1": [1, 0, 0],
                "FAILURE_T3": ["unmodified"] * 3, "MERGER_T3": [0, 0, 0],
            }).to_csv(inputs / "Mergers_20200331.csv", index=False)
            with redirect_stdout(StringIO()):
                BASE.build_peer_groups(material, [1, 3])
            failures = pd.read_csv(material / "Failures/Horizons/Basel III T+1/Failures_20200331.csv")
            mergers = pd.read_csv(material / "Mergers/Horizons/Basel III T+1/Mergers_20200331.csv")
            survivors1 = pd.read_csv(material / "Survivors/Horizons/Basel III T+1/Survivors_20200331.csv")
            survivors3 = pd.read_csv(material / "Survivors/Horizons/Basel III T+3/Survivors_20200331.csv")
            self.assertTrue(failures.empty)  # Original failure selection does not coerce strings.
            self.assertEqual([1], mergers["CERT"].tolist())
            self.assertEqual(["unmodified"], mergers["FAILURE_T3"].tolist())
            self.assertEqual([2, 3], survivors1["CERT"].tolist())
            self.assertTrue(pd.isna(survivors1.loc[0, "FAILURE_T1"]))
            self.assertEqual(["unmodified", "unmodified"], survivors1["FAILURE_T3"].tolist())
            self.assertEqual([1, 2, 3], survivors3["CERT"].tolist())
            self.assertEqual(["1", "unknown", "0"], survivors3["FAILURE_T1"].tolist())
            self.assertTrue(survivors3["FAILURE_T3"].isna().all())

    def test_concatenation_keeps_file_order_duplicates_and_empty_file_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "quarterly"
            source.mkdir()
            pd.DataFrame({"CERT": [7, 7], "late_only": [1, 1]}).to_csv(source / "Late_20200630.csv", index=False)
            pd.DataFrame(columns=["CERT", "empty_only"]).to_csv(source / "Empty_20200930.csv", index=False)
            pd.DataFrame({"CERT": [8], "early_only": [2]}).to_csv(source / "Early_20200331.csv", index=False)
            pd.DataFrame({"CERT": [99]}).to_csv(source / "Excluded_20201231.csv", index=False)
            order = ["Late_20200630.csv", "Empty_20200930.csv", "Early_20200331.csv", "Excluded_20201231.csv"]
            with mock.patch.object(HORIZONS.os, "listdir", return_value=order), redirect_stdout(StringIO()):
                target = HORIZONS.filter_and_concatenate(
                    source, root / "output", "combined.csv",
                    {"20200331", "20200630", "20200930"}, "Mergers",
                )
            actual = pd.read_csv(target)
            self.assertEqual([7, 7, 8], actual["CERT"].tolist())
            self.assertEqual(["CERT", "late_only", "empty_only", "early_only"], actual.columns.tolist())
            self.assertTrue(actual["empty_only"].isna().all())

    def test_no_matching_files_do_not_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "quarterly"
            source.mkdir()
            pd.DataFrame({"CERT": [1]}).to_csv(source / "Mergers_20200331.csv", index=False)
            target = root / "combined.csv"
            target.write_text("existing output\n")
            with redirect_stdout(StringIO()):
                result = HORIZONS.filter_and_concatenate(source, root, target.name, {"20200630"}, "Mergers")
            self.assertIsNone(result)
            self.assertEqual("existing output\n", target.read_text())

    def test_input_without_mergers_prefix_uses_its_own_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            material = Path(directory)
            inputs = material / "Mergers" / "Call Reports"
            inputs.mkdir(parents=True)
            for filename, cert in (("First_20200331.csv", 1), ("Second_20200630.csv", 2)):
                pd.DataFrame({"CERT": [cert], "FAILURE_T1": [1], "MERGER_T1": [1]}).to_csv(
                    inputs / filename, index=False,
                )
            with redirect_stdout(StringIO()):
                BASE.build_peer_groups(material, [1])
            for group in ("Failures", "Mergers", "Survivors"):
                outputs = material / group / "Horizons" / "Basel III T+1"
                prefix = "" if group == "Mergers" else group + "_"
                self.assertEqual(
                    {prefix + "First_20200331.csv", prefix + "Second_20200630.csv"},
                    {path.name for path in outputs.iterdir()},
                )
                for filename, cert in (("First_20200331.csv", 1), ("Second_20200630.csv", 2)):
                    actual = pd.read_csv(outputs / (prefix + filename))
                    self.assertEqual([] if group == "Survivors" else [cert], actual["CERT"].tolist())


if __name__ == "__main__":
    unittest.main()
