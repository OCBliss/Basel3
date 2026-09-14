"""Deterministic checks of the chronological xi -> sigma -> rate update."""

from copy import deepcopy
from dataclasses import replace
import importlib
from pathlib import Path
import sys
import unittest
from unittest import mock
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
recursive = importlib.import_module('src.RWA.models.parameter_hierarchy.recursive')
core = importlib.import_module('src.RWA.models.parameter_hierarchy.core')
covariance = importlib.import_module('src.RWA.models.parameter_hierarchy.covariance')


def fixture(window=12):
    clock = np.arange(window)[:, None, None]
    phase = np.arange(6).reshape(1, 3, 2)
    base = np.array([[3.8, 4.2], [.8, 1.], [.25, .30]])
    return base[None] + .005 * np.sin(clock * .7 + phase) + .001 * clock


def controlled_fit(values, maturities, dt, nll_budget=2., fallback_theta=.25, prior_thetas=None):
    fits = [core.CIRFit(a=.4 * (column[-1] + .3), theta=.4, mu=column[-1] + .3,
                        sigma=.12, theta_se=.1, nll=0., weak=False)
            for column in np.asarray(values).T]
    audit = [dict(weak=False, regularized=False, nll_cost=0., usable=True,
                  anchor_source='unmodified') for _ in fits]
    return fits, audit


def conditioned_adapter(fitter):
    """Discard sigma entirely so a drift-only mock cannot hide sigma access."""
    def conditioned(values, drivers, maturities, *args, **kwargs):
        fits, audit = fitter(values, maturities, *args, **kwargs)
        return [core.DriftFit(a=fit.a, theta=fit.theta, mu=fit.mu, theta_se=fit.theta_se,
                             nll=fit.nll, weak=fit.weak, deterministic=fit.deterministic)
                for fit in fits], audit
    return conditioned


class MemoryArchive:
    def __init__(self):
        self.records = []

    def append(self, step, elapsed_years, dt, matrices, before, after, **extras):
        self.records.append(deepcopy(dict(step=step, elapsed_years=elapsed_years, dt=dt,
                                         matrices=matrices, before=before, after=after, **extras)))


