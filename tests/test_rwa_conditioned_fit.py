"""Independent likelihood and information checks for supplied volatility paths."""

import importlib
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
core = importlib.import_module('src.RWA.models.parameter_hierarchy.core')


def fixture():
    return (np.array([4., 3.6, 3.9, 3.3, 3.5, 3.1]),
            np.array([.1, .4, .3, .8, .2, .6]),
            np.array([.1, .2, .08, .15, .1]))


def independent_nll(values, amplitudes, intervals, theta, mean):
    variance = amplitudes[1:]**2 * values[:-1] * intervals
    residual = np.diff(values) - theta*(mean-values[:-1])*intervals
    return .5*np.sum(np.log(2*np.pi*variance) + residual**2/variance)


class ConditionedDriftTests(unittest.TestCase):
    def test_known_weighted_normal_equations_and_information_match(self):
        values, amplitudes, intervals = fixture()
        left = values[:-1]
        derivative = np.diff(values)/intervals
        weights = intervals/(amplitudes[1:]**2 * left)
        design = np.column_stack([np.ones(len(left)), -left])
        information = design.T @ (weights[:, None]*design)
        expected = np.linalg.solve(information, design.T @ (weights*derivative))
        fitted = core.fit_conditioned_cir(values, amplitudes, intervals)
        np.testing.assert_allclose([fitted.a, fitted.theta], expected, rtol=1e-12)
        self.assertAlmostEqual(fitted.a, 21.93188655295006, places=11)
        self.assertAlmostEqual(fitted.theta, 6.15328509941603, places=12)
        self.assertAlmostEqual(fitted.theta_se, np.sqrt(np.linalg.inv(information)[1, 1]), places=12)
        self.assertAlmostEqual(fitted.nll, independent_nll(values, amplitudes, intervals,
                                                        fitted.theta, fitted.mu), places=12)
        self.assertFalse(hasattr(fitted, 'sigma'))
        self.assertFalse(fitted.deterministic)

    def test_independent_full_known_variance_likelihood_optimizer(self):
        values, amplitudes, intervals = fixture()

        def objective(log_parameters):
            speed, mean = np.exp(log_parameters)
            return independent_nll(values, amplitudes, intervals, speed, mean)

        answer = minimize(objective, np.log([6., 3.5]), method='BFGS', tol=1e-10)
        fitted = core.fit_conditioned_cir(values, amplitudes, intervals)
        self.assertAlmostEqual(answer.fun, fitted.nll, places=10)
        np.testing.assert_allclose([fitted.theta, fitted.mu], np.exp(answer.x), rtol=2e-6)

    def test_right_endpoint_amplitudes_are_used_and_initial_driver_is_not(self):
        values, amplitudes, intervals = fixture()
        fitted = core.fit_conditioned_cir(values, amplitudes, intervals)
        changed_initial = amplitudes.copy()
        changed_initial[0] = 9000.
        self.assertEqual(fitted, core.fit_conditioned_cir(values, changed_initial, intervals))
        changed_initial[0] = 0.
        self.assertEqual(fitted, core.fit_conditioned_cir(values, changed_initial, intervals))
        wrong_left_weights = intervals/(amplitudes[:-1]**2*values[:-1])
        design = np.column_stack([np.ones(len(intervals)), -values[:-1]])
        wrong = np.linalg.solve(design.T @ (wrong_left_weights[:, None]*design),
                                design.T @ (wrong_left_weights*np.diff(values)/intervals))
        self.assertGreater(np.max(np.abs(wrong-[fitted.a, fitted.theta])), 1.)
        changed_right = amplitudes.copy()
        changed_right[-1] *= 4.
        later = core.fit_conditioned_cir(values, changed_right, intervals)
        self.assertGreater(abs(later.theta-fitted.theta), .01)

    def test_fixed_theta_profiles_drift_without_refitting_variance(self):
        values, amplitudes, intervals = fixture()
        speed = 2.5
        weights = intervals/(amplitudes[1:]**2*values[:-1])
        expected_a = np.average(np.diff(values)/intervals+speed*values[:-1], weights=weights)
        fitted = core.fit_conditioned_cir(values, amplitudes, intervals, fixed_theta=speed)
        self.assertEqual(fitted.theta, speed)
        self.assertAlmostEqual(fitted.a, expected_a, places=12)
        self.assertAlmostEqual(fitted.nll, independent_nll(values, amplitudes, intervals,
                                                        speed, expected_a/speed), places=12)
        larger_amplitude = core.fit_conditioned_cir(values, 2*amplitudes, intervals, fixed_theta=speed)
        self.assertAlmostEqual(larger_amplitude.a, fitted.a, places=12)
        self.assertAlmostEqual(larger_amplitude.theta_se, 2*fitted.theta_se, places=12)
        self.assertNotAlmostEqual(larger_amplitude.nll, fitted.nll, places=6)

    def test_positive_mean_constraint_edge_is_solved_instead_of_clipping(self):
        values = [4.]
        for _ in range(8):
            values.append(values[-1] + (-1.-.5*values[-1])*.1)
        values = np.array(values)
        amplitudes = np.linspace(.1, .3, len(values))
        weights = .1/(amplitudes[1:]**2*values[:-1])
        lower_mean = np.mean(values)*1e-12
        z = lower_mean-values[:-1]
        theta = np.sum(weights*z*np.diff(values)/.1)/np.sum(weights*z*z)
        fitted = core.fit_conditioned_cir(values, amplitudes, .1)
        self.assertAlmostEqual(fitted.theta, theta, places=12)
        self.assertAlmostEqual(fitted.mu, lower_mean, places=20)
        self.assertAlmostEqual(fitted.a, theta*lower_mean, places=20)

    def test_elapsed_intervals_are_not_replaced_by_their_mean(self):
        values, amplitudes, intervals = fixture()
        actual = core.fit_conditioned_cir(values, amplitudes, intervals)
        averaged = core.fit_conditioned_cir(values, amplitudes, intervals.mean())
        self.assertGreater(independent_nll(values, amplitudes, intervals, averaged.theta, averaged.mu)
                           - actual.nll, .01)
        scalar = core.fit_conditioned_cir(values, amplitudes, .1)
        vector = core.fit_conditioned_cir(values, amplitudes, np.full(len(values)-1, .1))
        self.assertEqual(scalar, vector)

    def test_state_time_and_driver_units_transform_the_conditional_model_together(self):
        values, amplitudes, intervals = fixture()
        original = core.fit_conditioned_cir(values, amplitudes, intervals)
        state_scale, time_scale = .01, 365.
        converted = core.fit_conditioned_cir(values*state_scale,
            amplitudes*np.sqrt(state_scale/time_scale), intervals*time_scale)
        np.testing.assert_allclose([converted.a, converted.theta, converted.mu, converted.theta_se],
            [original.a*state_scale/time_scale, original.theta/time_scale,
             original.mu*state_scale, original.theta_se/time_scale], rtol=3e-13)
        self.assertAlmostEqual(converted.nll-original.nll, (len(values)-1)*np.log(state_scale), places=11)

    def test_constant_observations_do_not_fabricate_a_deterministic_diffusion(self):
        values = np.full(10, 4.)
        amplitudes = np.linspace(.1, .4, 10)
        fitted = core.fit_conditioned_cir(values, amplitudes)
        self.assertEqual(fitted.theta, 0.)
        self.assertTrue(np.isnan(fitted.mu))
        self.assertTrue(fitted.weak)
        self.assertFalse(fitted.deterministic)
        self.assertAlmostEqual(fitted.nll, .5*np.log(2*np.pi*amplitudes[1:]**2*4/252).sum(), places=12)
        repaired, audit = core.stabilize_conditioned_panel(values[:,None], amplitudes[:,None], [1])
        self.assertEqual(repaired[0].theta, .25)
        self.assertAlmostEqual(repaired[0].mu, 4.)
        self.assertEqual(audit[0]['nll_cost'], 0.)
        self.assertTrue(audit[0]['weak'])

    def test_invalid_states_drivers_variances_and_intervals_fail_explicitly(self):
        values, amplitudes, intervals = fixture()
        bad_values = [values[:3], values[:,None], values*0, -values, values*np.nan,
                      values.astype(str), values.astype(bool)]
        for invalid in bad_values:
            with self.subTest(values=invalid), self.assertRaises(ValueError):
                core.fit_conditioned_cir(invalid, amplitudes, intervals)
        bad_drivers = [amplitudes[:-1], amplitudes[:,None], -amplitudes,
                       amplitudes*0, amplitudes*np.nan, amplitudes.astype(str), amplitudes.astype(bool)]
        for invalid in bad_drivers:
            with self.subTest(driver=invalid), self.assertRaises(ValueError):
                core.fit_conditioned_cir(values, invalid, intervals)
        for h in (0, True, [.1], np.full(len(values)-1, np.inf)):
            with self.subTest(dt=h), self.assertRaises(ValueError):
                core.fit_conditioned_cir(values, amplitudes, h)
        for speed in (-1, True, np.nan):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                core.fit_conditioned_cir(values, amplitudes, intervals, fixed_theta=speed)
        with self.assertRaisesRegex(ValueError, 'boundary-aware'):
            core.fit_conditioned_cir(values, np.r_[amplitudes[:-1], 0.], intervals)
        with self.assertRaisesRegex(ValueError, 'nonfinite known transition variance'):
            core.fit_conditioned_cir(values, np.full(len(values), 1e200), intervals)


