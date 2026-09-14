"""Independent elapsed-time likelihood, missing-quote and end-to-end checks."""

import importlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
core = importlib.import_module("src.RWA.models.parameter_hierarchy.core")
workflow = importlib.import_module("src.RWA.models.parameter_hierarchy.workflow")
recursive = importlib.import_module("src.RWA.models.parameter_hierarchy.recursive")
acquisition = importlib.import_module("src.RWA.data.yields.acquire")


def irregular_dates(n):
    days = np.resize(np.array([1, 3, 1, 2, 4, 1, 1]), n - 1)
    return pd.DatetimeIndex(pd.Timestamp("2020-02-20") +
                            pd.to_timedelta(np.r_[0, np.cumsum(days)], unit="D"))


def annual_steps(dates):
    # Independent elapsed-day calculation; includes weekends and leap day.
    return np.array([(b - a).total_seconds() / (365 * 86400)
                     for a, b in zip(dates[:-1], dates[1:])])


def stochastic_rates(n=1200, seed=771, dimensions=1):
    dates = irregular_dates(n)
    rng = np.random.default_rng(seed)
    values = np.empty((n, dimensions))
    means = np.linspace(3., 4., dimensions)
    values[0] = means
    for i, step in enumerate(annual_steps(dates)):
        x = values[i]
        values[i + 1] = x + 8 * (means - x) * step + .4 * np.sqrt(x * step) * rng.normal(size=dimensions)
    return pd.DataFrame(values, index=dates, columns=range(1, dimensions + 1))


def state_fixture(n=8):
    dates = irregular_dates(n)
    clock = np.arange(n)[:, None, None]
    base = np.array([[3.8, 4.2], [3.2, 3.6], [.8, 1.], [.25, .30]])
    phase = np.arange(8).reshape(1, 4, 2) / 3
    history = base[None] + .005 * np.sin(clock * .7 + phase) + .001 * clock
    coeff = np.array([[[.7, .8], [3.2, 3.6], [.015, .017]],
                      [[.8, .9], [.8, 1.], [.012, .014]],
                      [[.9, 1.], [.25, .30], [.008, .010]]])
    first = pd.DataFrame([
        dict(observation_date=date, maturity=tenor, mu=history[t, 1, j],
             theta=history[t, 2, j], sigma=history[t, 3, j])
        for t, date in enumerate(dates) for j, tenor in enumerate((1, 2))])
    second = pd.DataFrame([
        dict(observation_date=dates[-1], maturity=tenor, parameter=parameter,
             theta=coeff[k, 0, j], mu=coeff[k, 1, j], sigma=coeff[k, 2, j])
        for k, parameter in enumerate(workflow.PARAMETERS)
        for j, tenor in enumerate((1, 2))])
    yields = pd.DataFrame(history[:, 0], index=dates, columns=(1, 2))
    return history, coeff, yields, first, second


def independently_standardize(history, coeff, steps):
    result = np.empty_like(history[:-1])
    for t, step in enumerate(steps):
        for j in range(history.shape[2]):
            x, mu, theta, sigma = history[t, :, j]
            result[t, 0, j] = ((history[t + 1, 0, j] - x - theta * (mu - x) * step)
                               / (sigma * np.sqrt(x * step)))
            for k in range(3):
                old = history[t, k + 1, j]
                speed, level, volatility = coeff[k, :, j]
                result[t, k + 1, j] = ((history[t + 1, k + 1, j] - old
                                        - speed * (level - old) * step)
                                       / (volatility * np.sqrt(old * step)))
    return result


def controlled_fit(histories, maturities, dt=1 / 252, nll_budget=2.,
                   fallback_theta=.25, prior_thetas=None):
    fits = [core.CIRFit(a=1.5 * v[-1], theta=1.5, mu=v[-1], sigma=.01,
                        theta_se=.05, nll=0., weak=False)
            for v in np.asarray(histories).T]
    audit = [dict(weak=False, regularized=False, nll_cost=0.,
                  anchor_source="unmodified", usable=True) for _ in fits]
    return fits, audit