class ChronologicalWalkTests(unittest.TestCase):
    def run_walk(self, history=None, **settings):
        options = dict(steps=2, dt=.004, normal_shocks=iter([np.full((3, 2), .2)] * 32))
        options.update(settings)
        with mock.patch.object(recursive, 'stabilize_panel', side_effect=controlled_fit), \
                mock.patch.object(recursive, 'stabilize_conditioned_panel',
                                  side_effect=conditioned_adapter(controlled_fit)):
            return recursive.simulate_walk(fixture() if history is None else history, (1, 2), **options)

    def test_real_rate_drift_uses_right_endpoint_driver_weights_and_only_xi_fits_diffusion(self):
        rate = np.array([4., 4.4, 4.1, 4.5, 4.2, 4.35, 4., 4.2])
        sigma = np.array([.2, .8, .1, .5, .2, .9, .15, .6])
        xi = np.array([.12, .14, .11, .15, .13, .16, .12, .14])
        intervals = np.array([.1, .2, .1, .15, .1, .2, .1])
        history = np.stack([rate, sigma, xi], axis=1)[:, :, None]
        x = rate[:-1]
        derivative = np.diff(rate) / intervals
        weights = intervals / (sigma[1:] ** 2 * x)
        design = np.column_stack([np.ones(len(x)), -x])
        intercept, speed = np.linalg.lstsq(np.sqrt(weights)[:, None] * design,
                                          np.sqrt(weights) * derivative, rcond=None)[0]
        with mock.patch.object(recursive, 'stabilize_panel', wraps=core.stabilize_panel) as terminal, \
                mock.patch.object(recursive, 'stabilize_conditioned_panel',
                                  wraps=core.stabilize_conditioned_panel) as conditioned:
            coefficients, audits = recursive._calibrate(history, (1,), intervals, 2., .25, None)
        self.assertEqual(terminal.call_count, 1)
        self.assertEqual(conditioned.call_count, 2)
        np.testing.assert_array_equal(terminal.call_args.args[0], history[:, 2])
        np.testing.assert_array_equal(conditioned.call_args_list[0].args[1], history[:, 1])
        np.testing.assert_array_equal(conditioned.call_args_list[1].args[1], history[:, 2])
        self.assertAlmostEqual(coefficients[0, 0, 0], speed, places=10)
        self.assertAlmostEqual(coefficients[0, 1, 0], intercept / speed, places=11)
        self.assertNotIn('raw_sigma', audits[0][0])
        self.assertNotIn('raw_sigma', audits[1][0])
        self.assertIn('raw_sigma', audits[2][0])

    def test_first_increment_matches_hand_calculation_using_new_xi_then_new_sigma(self):
        history = fixture()
        dt = .04
        normal = np.array([[.2, -.3], [.8, .5], [1.1, .7]])
        matrices = covariance.family_covariances(history, dt)
        increments = np.array([matrices['cholesky'][family] @ normal[family] * np.sqrt(dt)
                               for family in range(3)])
        rate, sigma, xi = history[-1]
        expected_xi = xi + .4 * .3 * dt + .12 * np.sqrt(xi) * increments[2]
        expected_sigma = sigma + .4 * .3 * dt + expected_xi * np.sqrt(sigma) * increments[1]
        expected_rate = rate + .4 * .3 * dt + expected_sigma * np.sqrt(rate) * increments[0]
        archive = MemoryArchive()
        actual, hits, diagnostics, final, intervals = self.run_walk(
            history, steps=1, dt=dt, normal_shocks=iter([normal]), archive=archive)
        np.testing.assert_allclose(actual[1], np.array([expected_rate, expected_sigma, expected_xi]), atol=1e-15)
        self.assertEqual(hits.sum(), 0)
        self.assertEqual(diagnostics['calibration_count'], 1)
        self.assertEqual(diagnostics['matrix_refresh_count'], 1)
        wrong_sigma = sigma + .4 * .3 * dt + xi * np.sqrt(sigma) * increments[1]
        wrong_rate = rate + .4 * .3 * dt + sigma * np.sqrt(rate) * increments[0]
        self.assertGreater(np.max(np.abs(actual[1, 1] - wrong_sigma)), 1e-4)
        self.assertGreater(np.max(np.abs(actual[1, 0] - wrong_rate)), 1e-4)
        np.testing.assert_array_equal(final[-1], actual[-1])
        self.assertEqual(intervals[-1], dt)
        coefficients = archive.records[0]['coefficients']
        np.testing.assert_array_equal(coefficients[0, 2], actual[1, 1])
        np.testing.assert_array_equal(coefficients[1, 2], actual[1, 2])
        np.testing.assert_array_equal(coefficients[2, 2], [.12, .12])
        for family, source in enumerate(('updated sigma state', 'updated xi state', 'CIR fitted diffusion')):
            for record in archive.records[0]['calibration_audit']['families'][family]:
                self.assertEqual(record['diffusion_source'], source)
                if family < 2:
                    self.assertNotIn('raw_sigma', record)

    def test_every_substep_including_first_recalibrates_all_families_before_draw(self):
        history = fixture()
        clock = np.linspace(.001, .006, len(history) - 1)
        fit_calls, conditioned_calls, matrix_calls, events = [], [], [], []
        archive = MemoryArchive()

        def capture_matrices(values, dt, regularization=0.):
            events.append('matrices')
            matrix_calls.append(values.copy())
            return covariance.family_covariances(values, dt, regularization)

        def capture_fit(values, tenors, dt, *args, **kwargs):
            events.append('fit')
            fit_calls.append((values.copy(), np.asarray(dt).copy(), deepcopy(kwargs['prior_thetas'])))
            return controlled_fit(values, tenors, dt, *args, **kwargs)

        def capture_conditioned(values, drivers, tenors, dt, *args, **kwargs):
            conditioned_calls.append((values.copy(), drivers.copy(), np.asarray(dt).copy()))
            return conditioned_adapter(capture_fit)(values, drivers, tenors, dt, *args, **kwargs)

        def tape():
            for _ in range(6):
                events.append('draw')
                yield np.full((3, 2), .2)

        with mock.patch.object(recursive, 'stabilize_panel', side_effect=capture_fit), \
                mock.patch.object(recursive, 'stabilize_conditioned_panel', side_effect=capture_conditioned), \
                mock.patch.object(recursive, 'family_covariances', side_effect=capture_matrices):
            reported, hits, diagnostics, final, final_clock = recursive.simulate_walk(
                history, (1, 2), steps=2, dt=.006, substeps=3, history_dt=clock,
                normal_shocks=tape(), archive=archive)
        self.assertEqual(events, ['matrices', 'fit', 'fit', 'fit', 'draw'] * 6)
        self.assertEqual(len(archive.records), 6)
        self.assertEqual(len(conditioned_calls), 12)
        self.assertEqual(diagnostics['scalar_fits'], 6 * 3 * 2)
        self.assertEqual(diagnostics['matrix_refresh_count'], 6)
        observed_states = [record['after'] for record in archive.records]
        for increment in range(6):
            expected = np.concatenate([history, np.array(observed_states[:increment]).reshape(-1, 3, 2)])[-len(history):]
            expected_clock = np.r_[clock, np.full(increment, .002)][-(len(history) - 1):]
            np.testing.assert_array_equal(matrix_calls[increment], expected)
            for family in range(3):
                values, actual_clock, prior = fit_calls[3 * increment + family]
                np.testing.assert_array_equal(values, expected[:, family])
                np.testing.assert_array_equal(actual_clock, expected_clock)
                if increment == 0:
                    self.assertIsNone(prior)
                else:
                    np.testing.assert_array_equal(prior, [.4, .4])
                if family < 2:
                    conditioned_values, drivers, conditional_clock = conditioned_calls[2 * increment + family]
                    np.testing.assert_array_equal(conditioned_values, expected[:, family])
                    np.testing.assert_array_equal(drivers, expected[:, family + 1])
                    np.testing.assert_array_equal(conditional_clock, expected_clock)
            record = archive.records[increment]
            self.assertEqual(record['step'], increment)
            self.assertAlmostEqual(record['elapsed_years'], increment * .002)
            np.testing.assert_array_equal(record['before'], expected[-1])
            self.assertEqual(record['coefficients'].shape, (3, 3, 2))
        np.testing.assert_array_equal(reported[1], observed_states[2])
        np.testing.assert_array_equal(reported[2], observed_states[5])
        np.testing.assert_array_equal(final, np.concatenate([history, observed_states])[-len(history):])
        np.testing.assert_array_equal(final_clock, np.r_[clock, np.full(6, .002)][-11:])

    def test_new_family_factor_changes_the_immediate_substep_with_coefficients_fixed(self):
        history = fixture()
        draws = [np.full((3, 2), .2), np.array([[1., .2], [.3, -.2], [.4, .5]])]
        results, records = [], []
        for replace_second in (False, True):
            calls = []
            archive = MemoryArchive()

            def matrices(values, dt, regularization=0.):
                result = covariance.family_covariances(values, dt, regularization)
                calls.append(1)
                if replace_second and len(calls) == 2:
                    correlation = np.array([[1., -.7], [-.7, 1.]])
                    result['correlation'][0] = correlation
                    result['cholesky'][0] = np.linalg.cholesky(correlation)
                    result['brownian_covariance'][0] = dt * correlation
                return result

            with mock.patch.object(recursive, 'family_covariances', side_effect=matrices):
                results.append(self.run_walk(history, steps=1, substeps=2,
                                             normal_shocks=iter(draws), archive=archive)[0])
            records.append(archive.records)
        np.testing.assert_array_equal(records[0][0]['after'], records[1][0]['after'])
        np.testing.assert_array_equal(records[0][1]['coefficients'], records[1][1]['coefficients'])
        np.testing.assert_array_equal(results[0][1, 1:], results[1][1, 1:])
        self.assertGreater(np.max(np.abs(results[0][1, 0] - results[1][1, 0])), 1e-4)

    def test_later_draws_cannot_change_earlier_states_or_calibration_inputs(self):
        original = [np.full((3, 2), .2)] * 3
        changed = [*original[:2], np.full((3, 2), 2.)]
        outputs, captured = [], []
        for tape in (original, changed):
            calls = []

            def capture_fit(values, *args, **kwargs):
                calls.append(values.copy())
                return controlled_fit(values, *args, **kwargs)

            with mock.patch.object(recursive, 'stabilize_panel', side_effect=capture_fit), \
                    mock.patch.object(recursive, 'stabilize_conditioned_panel',
                                      side_effect=conditioned_adapter(capture_fit)):
                outputs.append(recursive.simulate_walk(fixture(), (1, 2), steps=3,
                                                      normal_shocks=iter(tape))[0])
            captured.append(calls)
        np.testing.assert_array_equal(outputs[0][:3], outputs[1][:3])
        for a, b in zip(*captured):
            np.testing.assert_array_equal(a, b)
        self.assertGreater(np.max(np.abs(outputs[0][3] - outputs[1][3])), 0.)

    def test_serial_continuation_preserves_generator_and_causal_ridge_anchors(self):
        history = fixture()
        clock = np.linspace(.001, .006, len(history) - 1)

        def anchored_fit(values, tenors, dt, *args, **kwargs):
            fits, audit = controlled_fit(values, tenors, dt, *args, **kwargs)
            prior = kwargs['prior_thetas']
            if prior is not None:
                fits = [replace(fit, theta=prior[i] + .01, a=(prior[i] + .01) * fit.mu)
                        for i, fit in enumerate(fits)]
            return fits, audit

        with mock.patch.object(recursive, 'stabilize_panel', side_effect=anchored_fit), \
                mock.patch.object(recursive, 'stabilize_conditioned_panel',
                                  side_effect=conditioned_adapter(anchored_fit)):
            whole = recursive.simulate_walk(history, (1, 2), steps=6, substeps=2,
                                            seed=198, history_dt=clock)
            first = recursive.simulate_walk(history, (1, 2), steps=3, substeps=2,
                                            seed=198, history_dt=clock)
            second = recursive.simulate_walk(first[3], (1, 2), steps=3, substeps=2,
                                             history_dt=first[4], rng_state=first[2]['rng_state'],
                                             prior_thetas=first[2]['prior_thetas'])
        np.testing.assert_array_equal(np.concatenate([first[0], second[0][1:]]), whole[0])
        np.testing.assert_array_equal(first[1] + second[1], whole[1])
        np.testing.assert_array_equal(second[3], whole[3])
        np.testing.assert_array_equal(second[4], whole[4])
        self.assertEqual(second[2]['rng_state'], whole[2]['rng_state'])
        self.assertEqual(second[2]['prior_thetas'], whole[2]['prior_thetas'])

    def test_projection_happens_in_chain_before_downstream_multipliers(self):
        history = fixture()
        normal = np.array([[.5, .5], [-1000., -1000.], [.4, .4]])
        result, hits, *_ = self.run_walk(history, steps=1, normal_shocks=iter([normal]))
        np.testing.assert_array_equal(result[1, 1], [0., 0.])
        np.testing.assert_array_equal(hits[1], [1, 1])
        np.testing.assert_allclose(result[1, 0], history[-1, 0] + .4 * .3 * .004, atol=1e-15)

    def test_insufficient_refinement_fails_before_drawing_or_archiving(self):
        archive = MemoryArchive()
        consumed = []

        def tape():
            consumed.append(True)
            yield np.zeros((3, 2))

        with self.assertRaisesRegex(ValueError, 'increment 0.*increase substeps'):
            self.run_walk(steps=1, dt=3., normal_shocks=tape(), archive=archive)
        self.assertEqual(consumed, [])
        self.assertEqual(archive.records, [])

    def test_bad_inputs_bounds_and_no_path_axis_are_rejected(self):
        h = fixture()
        for invalid in (h[:3], h[:, :2], h[None], h.reshape(len(h), 6),
                        h.astype(str), h.astype(bool), -h, h * np.nan):
            with self.subTest(shape=invalid.shape), self.assertRaises(ValueError):
                self.run_walk(invalid)
        for settings in (dict(steps=0), dict(substeps=0), dict(steps=10**12), dict(substeps=10**12),
                         dict(dt=0), dict(dt=True), dict(regularization=1.1), dict(seed=True),
                         dict(prior_thetas=np.ones((2, 2))), dict(prior_thetas=np.zeros((3, 2))),
                         dict(history_dt=[.01]), dict(rng_state={'invalid': 1}, normal_shocks=None),
                         dict(rng_state={}, normal_shocks=iter([]))):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.run_walk(**settings)
        for tape in ([], [np.zeros((2, 3, 2))], [np.zeros((3, 2)) * np.nan]):
            with self.subTest(tape=tape), self.assertRaisesRegex(ValueError, 'increment 0'):
                self.run_walk(normal_shocks=iter(tape))


if __name__ == '__main__':
    unittest.main()