class ConditionedRidgeTests(unittest.TestCase):
    def test_all_maturity_positions_use_healthy_anchors_with_known_variance_budget(self):
        clock = np.arange(120)
        healthy, weak = 3+.1*np.sin(clock*.6), 3+.002*clock
        tenors = np.array([1,2,3,5,7,10,20,30])
        drivers = np.full((120,8), .02)
        for position in range(8):
            histories = np.tile(healthy[:,None], (1,8))
            histories[:,position] = weak
            originals = histories.copy(), drivers.copy()
            fits, audit = core.stabilize_conditioned_panel(histories, drivers, tenors, nll_budget=.1)
            row, fit = audit[position], fits[position]
            self.assertTrue(row['weak'])
            self.assertEqual(row['anchor_source'], 'tenor_anchors')
            self.assertEqual(row['variance_source'], 'observed_right_endpoint_higher_layer')
            self.assertGreater(fit.theta, 0.)
            self.assertLess(fit.theta, row['target_theta'])
            self.assertLessEqual(row['nll_cost'], .1+1e-10)
            self.assertAlmostEqual(fit.nll, independent_nll(weak, drivers[:,position],
                np.full(119,1/252), fit.theta, fit.mu), places=8)
            self.assertFalse(any(a['regularized'] for i,a in enumerate(audit) if i != position))
            for actual, original in zip((histories, drivers), originals):
                np.testing.assert_array_equal(actual, original)

    def test_unidentified_panel_uses_only_supplied_causal_priors_or_explicit_fallback(self):
        values = np.column_stack([3+.002*np.arange(80), 4+.003*np.arange(80)])
        drivers = np.full_like(values, .1)
        prior = np.array([.7,.9])
        _, audit = core.stabilize_conditioned_panel(values, drivers, [1,2],
                                                   prior_thetas=prior, nll_budget=2.)
        self.assertEqual([a['anchor_source'] for a in audit], ['previous_date']*2)
        np.testing.assert_array_equal([a['target_theta'] for a in audit], prior)
        _, fallback = core.stabilize_conditioned_panel(values, drivers, [1,2], fallback_theta=.4)
        self.assertEqual([a['anchor_source'] for a in fallback], ['explicit_fallback']*2)
        self.assertEqual([a['target_theta'] for a in fallback], [.4,.4])

    def test_panel_alignment_controls_and_driver_columns_are_validated(self):
        values = np.column_stack([3+.01*np.arange(8), 4+.02*np.arange(8)])
        drivers = np.full_like(values,.2)
        cases = [(values, drivers[:,:1], [1,2]), (values, drivers, [1,1]),
                 (values, drivers, [1,0]), (values, drivers, [1,np.nan]),
                 (values, drivers, [1]), (values, drivers*np.nan, [1,2])]
        for h,a,m in cases:
            with self.subTest(shape=a.shape, maturities=m), self.assertRaises(ValueError):
                core.stabilize_conditioned_panel(h,a,m)
        for settings in (dict(nll_budget=-1), dict(fallback_theta=0),
                         dict(prior_thetas=[1]), dict(prior_thetas=[1,0])):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                core.stabilize_conditioned_panel(values,drivers,[1,2],**settings)


if __name__ == '__main__':
    unittest.main()