class IrregularLikelihoodTests(unittest.TestCase):
    def test_profile_matches_independent_full_likelihood_optimizer(self):
        source = stochastic_rates()
        values = source.iloc[:, 0].to_numpy()
        steps = annual_steps(source.index)

        def objective(log_parameters):
            speed, level, volatility = np.exp(log_parameters)
            variance = volatility ** 2 * values[:-1] * steps
            errors = np.diff(values) - speed * (level - values[:-1]) * steps
            return .5 * np.sum(np.log(2 * np.pi * variance) + errors ** 2 / variance)

        independent = minimize(objective, np.log([8., 3., .4]), method="BFGS", tol=1e-8)
        fitted = core.fit_cir(values, steps)
        self.assertAlmostEqual(fitted.nll, independent.fun, places=6)
        np.testing.assert_allclose([fitted.theta, fitted.mu, fitted.sigma],
                                   np.exp(independent.x), rtol=2e-4)
        # Conditional Gaussian regression information gives a separate SE oracle.
        design = np.column_stack([steps, -values[:-1] * steps])
        precision = 1 / (fitted.sigma ** 2 * values[:-1] * steps)
        covariance = np.linalg.inv(design.T @ (precision[:, None] * design))
        self.assertAlmostEqual(fitted.theta_se, np.sqrt(covariance[1, 1]), places=9)

    def test_constant_duration_vector_preserves_scalar_fits_and_ridge_decisions(self):
        source = stochastic_rates(n=90, dimensions=2)
        source.iloc[:, 1] = 3 + np.arange(len(source)) * .002
        for step in (1 / 252, 1 / 365, .1):
            with self.subTest(step=step):
                scalar, scalar_audit = core.stabilize_panel(source.to_numpy(), source.columns, step)
                vector, vector_audit = core.stabilize_panel(
                    source.to_numpy(), source.columns, np.full(len(source) - 1, step))
                self.assertEqual(scalar, vector)
                self.assertEqual(scalar_audit, vector_audit)
                self.assertEqual(core.fit_cir(np.ones(8), step),
                                 core.fit_cir(np.ones(8), np.full(7, step)))

    def test_state_and_time_unit_changes_obey_diffusion_dimensions(self):
        source = stochastic_rates()
        values = source.iloc[:, 0].to_numpy()
        steps = annual_steps(source.index)
        fitted = core.fit_cir(values, steps)
        state_scale, time_scale = .01, 365.
        converted = core.fit_cir(values * state_scale, steps * time_scale)
        self.assertFalse(fitted.weak)
        np.testing.assert_allclose(
            [converted.a, converted.theta, converted.mu, converted.sigma, converted.theta_se],
            [fitted.a * state_scale / time_scale, fitted.theta / time_scale,
             fitted.mu * state_scale, fitted.sigma * np.sqrt(state_scale / time_scale),
             fitted.theta_se / time_scale], rtol=2e-10)
        self.assertAlmostEqual(converted.nll - fitted.nll,
                               (len(values) - 1) * np.log(state_scale), places=7)

    def test_elapsed_days_cannot_be_replaced_by_the_mean_interval(self):
        source = stochastic_rates()
        values = source.iloc[:, 0].to_numpy()
        steps = annual_steps(source.index)
        fitted = core.fit_cir(values, steps)
        averaged = core.fit_cir(values, steps.mean())
        variance = averaged.sigma ** 2 * values[:-1] * steps
        errors = np.diff(values) - averaged.theta * (averaged.mu - values[:-1]) * steps
        actual_nll_at_average_fit = .5 * np.sum(np.log(2 * np.pi * variance) + errors ** 2 / variance)
        self.assertGreater(actual_nll_at_average_fit - fitted.nll, .05)

    def test_irregular_ridge_profile_preserves_its_likelihood_budget(self):
        dates = irregular_dates(90)
        steps = annual_steps(dates)
        values = 3. + np.arange(90) * .002 + .0005 * np.sin(np.arange(90))
        original = core.fit_cir(values, steps)
        fitted, audit = core.stabilize_panel(values[:, None], [1], steps,
                                           nll_budget=.1, fallback_theta=20.)
        fit = fitted[0]
        self.assertTrue(original.weak)
        self.assertTrue(audit[0]["regularized"])
        self.assertGreater(fit.theta, 0.)
        self.assertLessEqual(fit.nll - original.nll, .1 + 1e-9)
        variance = fit.sigma ** 2 * values[:-1] * steps
        errors = np.diff(values) - fit.theta * (fit.mu - values[:-1]) * steps
        independent_nll = .5 * np.sum(np.log(2 * np.pi * variance) + errors ** 2 / variance)
        self.assertAlmostEqual(fit.nll, independent_nll, places=7)

    def test_invalid_intervals_rejected_even_for_deterministic_history(self):
        bad_steps = [0, -1, np.nan, np.inf, True, "0.1", [], [.1] * 2,
                     [.1] * 4, [[.1, .1, .1]], [.1, 0., .1], [.1, -1., .1],
                     [.1, np.nan, .1], [.1, np.inf, .1], [True, True, True]]
        for values in ([1., 2., 1., 2.], [1., 1., 1., 1.]):
            for steps in bad_steps:
                with self.subTest(values=values, steps=steps), self.assertRaises(ValueError):
                    core.fit_cir(values, steps)


class ObservedQuoteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write(self, tenor, quotes):
        pd.DataFrame({"observation_date": irregular_dates(len(quotes)),
                      "DGS%d" % tenor: quotes,
                      "yield_clean": np.full(len(quotes), 99.),
                      "is_imputed": np.ones(len(quotes), dtype=bool)}).iloc[::-1].to_csv(
            self.directory / ("DGS%d.csv" % tenor), index=False)

    def test_observed_policy_uses_raw_quotes_and_intersects_after_dropping(self):
        self.write(1, [3., ".", 3.1, 3.2, np.nan, 3.4])
        self.write(2, [4., 4.1, 4.2, ".", 4.3, 4.4])
        panel, sources = workflow.read_yield_panel(self.directory, (1, 2), missing_policy="observed")
        self.assertEqual(panel.index.tolist(), irregular_dates(6)[[0, 2, 5]].tolist())
        np.testing.assert_array_equal(panel.to_numpy(), [[3., 4.], [3.1, 4.2], [3.4, 4.4]])
        self.assertEqual([s["filled_quotes"] for s in sources], [0, 0])
        self.assertEqual([s["rows_before_alignment"] for s in sources], [4, 5])
        self.assertEqual([s["missing_quotes"] for s in sources], [2, 1])
        self.assertEqual([s["excluded_missing_quotes"] for s in sources], [2, 1])
        self.assertEqual([s["rows_after_alignment"] for s in sources], [3, 3])

    def test_default_forward_fill_and_as_of_are_causal(self):
        self.write(1, [3., ".", 3.1, 3.2, 8., 9.])
        self.write(2, [4., 4.1, 4.2, ".", 8., 9.])
        cutoff = irregular_dates(6)[3]
        default, sources = workflow.read_yield_panel(self.directory, (1, 2), as_of=cutoff)
        explicit, _ = workflow.read_yield_panel(self.directory, (1, 2), as_of=cutoff,
                                               missing_policy="forward-fill")
        pd.testing.assert_frame_equal(default, explicit)
        np.testing.assert_array_equal(default.to_numpy(), [[3., 4.], [3., 4.1], [3.1, 4.2], [3.2, 4.2]])
        self.assertEqual([s["filled_quotes"] for s in sources], [1, 1])
        observed, _ = workflow.read_yield_panel(self.directory, (1, 2), as_of=cutoff,
                                               missing_policy="observed")
        self.assertEqual(observed.index.tolist(), irregular_dates(6)[[0, 2]].tolist())

    def test_leading_missing_is_usable_only_under_explicit_observed_policy(self):
        self.write(1, [".", 3., 3.1, 3.2])
        observed, _ = workflow.read_yield_panel(self.directory, (1,), missing_policy="observed")
        self.assertEqual(observed.index[0], irregular_dates(4)[1])
        with self.assertRaises(ValueError):
            workflow.read_yield_panel(self.directory, (1,))

    def test_invalid_nonmissing_token_cannot_disappear_as_missing(self):
        for token in ("broken", "3,4", "1x", np.inf, -1., 0.):
            self.write(1, [3., token, 3.1, 3.2])
            for policy in ("observed", "forward-fill"):
                with self.subTest(token=token, policy=policy), self.assertRaises(ValueError):
                    workflow.read_yield_panel(self.directory, (1,), missing_policy=policy)
        with self.assertRaises(ValueError):
            workflow.read_yield_panel(self.directory, (1,), missing_policy="drop-whatever")

    def test_nul_corruption_cannot_be_truncated_into_a_genuine_quote(self):
        # pandas' default C parser truncates tokens at NUL; require a file guard.
        (self.directory / "DGS1.csv").write_bytes(
            b"observation_date,DGS1\n2024-01-02,3\n2024-01-03,3\x00invalid\n"
            b"2024-01-04,3.2\n2024-01-05,3.3\n")
        for policy in ("observed", "forward-fill"):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                workflow.read_yield_panel(self.directory, (1,), missing_policy=policy)

    def test_short_rows_and_duplicate_headers_cannot_change_missingness(self):
        corruptions = [
            b"observation_date,DGS1\n2024-01-02,3\n2024-01-03\n2024-01-04,3.2\n",
            b"observation_date,DGS1,DGS1\n2024-01-02,3,8\n2024-01-03,3.1,9\n",
            b"observation_date,DGS1\n2024-01-02,3\n2024-01-03,3.1,extra\n",
        ]
        for content in corruptions:
            (self.directory / "DGS1.csv").write_bytes(content)
            for policy in ("observed", "forward-fill"):
                with self.subTest(content=content, policy=policy), self.assertRaises(ValueError):
                    workflow.read_yield_panel(self.directory, (1,), missing_policy=policy)


