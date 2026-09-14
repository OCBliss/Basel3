"""Independent deterministic checks of separate family level dependence."""

import importlib
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
covariance = importlib.import_module('src.RWA.models.parameter_hierarchy.covariance')


def history_fixture(dimensions=8):
    """Orthogonal deterministic level variations with three distinct mixes."""
    basis = np.array([[(-1.) ** bin(row & column).count('1')
                       for column in range(1, dimensions + 1)] for row in range(32)])
    history = np.empty((32, 3, dimensions))
    for family in range(3):
        mixing = np.eye(dimensions)
        for row in range(dimensions):
            for column in range(row):
                mixing[row, column] = ((row + column + family) % 3 - 1) * .15 * (family + 1)
        scales = np.linspace(.01, .09, dimensions) * (family + 1)
        history[:, family] = (basis @ mixing.T) * scales + 2 + family
    return history


def manual_level_covariance(values):
    """Pairwise sample definition, independent of the implementation's products."""
    observations, dimensions = values.shape
    means = [sum(float(value) for value in values[:, j]) / observations
             for j in range(dimensions)]
    return np.array([[sum((float(row[i]) - means[i]) * (float(row[j]) - means[j])
                         for row in values) / (observations - 1)
                      for j in range(dimensions)] for i in range(dimensions)])


class FamilyCovarianceTests(unittest.TestCase):
    def test_all_three_eight_tenor_level_covariances_match_pairwise_definition(self):
        history = history_fixture()
        original = history.copy()
        step = 1 / 365
        result = covariance.family_covariances(history, step)
        self.assertEqual(result['regularization'], 0.)
        for name in ('factor_covariance', 'raw_correlation', 'correlation',
                     'cholesky', 'brownian_covariance'):
            self.assertEqual(result[name].shape, (3, 8, 8), name)
        for family in range(3):
            expected = manual_level_covariance(history[:, family])
            deviations = np.sqrt(np.diag(expected))
            correlation = expected / np.outer(deviations, deviations)
            np.testing.assert_allclose(result['factor_covariance'][family], expected,
                                       rtol=1e-13, atol=1e-16)
            np.testing.assert_allclose(result['raw_correlation'][family], correlation, atol=2e-14)
            np.testing.assert_array_equal(result['correlation'][family], result['raw_correlation'][family])
            factor = result['cholesky'][family]
            np.testing.assert_array_equal(np.triu(factor, 1), np.zeros((8, 8)))
            np.testing.assert_allclose(factor @ factor.T, correlation, atol=2e-14)
            np.testing.assert_allclose(result['brownian_covariance'][family], step * correlation, atol=1e-16)
        np.testing.assert_array_equal(history, original)

    def test_level_units_and_offsets_preserve_correlation_but_change_covariance(self):
        history = history_fixture()
        scales = np.arange(1, 25).reshape(3, 8) / 3
        offsets = np.arange(24).reshape(3, 8) - 20.
        before = covariance.family_covariances(history, .01)
        after = covariance.family_covariances(history * scales + offsets, .01)
        for family in range(3):
            expected = before['factor_covariance'][family] * np.outer(scales[family], scales[family])
            np.testing.assert_allclose(after['factor_covariance'][family], expected, rtol=2e-13, atol=1e-15)
        np.testing.assert_allclose(after['correlation'], before['correlation'], atol=1e-13)
        np.testing.assert_allclose(after['cholesky'], before['cholesky'], atol=1e-13)

    def test_family_and_maturity_order_are_preserved_without_pooled_estimation(self):
        history = history_fixture()
        families, tenors = [2, 0, 1], [7, 0, 6, 1, 5, 2, 4, 3]
        before = covariance.family_covariances(history, .01)
        after = covariance.family_covariances(history[:, families][:, :, tenors], .01)
        for name in ('factor_covariance', 'raw_correlation', 'correlation', 'brownian_covariance'):
            expected = before[name][families][:, tenors][:, :, tenors]
            np.testing.assert_allclose(after[name], expected, atol=1e-14)
        changed = history.copy()
        changed[:, 1, 3] += np.linspace(-.1, .1, len(history))
        new = covariance.family_covariances(changed, .01)
        for family in (0, 2):
            for name in ('factor_covariance', 'correlation', 'cholesky', 'brownian_covariance'):
                np.testing.assert_array_equal(new[name][family], before[name][family])
        self.assertGreater(np.max(np.abs(new['correlation'][1] - before['correlation'][1])), .01)

    def test_rank_deficiency_requires_explicit_recorded_regularization(self):
        history = np.empty((10, 3, 8))
        for family in range(3):
            history[:, family] = np.arange(10)[:, None] * np.arange(1, 9)[None, :] + family
        with self.assertRaisesRegex(ValueError, 'family 0.*rank deficient'):
            covariance.family_covariances(history, .01)
        result = covariance.family_covariances(history, .01, regularization=.2)
        self.assertEqual(result['regularization'], .2)
        expected_correlation = .8 * np.ones((8, 8)) + .2 * np.eye(8)
        for family in range(3):
            np.testing.assert_allclose(result['factor_covariance'][family],
                                       manual_level_covariance(history[:, family]))
            np.testing.assert_allclose(result['raw_correlation'][family], 1.)
            np.testing.assert_allclose(result['correlation'][family], expected_correlation)
            factor = result['cholesky'][family]
            np.testing.assert_allclose(factor @ factor.T, expected_correlation, atol=1e-15)

    def test_constant_columns_are_explicitly_undefined_even_with_regularization(self):
        history = history_fixture()
        for level in (0., 1.23):
            history[:, 1, 3] = level
            for alpha in (0., .1, 1.):
                with self.subTest(level=level, regularization=alpha), \
                        self.assertRaisesRegex(ValueError, r'family 1.*zero-variance.*\[3\]'):
                    covariance.family_covariances(history, .01, regularization=alpha)

    def test_two_observations_work_for_one_maturity_but_not_eight(self):
        history = np.array([[[1.], [2.], [3.]], [[3.], [5.], [7.]]])
        result = covariance.family_covariances(history, .25)
        np.testing.assert_array_equal(result['factor_covariance'][:, 0, 0], [2., 4.5, 8.])
        np.testing.assert_array_equal(result['correlation'], np.ones((3, 1, 1)))
        with self.assertRaisesRegex(ValueError, 'rank deficient'):
            covariance.family_covariances(np.concatenate([history] * 8, axis=2), .25)

    def test_invalid_data_shape_types_scales_and_timestep_fail_descriptively(self):
        history = history_fixture()
        invalid = [history[:1], history[:, :2], history[:, :, :0], history.reshape(32, 24),
                   history.astype(str), history.astype(complex), history.astype(bool),
                   history.astype(object), history * np.nan, history * np.inf]
        overflow = history.copy()
        overflow[0, 0, 0] = np.finfo(float).max
        invalid.append(overflow)
        for values in invalid:
            with self.subTest(shape=values.shape, dtype=values.dtype), self.assertRaises(ValueError):
                covariance.family_covariances(values, .01)
        for step in (0., -1., True, '0.1', np.inf, np.nan, 10**500):
            with self.subTest(dt=step), self.assertRaises(ValueError):
                covariance.family_covariances(history, step)
        for alpha in (-.1, 1.1, True, '.1', np.inf, np.nan):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                covariance.family_covariances(history, .01, regularization=alpha)


