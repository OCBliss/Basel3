"""Causal, date-aligned rolling CIR calibration and downstream compatibility."""

import importlib.util
import math
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_rwa_module(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "src/RWA" / filename
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


calibration = load_rwa_module("rwa_calibration", "calibration/yields/calibrate.py")
mu_repair = load_rwa_module("rwa_mu_repair", "calibration/curves/mu.py")
theta_repair = load_rwa_module("rwa_theta_repair", "calibration/curves/theta.py")
rebuild = load_rwa_module("rwa_rebuild", "data/parameters/rebuild.py")


def frame(values):
    return pd.DataFrame({
        "observation_date": pd.bdate_range("2024-01-02", periods=len(values)),
        "DGS1": values,
    })


def window_marker(block, initial_guess):
    # Deliberately order-sensitive; this exposes incorrect inputs independently
    # of a nonlinear optimizer's convergence or parameter identification.
    return np.array([block[0], block[-1], np.sum(block)], dtype=float)


class RollingCIRTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "FRED").mkdir()
        self.output = self.root / "parameters"

    def test_relocated_stages_resolve_the_same_repository_and_data_root(self):
        for module in (calibration, mu_repair, theta_repair, rebuild):
            with self.subTest(stage=module.__name__):
                self.assertEqual(Path(module.ROOT_DIR).resolve(), PROJECT_ROOT)
                self.assertEqual(Path(module.RWA_DIR).resolve(), PROJECT_ROOT / "RWA")

    def run_frame(self, source, window=3, estimator=window_marker):
        source.to_csv(self.root / "FRED/DGS1.csv", index=False)
        with mock.patch.object(calibration, "RWA_DIR", str(self.root)), \
                mock.patch.object(calibration, "OUTPUT_DIR", str(self.output)), \
                mock.patch.object(calibration, "WINDOW_SIZE", window), \
                redirect_stdout(StringIO()):
            if estimator is None:
                output_path = calibration.process_csv("DGS1.csv")
            else:
                with mock.patch.object(calibration, "estimate_theta_cir", side_effect=estimator):
                    output_path = calibration.process_csv("DGS1.csv")
        return pd.read_csv(output_path, parse_dates=["observation_date"])

    def test_newest_first_input_uses_forward_time_transitions(self):
        observed_blocks = []

        def record(block, guess):
            observed_blocks.append(block.tolist())
            return window_marker(block, guess)

        result = self.run_frame(frame([1., 2., 3., 4., 5.]).iloc[::-1], estimator=record)
        self.assertEqual([[1., 2., 3.], [2., 3., 4.], [3., 4., 5.]], observed_blocks)
        latest = result.iloc[0]
        np.testing.assert_array_equal([3., 5., 12.], latest[["theta", "mu", "sigma"]].astype(float))
        self.assertTrue(result.iloc[-2:][["theta", "mu", "sigma"]].isna().all().all())

    def test_ascending_input_assigns_each_fit_to_last_date_in_its_window(self):
        result = self.run_frame(frame([1., 2., 3., 4., 5.]))
        self.assertTrue(result.iloc[:2][["theta", "mu", "sigma"]].isna().all().all())
        np.testing.assert_array_equal([1., 3., 6.], result.iloc[2][["theta", "mu", "sigma"]].astype(float))
        np.testing.assert_array_equal([3., 5., 12.], result.iloc[4][["theta", "mu", "sigma"]].astype(float))

    def test_row_order_does_not_change_date_keyed_estimates(self):
        source = frame([1., 2., 3., 4., 5., 6.])
        ascending = self.run_frame(source).set_index("observation_date").sort_index()
        for ordered in (source.iloc[::-1], source.iloc[[3, 0, 5, 1, 4, 2]]):
            with self.subTest(order=ordered.index.tolist()):
                result = self.run_frame(ordered)
                self.assertEqual(ordered.observation_date.tolist(), result.observation_date.tolist())
                pd.testing.assert_frame_equal(
                    ascending.drop(columns="Unnamed: 0"),
                    result.set_index("observation_date").sort_index().drop(columns="Unnamed: 0"),
                )

    def test_appending_future_data_does_not_change_any_past_output(self):
        source = frame([1., 2., 3., 4., 5., 90., 80.])
        short = self.run_frame(source.iloc[:5]).set_index("observation_date")
        extended = self.run_frame(source).set_index("observation_date")
        pd.testing.assert_frame_equal(short, extended.loc[short.index])

    def test_missing_yields_use_only_earlier_observations_in_any_order(self):
        source = frame([1., 2., ".", 4., np.nan, 6.])
        for ordered in (source, source.iloc[::-1], source.iloc[[4, 0, 5, 2, 1, 3]]):
            with self.subTest(order=ordered.index.tolist()):
                result = self.run_frame(ordered).sort_values("observation_date")
                self.assertEqual([1., 2., 2., 4., 4., 6.], result.yield_clean.tolist())
                np.testing.assert_array_equal([1., 2., 5.], result.iloc[2][["theta", "mu", "sigma"]].astype(float))

    def test_unknown_initial_yield_is_not_filled_from_the_future(self):
        with self.assertRaisesRegex(ValueError, "earliest|earlier|prior|chronolog"):
            self.run_frame(frame([np.nan, 2., 3., 4.]))
        self.assertFalse(self.output.exists())

    def test_invalid_dates_fail_before_fitting_or_overwriting_output(self):
        self.output.mkdir()
        target = self.output / "DGS1_with_parameters.csv"
        target.write_text("previous valid result\n")
        invalid_frames = []
        for value in (None, "not-a-date", "2024-01-02"):
            source = frame([1., 2., 3., 4.])
            source["observation_date"] = source.observation_date.astype(str)
            source.loc[1, "observation_date"] = value
            invalid_frames.append(source)
        invalid_frames.append(frame([1., 2., 3., 4.]).drop(columns="observation_date"))
        for source in invalid_frames:
            with self.subTest(dates=source.to_dict("list")):
                estimator = mock.Mock(side_effect=window_marker)
                with self.assertRaises((ValueError, KeyError)):
                    self.run_frame(source, estimator=estimator)
                estimator.assert_not_called()
                self.assertEqual("previous valid result\n", target.read_text())

    def test_nonpositive_and_infinite_yields_fail_before_writing(self):
        for value in (0., -1., np.inf, -np.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive|finite"):
                    self.run_frame(frame([1., value, 3., 4.]))
                self.assertFalse(self.output.exists())

    def test_exact_window_retains_schema_row_labels_and_metadata(self):
        source = frame([1., 2., 3.]).iloc[::-1].copy()
        source["vendor_note"] = ["latest", "middle", "oldest"]
        result = self.run_frame(source)
        self.assertEqual(["Unnamed: 0", "observation_date", "DGS1", "vendor_note",
                          "yield_clean", "theta", "mu", "sigma"], result.columns.tolist())
        self.assertEqual([1, 2, 3], result["Unnamed: 0"].tolist())
        self.assertEqual(source.vendor_note.tolist(), result.vendor_note.tolist())
        self.assertEqual([1., 3., 6.], result.iloc[0][["theta", "mu", "sigma"]].tolist())
        self.assertTrue(result.iloc[1:][["theta", "mu", "sigma"]].isna().all().all())

    def test_short_input_and_invalid_window_size_fail_before_writing(self):
        for window in (0, 1, 2.5, True, 5):
            with self.subTest(window=window):
                with self.assertRaises(ValueError):
                    self.run_frame(frame([1., 2., 3., 4.]), window=window)
                self.assertFalse(self.output.exists())

    def test_failed_fit_resets_warm_start_without_moving_results_to_another_date(self):
        guesses = []
        answers = [np.array([2., 3., .5]), np.full(3, np.nan), np.array([4., 5., .7])]

        def estimate(block, guess):
            guesses.append(guess.copy())
            return answers[len(guesses) - 1]

        source = frame([1., 2., 3., 4., 5.])
        result = self.run_frame(source, estimator=estimate)
        np.testing.assert_array_equal(calibration.make_initial_guess(np.array([1., 2., 3.])), guesses[0])
        np.testing.assert_array_equal(answers[0], guesses[1])
        np.testing.assert_array_equal(calibration.make_initial_guess(np.array([3., 4., 5.])), guesses[2])
        self.assertTrue(result.iloc[3][["theta", "mu", "sigma"]].isna().all())
        np.testing.assert_array_equal(answers[2], result.iloc[4][["theta", "mu", "sigma"]].astype(float))

    def test_real_optimizer_is_invariant_to_row_order_and_future_observations(self):
        rng = np.random.default_rng(410)
        values = [4.]
        for shock in rng.normal(0., .07, 79):
            values.append(values[-1] + .1 * (3. - values[-1]) + shock)
        source = frame(values)
        short = self.run_frame(source.iloc[:70], window=64, estimator=None)
        ascending = self.run_frame(source, window=64, estimator=None)
        descending = self.run_frame(source.iloc[::-1], window=64, estimator=None)
        cols = ["yield_clean", "theta", "mu", "sigma"]
        self.assertTrue(np.isfinite(ascending.iloc[-1][cols].astype(float)).all())
        pd.testing.assert_frame_equal(
            ascending.set_index("observation_date")[cols],
            descending.set_index("observation_date").sort_index()[cols],
        )
        pd.testing.assert_frame_equal(
            short.set_index("observation_date")[cols],
            ascending.set_index("observation_date").loc[short.observation_date, cols],
        )

    def test_likelihood_matches_independent_forward_transition_calculation(self):
        values = np.array([4., 3.8, 3.7, 3.5])
        theta, mu, sigma, dt = 2., 3., .4, .1
        expected = 0.
        for earlier, later in zip(values[:-1], values[1:]):
            mean = earlier + theta * (mu - earlier) * dt
            variance = sigma ** 2 * earlier * dt
            expected += .5 * (math.log(2 * math.pi * variance) + (later - mean) ** 2 / variance)
        self.assertAlmostEqual(expected, calibration.cir_log_likelihood([theta, mu, sigma], values, dt))
        self.assertNotAlmostEqual(expected, calibration.cir_log_likelihood([theta, mu, sigma], values[::-1], dt))

    def test_all_maturities_flow_through_nss_files_and_parameter_rebuild(self):
        rng = np.random.default_rng(410)
        values = [4.]
        for shock in rng.normal(0., .07, 67):
            values.append(values[-1] + .1 * (3. - values[-1]) + shock)
        raw_outputs = {}
        curve_series = {parameter: [] for parameter in ("theta", "mu", "sigma")}
        for number, (dgs_name, mapping) in enumerate(rebuild.MATURITY_MAP.items()):
            source = frame(np.array(values) * (1. + number * .04)).rename(columns={"DGS1": dgs_name})
            # Include descending, ascending and unordered sources in one run.
            if number % 3 == 0:
                source = source.iloc[::-1]
            elif number % 3 == 1:
                source = source.sample(frac=1., random_state=number)
            source.to_csv(self.root / "FRED" / (dgs_name + ".csv"), index=False)
            with mock.patch.object(calibration, "RWA_DIR", str(self.root)), \
                    mock.patch.object(calibration, "OUTPUT_DIR", str(self.output)), \
                    mock.patch.object(calibration, "WINDOW_SIZE", 64), \
                    redirect_stdout(StringIO()):
                path = calibration.process_csv(dgs_name + ".csv")
            raw = pd.read_csv(path, parse_dates=["observation_date"])
            self.assertEqual(source.observation_date.tolist(), raw.observation_date.tolist())
            self.assertEqual(5, raw["mu"].notna().sum())
            raw_outputs[dgs_name] = raw
            dated = raw.set_index("observation_date")
            for parameter in curve_series:
                curve_series[parameter].append(dated[parameter].rename(mapping[parameter]))

        # Curve-table assembly is an explicit file contract between the scripts;
        # the repository does not supply a separate automated assembly stage.
        curves = {}
        for parameter, series in curve_series.items():
            curves[parameter] = self.root / (parameter + "_curve.csv")
            pd.concat(series, axis=1).sort_index().to_csv(curves[parameter])
        repaired_mu_path = self.root / "mu_repaired.csv"
        repaired_theta_path = self.root / "theta_repaired.csv"
        with redirect_stdout(StringIO()):
            repaired_mu = mu_repair.repair_mu_file(curves["mu"], repaired_mu_path)
            repaired_theta = theta_repair.repair_mu_file(curves["theta"], repaired_theta_path)
        self.assertFalse(repaired_mu.curve_repair_performed.any())
        self.assertFalse(repaired_theta.curve_repair_performed.any())

        destination = self.root / "volatility_input"
        with mock.patch.object(rebuild, "DGS_RAW_DIR", str(self.output)), \
                mock.patch.object(rebuild, "MU_REPAIRED_FILE", str(repaired_mu_path)), \
                mock.patch.object(rebuild, "THETA_REPAIRED_FILE", str(repaired_theta_path)), \
                mock.patch.object(rebuild, "SIGMA_CURVE_FILE", str(curves["sigma"])), \
                mock.patch.object(rebuild, "MLE_VOL_RAW_DIR", str(destination)), \
                redirect_stdout(StringIO()):
            rebuild.main()
        self.assertEqual(8, len(list(destination.glob("*_with_parameters.csv"))))
        for dgs_name, expected in raw_outputs.items():
            with self.subTest(maturity=dgs_name):
                actual = pd.read_csv(destination / (dgs_name + "_with_parameters.csv"),
                                     parse_dates=["observation_date"])
                columns = ["observation_date", dgs_name, "yield_clean", "theta", "mu", "sigma"]
                self.assertEqual(columns, actual.columns.tolist())
                pd.testing.assert_frame_equal(expected[columns], actual, rtol=1e-12, atol=1e-12)
                self.assertTrue(actual.sort_values("observation_date").iloc[:63][
                    ["theta", "mu", "sigma"]].isna().all().all())

    def test_single_nonfinite_fit_does_not_contaminate_later_windows(self):
        guesses = []

        def estimate(block, guess):
            guesses.append(guess.copy())
            if len(guesses) == 1:
                return np.array([np.nan, np.nan, np.nan])
            return np.array([1., 3., .4])

        result = self.run_frame(frame([1., 2., 3., 4.]).iloc[::-1], estimator=estimate)
        np.testing.assert_array_equal(calibration.make_initial_guess(np.array([2., 3., 4.])), guesses[1])
        np.testing.assert_array_equal([1., 3., .4], result.iloc[0][["theta", "mu", "sigma"]].astype(float))
        self.assertTrue(result.iloc[1][["theta", "mu", "sigma"]].isna().all())


class CIRCurveDomainTests(unittest.TestCase):
    def test_inadmissible_extrapolation_rejects_entire_repair_and_records_reason(self):
        for module, key in ((mu_repair, "mu"), (theta_repair, "theta")):
            columns = list(module.MU_COLUMNS if key == "mu" else module.THETA_COLUMNS)
            values = ([20., 30.] if key == "mu" else [.001, .002]) + [1.] * 6
            row = pd.Series(dict(zip(columns, values)))
            row["observation_date"] = "2025-03-10"
            for invalid in (0., -.1, np.nan, np.inf):
                with self.subTest(parameter=key, invalid=invalid), \
                        mock.patch.object(module, "fit_nss", return_value=(np.ones(6), .01)), \
                        mock.patch.object(module, "nss_curve", return_value=np.array([1.2, invalid])):
                    with self.assertWarns(RuntimeWarning):
                        result = module.repair_mu_row(row)
                    # The first candidate is valid but must not be left partially
                    # applied when the second is rejected.
                    pd.testing.assert_series_equal(row[columns], result[columns])
                    self.assertFalse(result.curve_fit_success)
                    self.assertFalse(result.curve_repair_performed)
                    self.assertFalse(any(result[column + "_repaired"] for column in columns))
                    self.assertIn(columns[1], result.curve_fit_error)

    def test_admissible_reconstruction_changes_only_target_nodes(self):
        for module, key in ((mu_repair, "mu"), (theta_repair, "theta")):
            columns = list(module.MU_COLUMNS if key == "mu" else module.THETA_COLUMNS)
            values = ([20., 30.] if key == "mu" else [.001, .002]) + [1.] * 6
            row = pd.Series(dict(zip(columns, values)))
            row["observation_date"] = "2025-03-10"
            with self.subTest(parameter=key), \
                    mock.patch.object(module, "fit_nss", return_value=(np.ones(6), .01)), \
                    mock.patch.object(module, "nss_curve", return_value=np.array([1.2, 1.5])):
                result = module.repair_mu_row(row)
            np.testing.assert_array_equal([1.2, 1.5] + [1.] * 6, result[columns].astype(float))
            self.assertTrue(result.curve_fit_success)
            self.assertTrue(result.curve_repair_performed)
            self.assertEqual("", result.curve_fit_error)

    def test_real_short_tenor_theta_extrapolation_cannot_publish_negative_parameters(self):
        # Dated calibration fixture whose short-tenor NSS extrapolation is negative.
        row = pd.Series({
            "observation_date": "2025-03-10",
            "theta1y": .0016707722787036, "theta2y": .0065764086975963,
            "theta3y": .027044009969019, "theta5y": .1206759193145742,
            "theta7y": .1751496766736058, "theta10y": .2528230273527934,
            "theta20y": .2926494221904001, "theta30y": .3662768446363436,
        })
        columns = list(theta_repair.THETA_COLUMNS)
        with self.assertWarns(RuntimeWarning):
            repaired = theta_repair.repair_mu_row(row)
        self.assertFalse(repaired.curve_fit_success)
        self.assertIn("positive", repaired.curve_fit_error)
        pd.testing.assert_series_equal(row[columns], repaired[columns])


if __name__ == "__main__":
    unittest.main()