class ElapsedWorkflowTests(unittest.TestCase):
    def test_calendar_clock_uses_fixed_365_years_and_rejects_invalid_dates(self):
        dates = pd.to_datetime(["2020-02-28", "2020-02-29", "2020-03-02", "2021-03-02"])
        np.testing.assert_allclose(workflow.observation_steps(dates, time_basis="act365f"),
                                   [1 / 365, 2 / 365, 1.], rtol=0, atol=0)
        self.assertEqual(workflow.observation_steps(dates, dt=.02), .02)
        for bad in (dates[::-1], dates[[0, 1, 1, 3]], pd.DatetimeIndex([dates[0], pd.NaT]),
                    dates.tz_localize("UTC"), dates + pd.Timedelta(hours=1)):
            with self.subTest(dates=bad), self.assertRaises(ValueError):
                workflow.observation_steps(bad, time_basis="act365f")
        with self.assertRaises(ValueError):
            workflow.observation_steps(dates, time_basis="unknown")

    def test_rolling_windows_slice_causal_intervals_for_all_parameter_branches(self):
        source = stochastic_rates(n=11, dimensions=2)
        captured = []

        def capture(values, tenors, dt, *args, **kwargs):
            captured.append((np.asarray(values).copy(), np.asarray(dt).copy()))
            return controlled_fit(values, tenors, dt, *args, **kwargs)

        with mock.patch.object(workflow, "stabilize_panel", side_effect=capture):
            first = workflow.calibrate_panel(source.iloc[::-1], 5, time_basis="act365f")
        self.assertEqual(len(captured), 7)
        for end, (values, intervals) in enumerate(captured, start=4):
            np.testing.assert_array_equal(values, source.iloc[end - 4:end + 1].to_numpy())
            np.testing.assert_allclose(intervals, annual_steps(source.index[end - 4:end + 1]), rtol=0, atol=0)
        captured.clear()
        with mock.patch.object(workflow, "stabilize_panel", side_effect=capture):
            second = workflow.calibrate_parameters(first, 5, time_basis="act365f")
        self.assertEqual(set(second.parameter), set(workflow.PARAMETERS))
        panels = workflow.parameter_panels(first)
        self.assertEqual(len(captured), 9)
        for branch, parameter in enumerate(workflow.PARAMETERS):
            panel = panels[parameter]
            for offset, end in enumerate(range(4, len(panel))):
                values, intervals = captured[branch * 3 + offset]
                np.testing.assert_array_equal(values, panel.iloc[end - 4:end + 1])
                np.testing.assert_allclose(intervals, annual_steps(panel.index[end - 4:end + 1]), rtol=0, atol=0)

    def test_actual_two_pass_calibration_is_invariant_to_future_and_row_order(self):
        source = stochastic_rates(n=80, dimensions=2)
        whole = workflow.calibrate_panel(source, 30, time_basis="act365f")
        ordered = workflow.calibrate_panel(source.sample(frac=1, random_state=42), 30, time_basis="act365f")
        early = workflow.calibrate_panel(source.iloc[:-5], 30, time_basis="act365f")
        pd.testing.assert_frame_equal(whole, ordered)
        pd.testing.assert_frame_equal(early, whole.loc[whole.observation_date <= source.index[-6]].reset_index(drop=True))
        whole_second = workflow.calibrate_parameters(whole, 16, time_basis="act365f")
        early_second = workflow.calibrate_parameters(early, 16, time_basis="act365f")
        pd.testing.assert_frame_equal(early_second, whole_second.loc[
            whole_second.observation_date <= source.index[-6]].reset_index(drop=True))

    def test_joint_dependence_uses_each_actual_elapsed_interval(self):
        history, coeff, yields, first, second = state_fixture()
        captured = []

        def capture(values, shrinkage):
            captured.append(np.asarray(values).copy())
            return core.innovation_correlation(values, shrinkage)

        with mock.patch.object(workflow, "innovation_correlation", side_effect=capture):
            initial, actual_coeff, corr, factor, _ = workflow.forecast_inputs(
                yields, first, second, 6, .02, time_basis="act365f")
        expected = independently_standardize(history[-6:], coeff, annual_steps(yields.index[-6:]))
        np.testing.assert_allclose(captured[0], expected.reshape(5, 8), rtol=2e-13, atol=1e-11)
        np.testing.assert_array_equal(initial, history[-1])
        np.testing.assert_array_equal(actual_coeff, coeff)
        np.testing.assert_allclose(factor @ factor.T, corr, atol=1e-14)

    def test_noise_null_simulates_and_replays_the_same_irregular_clock(self):
        _, _, yields, first, second = state_fixture()
        latest = first.loc[first.observation_date == yields.index[-1]].sort_values("maturity")
        base = latest[["theta", "mu", "sigma"]].to_numpy().T
        draws = np.resize(np.array([.2, -.3, .1, .4]), (len(yields) - 1, 2))
        captured, clocks = [], []

        class FixedRandom:
            def normal(self, size):
                self_shape = draws.shape
                if size != self_shape:
                    raise AssertionError((size, self_shape))
                return draws.copy()

        def first_pass(panel, window, dt, nll_budget, fallback_theta, time_basis="observation"):
            captured.append(panel.to_numpy().copy())
            clocks.append(time_basis)
            return first

        def second_pass(table, window, dt, nll_budget, fallback_theta, time_basis="observation"):
            clocks.append(time_basis)
            return second

        with mock.patch.object(workflow, "calibrate_panel", side_effect=first_pass), \
                mock.patch.object(workflow, "calibrate_parameters", side_effect=second_pass), \
                mock.patch.object(workflow.np.random, "default_rng", return_value=FixedRandom()):
            report = workflow.parameter_noise_diagnostic(
                yields, first, second, 4, 5, replicates=2, dt=.02,
                shrinkage=1., time_basis="act365f")
        expected = np.empty_like(yields.to_numpy())
        expected[0] = yields.iloc[0]
        for t, step in enumerate(annual_steps(yields.index)):
            old = expected[t]
            expected[t + 1] = old + base[0] * (base[1] - old) * step + base[2] * np.sqrt(old * step) * draws[t]
        self.assertTrue(report["comparable"], report["failures"])
        self.assertEqual(clocks, ["act365f"] * 4)
        self.assertEqual(len(captured), 2)
        for actual in captured:
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)


