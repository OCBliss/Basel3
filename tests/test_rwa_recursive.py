"""Independent pathwise calibration, information timing and integration checks."""

import importlib
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


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
recursive = importlib.import_module('src.RWA.models.parameter_hierarchy.recursive')
workflow = importlib.import_module('src.RWA.models.parameter_hierarchy.workflow')
core = importlib.import_module('src.RWA.models.parameter_hierarchy.core')


def fixture(window=12):
    """A small, positive, varied history with distinct parameter branches."""
    base = np.array([[3.8, 4.2], [3.2, 3.6], [.8, 1.], [.25, .30]])
    clock = np.arange(window)[:, None, None]
    phase = np.arange(8).reshape(1, 4, 2)/3
    history = base[None] + .005*np.sin(clock*.7 + phase) + .001*clock
    coefficients = np.array([
        [[.7, .8], [3.2, 3.6], [.015, .017]],
        [[.8, .9], [.8, 1.], [.012, .014]],
        [[.9, 1.], [.25, .30], [.008, .010]],
    ])
    correlation = np.eye(8)
    correlation[0, 6] = correlation[6, 0] = .2
    return history, coefficients, np.linalg.cholesky(correlation), (1, 2)


def controlled_fit(histories, maturities, dt=1/252, nll_budget=2.,
                   fallback_theta=.25, prior_thetas=None):
    """Known fitted drifts/diffusions make information-flow checks independent."""
    fits = [core.CIRFit(a=1.5*values[-1], theta=1.5, mu=values[-1], sigma=.01,
                        theta_se=.05, nll=0., weak=False)
            for values in np.asarray(histories).T]
    audit = [dict(weak=False, regularized=False, nll_cost=0.,
                  anchor_source='unmodified', usable=True) for _ in fits]
    return fits, audit


class ShockTape:
    def __init__(self, draws):
        self.draws = list(draws)
        self.position = 0

    def standard_normal(self, shape):
        result = self.draws[self.position]
        self.position += 1
        if result.shape != shape:
            raise AssertionError('unexpected random draw shape %r, expected %r' % (shape, result.shape))
        return result.copy()