class FamilyBrownianIncrementTests(unittest.TestCase):
    def test_eight_tenor_brownian_covariance_and_family_independence_are_exact(self):
        # This is a finite algebraic identity, not a random simulation. The
        # 48 signed coordinate vectors have exact population covariance I_24.
        # Transform each one individually through the single-increment API.
        step = .004
        matrices = covariance.family_covariances(history_fixture(), step)
        inputs, outputs = [], []
        for family in range(3):
            for maturity in range(8):
                for sign in (-1., 1.):
                    shock = np.zeros((3, 8))
                    shock[family, maturity] = sign * np.sqrt(24.)
                    inputs.append(shock)
                    outputs.append(covariance.brownian_increments(shock, matrices['cholesky'], step))
        inputs, outputs = np.array(inputs), np.array(outputs)
        np.testing.assert_array_equal(outputs.mean(axis=0), np.zeros((3, 8)))
        for family in range(3):
            np.testing.assert_allclose(inputs[:, family].T @ inputs[:, family] / len(inputs), np.eye(8))
            actual = outputs[:, family].T @ outputs[:, family] / len(outputs)
            np.testing.assert_allclose(actual, matrices['brownian_covariance'][family], atol=1e-17)
            for other in range(3):
                if family != other:
                    cross_covariance = outputs[:, family].T @ outputs[:, other] / len(outputs)
                    np.testing.assert_array_equal(cross_covariance, np.zeros((8, 8)))

    def test_each_draw_uses_its_own_factor_once_and_sqrt_timestep(self):
        matrices = covariance.family_covariances(history_fixture(), .01)
        normals = np.arange(24).reshape(3, 8) / 10 - 1.
        saved = normals.copy()
        factors = matrices['cholesky'].copy()
        actual = covariance.brownian_increments(normals, factors, .01)
        expected = np.stack([np.sqrt(.01) * factors[f] @ normals[f] for f in range(3)])
        np.testing.assert_allclose(actual, expected, atol=1e-16)
        np.testing.assert_allclose(covariance.brownian_increments(normals, factors, .04), 2 * actual)
        changed = normals.copy()
        changed[1] += 2.
        changed_result = covariance.brownian_increments(changed, factors, .01)
        np.testing.assert_array_equal(changed_result[[0, 2]], actual[[0, 2]])
        np.testing.assert_array_equal(normals, saved)
        np.testing.assert_array_equal(factors, matrices['cholesky'])

    def test_draws_reject_ensembles_pooled_factors_and_invalid_cholesky(self):
        matrices = covariance.family_covariances(history_fixture(), .01)
        factor = matrices['cholesky']
        normals = np.zeros((3, 8))
        for invalid in (np.zeros((2, 3, 8)), np.zeros(24), np.zeros((8, 3)),
                        normals.astype(str), normals.astype(bool), normals + np.nan):
            with self.subTest(shape=invalid.shape), self.assertRaises(ValueError):
                covariance.brownian_increments(invalid, factor, .01)
        bad_factors = [np.eye(24), np.eye(32), factor * 2., factor.transpose(0, 2, 1),
                       factor * np.nan, factor.astype(complex)]
        for invalid in bad_factors:
            with self.subTest(shape=invalid.shape), self.assertRaises(ValueError):
                covariance.brownian_increments(normals, invalid, .01)
        for step in (0, -1, True, '0.1', np.inf, np.nan):
            with self.subTest(dt=step), self.assertRaises(ValueError):
                covariance.brownian_increments(normals, factor, step)


if __name__ == '__main__':
    unittest.main()