class ElapsedRecursiveTests(unittest.TestCase):
    def test_recursive_rollover_replaces_only_expired_historical_intervals(self):
        history, coeff, yields, _, _ = state_fixture(n=5)
        history_steps = annual_steps(yields.index)
        original = history_steps.copy()
        forecast_step = .002
        captured, residuals = [], []

        def capture_fit(values, tenors, dt, *args, **kwargs):
            captured.append((np.asarray(values).copy(), np.asarray(dt).copy()))
            return controlled_fit(values, tenors, dt, *args, **kwargs)

        def capture_dependence(values, *args, **kwargs):
            residuals.append(np.asarray(values).copy())
            return core.innovation_correlation(values, *args, **kwargs)

        with mock.patch.object(recursive, "stabilize_panel", side_effect=capture_fit), \
                mock.patch.object(recursive, "innovation_correlation", side_effect=capture_dependence):
            result, _, diagnostics = recursive.simulate_recursive(
                history, coeff, np.eye(8), (1, 2), paths=2, steps=7, dt=forecast_step,
                seed=56, substeps=8, recalibrate_every=1, history_dt=history_steps)
        self.assertEqual(len(captured), 6 * 2 * 3)
        self.assertEqual(len(residuals), 6 * 2)
        for origin in range(1, 7):
            intervals = np.r_[history_steps, np.full(origin, forecast_step)][-4:]
            for path in range(2):
                trailing = np.concatenate([history, result[path, 1:origin + 1]])[-5:]
                learned = coeff.copy()
                for branch in range(3):
                    position = ((origin - 1) * 2 + path) * 3 + branch
                    values, actual_steps = captured[position]
                    np.testing.assert_array_equal(values, trailing[:, branch + 1])
                    np.testing.assert_array_equal(actual_steps, intervals)
                    learned[branch] = [np.full(2, 1.5), trailing[-1, branch + 1], np.full(2, .01)]
                expected = independently_standardize(trailing, learned, intervals)
                np.testing.assert_allclose(residuals[(origin - 1) * 2 + path],
                                           expected.reshape(4, 8), rtol=2e-13, atol=1e-10)
        np.testing.assert_array_equal(history_steps, original)
        self.assertEqual(diagnostics["recalibration_count"], 12)
        self.assertAlmostEqual(diagnostics["initial_history_elapsed_years"], history_steps.sum())
        for update in diagnostics["updates"]:
            origin = update["origin_step"]
            intervals = np.r_[history_steps, np.full(origin, forecast_step)][-4:]
            self.assertEqual(update["observed_history_transitions"], max(0, 4 - origin))
            self.assertEqual(update["simulated_history_transitions"], min(4, origin))
            self.assertAlmostEqual(update["history_elapsed_years"], intervals.sum())

    def test_historical_clock_does_not_change_forecast_before_first_refit(self):
        history, coeff, yields, _, _ = state_fixture()
        options = dict(paths=2, steps=3, dt=.002, seed=57, substeps=8, recalibrate_every=0)
        old = recursive.simulate_recursive(history, coeff, np.eye(8), (1, 2), **options)
        elapsed = recursive.simulate_recursive(history, coeff, np.eye(8), (1, 2),
                                               history_dt=annual_steps(yields.index), **options)
        np.testing.assert_array_equal(old[0], elapsed[0])
        np.testing.assert_array_equal(old[1], elapsed[1])
        with self.assertRaises(ValueError):
            recursive.simulate_recursive(history, coeff, np.eye(8), (1, 2),
                                         history_dt=[.1], **options)