class RecursiveSimulationTests(unittest.TestCase):
    def simulate(self, **settings):
        history, coefficients, factor, maturities = fixture()
        options = dict(paths=2, steps=3, dt=1/252, seed=45, substeps=8,
                       recalibrate_every=1)
        options.update(settings)
        return recursive.simulate_recursive(history, coefficients, factor, maturities, **options)

    def test_disabled_and_unused_cadences_exactly_match_the_frozen_random_stream(self):
        history, coefficients, factor, maturities = fixture()
        settings = dict(paths=3, steps=4, dt=1/252, seed=37, substeps=8)
        expected, expected_projections = workflow.simulate(history[-1], coefficients, factor, **settings)
        for cadence in (0, 4, 8):
            with self.subTest(cadence=cadence), \
                    mock.patch.object(recursive, 'stabilize_panel', side_effect=AssertionError('unexpected refit')):
                actual, projections, diagnostics = recursive.simulate_recursive(
                    history, coefficients, factor, maturities, recalibrate_every=cadence, **settings)
            np.testing.assert_array_equal(actual, expected)
            np.testing.assert_array_equal(projections, expected_projections)
            self.assertEqual(diagnostics['recalibration_count'], 0)
            self.assertEqual(diagnostics['updates'], [])

    def test_disabled_refits_preserve_frozen_support_for_zero_parameter_speeds(self):
        history, coefficients, factor, maturities = fixture()
        coefficients[:, 0] = 0.
        expected, counts = workflow.simulate(history[-1], coefficients, factor,
                                             paths=2, steps=2, seed=17, substeps=8)
        actual, projections, diagnostics = recursive.simulate_recursive(
            history, coefficients, factor, maturities, paths=2, steps=2,
            seed=17, substeps=8, recalibrate_every=0)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(projections, counts)
        self.assertEqual(diagnostics['recalibration_count'], 0)
        with self.assertRaisesRegex(ValueError, 'prior speeds'):
            recursive.simulate_recursive(history, coefficients, factor, maturities,
                                         paths=2, steps=2, seed=17, substeps=8, recalibrate_every=1)

    def test_first_step_is_unchanged_then_actual_parameter_refits_change_future_states(self):
        frozen, _, _ = self.simulate(recalibrate_every=0)
        result, projections, diagnostics = self.simulate()
        np.testing.assert_array_equal(result[:, :2], frozen[:, :2])
        self.assertGreater(np.max(np.abs(result[:, 2:] - frozen[:, 2:])), 1e-8)
        self.assertEqual(diagnostics['recalibrated_origins'], [1, 2])
        self.assertEqual(diagnostics['recalibration_count'], 4)
        self.assertEqual(diagnostics['scalar_fits'], 4*3*2)
        self.assertGreater(diagnostics['max_coefficient_change_from_origin'], 0.)
        self.assertGreater(diagnostics['max_correlation_change_from_origin'], 0.)
        self.assertTrue(np.isfinite(result).all())
        self.assertEqual(result.shape, (2, 4, 4, 2))
        self.assertEqual(projections.shape, (4, 2))

    def test_every_branch_refits_every_tenor_using_only_the_own_path_trailing_history(self):
        history, coefficients, factor, maturities = fixture()
        recorded = []

        def capture(values, tenors, *args, **kwargs):
            prior = kwargs.get('prior_thetas', args[3] if len(args) > 3 else None)
            recorded.append((np.asarray(values).copy(), tuple(tenors),
                             None if prior is None else np.asarray(prior).copy()))
            return controlled_fit(values, tenors, *args, **kwargs)

        with mock.patch.object(recursive, 'stabilize_panel', side_effect=capture):
            result, _, diagnostics = recursive.simulate_recursive(
                history, coefficients, factor, maturities,
                paths=2, steps=3, dt=1/252, seed=45, substeps=8, recalibrate_every=1)
        self.assertEqual(len(recorded), 2*2*3)
        remaining = list(recorded)
        for origin in (1, 2):
            for path in (0, 1):
                trailing = np.concatenate([history, result[path, 1:origin+1]], axis=0)[-len(history):]
                for branch in (1, 2, 3):
                    expected = trailing[:, branch, :]
                    matches = [i for i, (values, tenors, prior) in enumerate(remaining)
                               if np.array_equal(values, expected) and tenors == maturities]
                    self.assertEqual(len(matches), 1, 'Each path/branch must consume its own observed prefix')
                    _, _, prior = remaining.pop(matches[0])
                    self.assertIsNotNone(prior)
                    np.testing.assert_allclose(prior, coefficients[branch-1, 0] if origin == 1 else [1.5, 1.5])
        self.assertEqual(remaining, [])
        self.assertEqual(len(diagnostics['updates']), 4)
        for update in diagnostics['updates']:
            self.assertEqual(update['observed_history_rows'], len(history)-update['origin_step'])
            self.assertEqual(update['simulated_history_rows'], update['origin_step'])

    def test_full_joint_residuals_are_standardized_from_the_current_path_history(self):
        history, coefficients, factor, maturities = fixture()
        residuals = []

        def capture(values, *args, **kwargs):
            residuals.append(np.asarray(values).copy())
            return core.innovation_correlation(values, *args, **kwargs)

        with mock.patch.object(recursive, 'stabilize_panel', side_effect=controlled_fit), \
                mock.patch.object(recursive, 'innovation_correlation', side_effect=capture):
            result, _, _ = recursive.simulate_recursive(history, coefficients, factor, maturities,
                paths=2, steps=2, dt=1/252, seed=45, substeps=8, recalibrate_every=1)
        self.assertEqual(len(residuals), 2)
        expected_residuals = []
        for path in (0, 1):
            trailing = np.concatenate([history[1:], result[path, 1:2]], axis=0)
            earlier = trailing[:-1]
            expected = np.empty_like(earlier)
            for t in range(len(earlier)):
                for tenor in range(2):
                    x, mu, theta, sigma = earlier[t, :, tenor]
                    expected[t, 0, tenor] = ((trailing[t+1, 0, tenor]-x-theta*(mu-x)/252)
                                               /(sigma*np.sqrt(x/252)))
                    for branch in (1, 2, 3):
                        old = earlier[t, branch, tenor]
                        mean = trailing[-1, branch, tenor]
                        expected[t, branch, tenor] = ((trailing[t+1, branch, tenor]-old-1.5*(mean-old)/252)
                                                      /(.01*np.sqrt(old/252)))
            expected_residuals.append(expected.reshape(len(earlier), 8))
        for actual, expected in zip(residuals, expected_residuals):
            np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-12)

    def test_rolling_window_remains_chronological_after_all_observed_rows_expire(self):
        history, coefficients, factor, maturities = fixture(window=5)
        recorded = []

        def capture(values, *args, **kwargs):
            recorded.append(np.asarray(values).copy())
            return controlled_fit(values, *args, **kwargs)

        with mock.patch.object(recursive, 'stabilize_panel', side_effect=capture):
            result, _, diagnostics = recursive.simulate_recursive(
                history, coefficients, factor, maturities, paths=1, steps=7,
                dt=1/252, seed=45, substeps=8, recalibrate_every=1)
        self.assertEqual(len(recorded), 6*3)
        for origin in range(1, 7):
            expected = np.concatenate([history, result[0, 1:origin+1]], axis=0)[-5:]
            for branch in range(3):
                np.testing.assert_array_equal(recorded[(origin-1)*3+branch], expected[:, branch+1])
        for update in diagnostics['updates']:
            self.assertEqual(update['observed_history_rows'], max(0, 5-update['origin_step']))
            self.assertEqual(update['simulated_history_rows'], min(5, update['origin_step']))

    def test_altering_one_path_shock_does_not_change_the_other_path(self):
        draws = [np.full((2, 4, 2), .2), np.full((2, 4, 2), -.1), np.full((2, 4, 2), .3)]
        changed = [array.copy() for array in draws]
        changed[0][0, 1, 0] += 2.
        original_rng = np.random.default_rng
        outputs = []
        for tape in (draws, changed):
            with mock.patch.object(recursive.np.random, 'default_rng', return_value=ShockTape(tape)), \
                    mock.patch.object(recursive, 'stabilize_panel', side_effect=controlled_fit):
                outputs.append(self.simulate(substeps=1)[0])
        self.assertIs(np.random.default_rng, original_rng)
        np.testing.assert_array_equal(outputs[0][1], outputs[1][1])
        self.assertGreater(np.max(np.abs(outputs[0][0] - outputs[1][0])), 0.)

    def test_a_later_shock_cannot_change_earlier_paths_or_recalibration_inputs(self):
        draws = [np.full((2, 4, 2), .2), np.full((2, 4, 2), -.1), np.full((2, 4, 2), .3)]
        changed = [array.copy() for array in draws]
        changed[-1] += 5.
        results, recorded = [], []
        for tape in (draws, changed):
            seen = []

            def capture(values, *args, **kwargs):
                seen.append(np.asarray(values).copy())
                return controlled_fit(values, *args, **kwargs)

            with mock.patch.object(recursive.np.random, 'default_rng', return_value=ShockTape(tape)), \
                    mock.patch.object(recursive, 'stabilize_panel', side_effect=capture):
                results.append(self.simulate(substeps=1)[0])
            recorded.append(seen)
        np.testing.assert_array_equal(results[0][:, :3], results[1][:, :3])
        self.assertEqual(len(recorded[0]), len(recorded[1]))
        for earlier, later in zip(*recorded):
            np.testing.assert_array_equal(earlier, later)
        self.assertGreater(np.max(np.abs(results[0][:, -1] - results[1][:, -1])), 0.)

    def test_seed_reproducibility_input_immutability_and_no_unused_final_refit(self):
        history, coefficients, factor, maturities = fixture()
        originals = [a.copy() for a in (history, coefficients, factor)]
        options = dict(paths=2, steps=4, seed=108, substeps=8, recalibrate_every=2)
        a, p, diagnostics = recursive.simulate_recursive(history, coefficients, factor, maturities, **options)
        b, q, repeated = recursive.simulate_recursive(history, coefficients, factor, maturities, **options)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(p, q)
        self.assertEqual(diagnostics, repeated)
        self.assertEqual(diagnostics['recalibrated_origins'], [2])
        self.assertEqual(diagnostics['recalibration_count'], 2)
        for actual, original in zip((history, coefficients, factor), originals):
            np.testing.assert_array_equal(actual, original)

    def test_invalid_shapes_values_and_work_bounds_fail_before_any_fit(self):
        history, coefficients, factor, maturities = fixture()
        variants = [(history[:3], coefficients, factor, maturities),
                    (history[:, :3], coefficients, factor, maturities),
                    (history, coefficients, np.eye(7), maturities),
                    (history, coefficients, factor, (1, 1)),
                    (history, coefficients, factor, (1,)),
                    (history * np.nan, coefficients, factor, maturities),
                    (-history, coefficients, factor, maturities)]
        with mock.patch.object(recursive, 'stabilize_panel', side_effect=AssertionError('fit before validation')):
            for h, c, l, m in variants:
                with self.subTest(shape=h.shape, maturities=m), self.assertRaises(ValueError):
                    recursive.simulate_recursive(h, c, l, m, paths=2, steps=2, substeps=8)
            for settings in (dict(paths=10**9), dict(steps=10**9), dict(substeps=10**9),
                             dict(recalibrate_every=-1),
                             dict(recalibrate_every=True), dict(paths=0), dict(substeps=0),
                             dict(dt=0), dict(shrinkage=0), dict(nll_budget=-1)):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    self.simulate(**settings)

    def test_mixed_zero_history_failure_names_the_path_origin_and_parameter(self):
        history, coefficients, factor, maturities = fixture()
        history[-3, 1, 0] = 0.
        with self.assertRaises(ValueError) as caught:
            recursive.simulate_recursive(history, coefficients, factor, maturities,
                paths=1, steps=2, seed=10, substeps=8, recalibrate_every=1)
        message = str(caught.exception).lower()
        self.assertIn('path', message)
        self.assertIn('1', message)
        self.assertIn('mu', message)
        self.assertIn('zero', message)