class ElapsedCommandTests(unittest.TestCase):
    def test_verified_acquisition_snapshot_flows_through_elapsed_cli(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            directory = Path(temporary)
            snapshot = directory / "snapshot"
            source = stochastic_rates(n=96, seed=419, dimensions=2)
            source.index.name = "observation_date"
            quotes = source.astype(object).rename(columns={1: "DGS1", 2: "DGS2"})
            quotes.iloc[10, 0] = "."
            quotes.iloc[20, 1] = "."
            payload = quotes.to_csv(date_format="%Y-%m-%d").encode("utf-8")
            # Transport is isolated; real acquisition preparation, snapshot
            # regeneration verification and the actual child CLI remain active.
            with mock.patch.object(acquisition, "download_yields", return_value=(payload, acquisition.ENDPOINT)):
                acquired = acquisition.acquire_snapshot(
                    snapshot, str(source.index[0].date()), str(source.index[-1].date()),
                    (1, 2), max_fill_days=14, session=mock.Mock())
            snapshot_manifest = snapshot / "snapshot.json"
            original = {str(p.relative_to(snapshot)): p.read_bytes()
                        for p in snapshot.rglob("*") if p.is_file()}
            output = directory / "verified-model"
            command = [sys.executable, "-B", str(ROOT / "src/RWA/models/parameter_hierarchy/workflow.py"),
                       "--input", str(snapshot / "series"), "--input-manifest", str(snapshot_manifest),
                       "--output", str(output), "--maturities", "1", "2", "--yield-window", "32",
                       "--parameter-window", "16", "--steps", "2", "--paths", "2", "--substeps", "128",
                       "--forecast-mode", "recursive", "--time-basis", "act365f", "--missing-policy", "observed"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output / "manifest.json").read_text())
            evidence = manifest["yield_acquisition"]
            self.assertEqual(evidence["path"], str(snapshot_manifest.relative_to(ROOT)))
            self.assertEqual(evidence["sha256"], hashlib.sha256(snapshot_manifest.read_bytes()).hexdigest())
            self.assertEqual(evidence["quality"], acquired["quality"])
            self.assertEqual(evidence["quality"]["rows"], 96)
            self.assertEqual([s["excluded_missing_quotes"] for s in manifest["source_files"]], [1, 1])
            self.assertEqual(manifest["first_stage_rows"], (94 - 32 + 1) * 2)
            self.assertEqual(manifest["time_convention"]["historical_interval_count"], 93)
            intervals = pd.read_csv(output / "transition_intervals.csv")
            np.testing.assert_allclose(intervals.dt_years, annual_steps(source.index.delete([10, 20])),
                                       rtol=1e-13, atol=1e-16)
            self.assertEqual(original, {str(p.relative_to(snapshot)): p.read_bytes()
                                        for p in snapshot.rglob("*") if p.is_file()})
            # A preserved-raw mismatch aborts before the model can publish files.
            (snapshot / "raw/fred.csv").write_bytes(payload + b"\n")
            rejected_output = directory / "tampered-model"
            command[command.index("--output") + 1] = str(rejected_output)
            rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                      env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
            self.assertFalse(rejected_output.exists())

    def test_actual_cli_records_missing_policy_and_clock_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
            directory = Path(temporary)
            inputs = directory / "quotes"
            inputs.mkdir()
            source = stochastic_rates(n=100, seed=417, dimensions=2)
            for tenor in (1, 2):
                values = source[tenor].astype(object)
                values.iloc[10 + tenor] = "."
                pd.DataFrame({"observation_date": source.index, "DGS%d" % tenor: values.to_numpy(),
                              "yield_clean": np.full(len(source), 99.),
                              "is_imputed": np.zeros(len(source), dtype=bool)}).to_csv(
                    inputs / ("DGS%d.csv" % tenor), index=False)
            originals = {p.name: p.read_bytes() for p in inputs.iterdir()}
            output = directory / "elapsed-model"
            command = [sys.executable, "-B", str(ROOT / "src/RWA/models/parameter_hierarchy/workflow.py"),
                       "--input", str(inputs), "--output", str(output), "--maturities", "1", "2",
                       "--yield-window", "32", "--parameter-window", "16", "--steps", "3", "--paths", "2",
                       "--substeps", "128", "--forecast-mode", "recursive", "--recalibrate-every", "1",
                       "--time-basis", "act365f", "--missing-policy", "observed", "--dt", ".002"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["settings"]["time_basis"], "act365f")
            self.assertEqual(manifest["settings"]["missing_policy"], "observed")
            self.assertEqual(manifest["settings"]["dt"], .002)
            self.assertEqual([s["filled_quotes"] for s in manifest["source_files"]], [0, 0])
            self.assertEqual(manifest["first_stage_rows"], (98 - 32 + 1) * 2)
            retained_dates = source.index.delete([11, 12])
            expected_steps = annual_steps(retained_dates)
            clock = manifest["time_convention"]
            self.assertEqual(clock["basis"], "act365f")
            self.assertEqual(clock["historical_interval_count"], 97)
            self.assertAlmostEqual(clock["min_historical_dt_years"], expected_steps.min())
            self.assertAlmostEqual(clock["max_historical_dt_years"], expected_steps.max())
            self.assertAlmostEqual(clock["sum_historical_dt_years"], expected_steps.sum())
            self.assertEqual(clock["forecast_dt_years"], .002)
            intervals = pd.read_csv(output / "transition_intervals.csv", parse_dates=["start_date", "end_date"])
            self.assertEqual(intervals.start_date.tolist(), retained_dates[:-1].tolist())
            self.assertEqual(intervals.end_date.tolist(), retained_dates[1:].tolist())
            np.testing.assert_allclose(intervals.dt_years, expected_steps, atol=1e-16, rtol=1e-13)
            with np.load(output / "scenarios.npz") as scenarios:
                self.assertEqual(scenarios["states"].shape, (2, 4, 4, 2))
                self.assertTrue(np.isfinite(scenarios["states"]).all())
                np.testing.assert_array_equal(scenarios["elapsed_years"], np.arange(4) * .002)
            summary = pd.read_csv(output / "scenario_summary.csv")
            np.testing.assert_allclose(summary.elapsed_years, summary.step * .002, atol=1e-16, rtol=0)
            exported = pd.read_csv(output / "RAW/DGS1_with_parameters.csv")
            self.assertEqual(len(exported), 98)
            self.assertLess(exported.yield_clean.max(), 10.)
            self.assertEqual(originals, {p.name: p.read_bytes() for p in inputs.iterdir()})
            # A corrupted genuine token must fail before writing a model directory.
            corrupt = pd.read_csv(inputs / "DGS1.csv", dtype=str)
            corrupt.loc[3, "DGS1"] = "unparseable"
            corrupt.to_csv(inputs / "DGS1.csv", index=False)
            rejected_output = directory / "rejected-model"
            command[command.index("--output") + 1] = str(rejected_output)
            rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                      env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            self.assertEqual(rejected.returncode, 2, rejected.stdout + rejected.stderr)
            self.assertFalse(rejected_output.exists())


if __name__ == "__main__":
    unittest.main()