class RecursiveCommandTests(unittest.TestCase):
    def test_real_cli_uses_observed_parameter_history_and_records_pathwise_updates(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as temporary:
            directory = Path(temporary)
            inputs = directory/'quotes'
            inputs.mkdir()
            dates = pd.bdate_range('2010-01-04', periods=96)
            rng = np.random.default_rng(417)
            means = np.array([3., 4.])
            values = np.empty((len(dates), 2))
            values[0] = means
            for position in range(1, len(dates)):
                previous = values[position-1]
                values[position] = previous + 8*(means-previous)/252 + .4*np.sqrt(previous/252)*rng.normal(size=2)
            for tenor in (1, 2):
                pd.DataFrame({'observation_date': dates, 'DGS%d' % tenor: values[:, tenor-1]}).to_csv(
                    inputs/('DGS%d.csv' % tenor), index=False)
            originals = {path.name: path.read_bytes() for path in inputs.iterdir()}
            output = directory/'recursive-model'
            command = [sys.executable, '-B', str(ROOT/'src/RWA/models/parameter_hierarchy/workflow.py'),
                       '--input', str(inputs), '--output', str(output), '--maturities', '1', '2',
                       '--yield-window', '32', '--parameter-window', '16', '--steps', '3',
                       '--paths', '2', '--substeps', '32', '--forecast-mode', 'recursive',
                       '--recalibrate-every', '1']
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output/'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'complete')
            self.assertIn('pathwise recursive', manifest['forecast_mode'])
            self.assertEqual(manifest['forecast_origin'], str(dates[-1].date()))
            diagnostics = manifest['recursive_calibration']
            self.assertEqual(diagnostics['rolling_window'], 16)
            self.assertEqual(diagnostics['recalibrated_origins'], [1, 2])
            self.assertEqual(diagnostics['recalibration_count'], 4)
            self.assertEqual({(r['path'], r['origin_step']) for r in diagnostics['updates']},
                             {(0, 1), (1, 1), (0, 2), (1, 2)})
            with np.load(output/'scenarios.npz') as scenarios:
                self.assertEqual(scenarios['states'].shape, (2, 4, 4, 2))
                self.assertTrue(np.isfinite(scenarios['states']).all())
            self.assertEqual(originals, {path.name: path.read_bytes() for path in inputs.iterdir()})


if __name__ == '__main__':
    unittest.main()
