"""Sequential-year continuity and independent replay of every saved increment."""

import importlib
import json
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
workflow = importlib.import_module('src.RWA.models.parameter_hierarchy.workflow')
recursive = importlib.import_module('src.RWA.models.parameter_hierarchy.recursive')
core = importlib.import_module('src.RWA.models.parameter_hierarchy.core')


def history_fixture():
    # Full-rank, positive, deterministic histories at eight maturities.
    t = np.arange(40.)[:, None]
    j = np.arange(1., 9.)[None, :]
    return np.stack([3 + .2*np.sin(t*j*.17) + .05*j,
                     .4 + .015*np.cos(t*j*.23) + .004*j,
                     .1 + .007*np.sin(t*j*.31 + .2) + .001*j], axis=1)


def controlled_fit(values, maturities, dt, nll_budget, fallback_theta, prior_thetas=None):
    fits, audit = [], []
    for j in range(values.shape[1]):
        mean = float(np.mean(values[:, j]))
        speed = .3 + .02*j
        fits.append(core.CIRFit(speed*mean, speed, mean, .02, .01, 0., False))
        audit.append({'usable': True, 'nll_cost': 0., 'weak': False,
                      'regularized': False, 'anchor_source': 'unmodified'})
    return fits, audit


class AnnualWalkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def test_two_years_continue_state_history_rng_and_every_increment_replays(self):
        history = history_fixture()
        tenors = np.array(workflow.TENORS)
        def conditioned(values, driver, maturities, dt, nll_budget, fallback_theta, prior_thetas=None):
            return controlled_fit(values, maturities, dt, nll_budget, fallback_theta, prior_thetas)
        with mock.patch.object(recursive, 'stabilize_panel', side_effect=controlled_fit), \
                mock.patch.object(recursive, 'stabilize_conditioned_panel', side_effect=conditioned):
            reports = workflow.run_years(self.output, history, tenors, years=2,
                                         steps_per_year=4, dt=.25, substeps=2, seed=73)
            expected, _, _, final_history, final_dt = recursive.simulate_walk(
                history, tenors, steps=8, dt=.25, substeps=2, seed=73)
        self.assertEqual(len(reports), 2)
        trajectories = []
        current = history.copy()
        for year in (1, 2):
            directory = self.output/('year_%04d' % year)
            report = json.loads((directory/'manifest.json').read_text())
            self.assertEqual(report['covariance_records'], 8)
            with np.load(directory/'trajectory.npz') as artifact:
                self.assertEqual(artifact['states'].shape, (5, 3, 8))
                trajectories.append(artifact['states'].copy())
                np.testing.assert_array_equal(artifact['elapsed_years'], year-1+np.arange(5)*.25)
            archive = directory/'covariance'
            for step in range(8):
                with np.load(archive/('step_%06d.npz' % step)) as record:
                    np.testing.assert_array_equal(record['state_before'], current[-1])
                    level_cov = np.stack([np.cov(current[:, k], rowvar=False, ddof=1) for k in range(3)])
                    np.testing.assert_allclose(record['factor_covariance'], level_cov, rtol=1e-11, atol=1e-14)
                    for k in range(3):
                        np.testing.assert_allclose(record['cholesky'][k] @ record['cholesky'][k].T,
                                                   record['correlation'][k], atol=1e-12)
                    h = float(record['dt_years'])
                    np.testing.assert_allclose(record['brownian_covariance'], h*record['correlation'], atol=1e-12)
                    dw = np.array([record['cholesky'][k].dot(record['normal_shocks'][k])*np.sqrt(h)
                                   for k in range(3)])
                    np.testing.assert_allclose(record['brownian_increments'], dw, atol=1e-14)
                    before, c = record['state_before'], record['coefficients']
                    after = before.copy()
                    for k in (2, 1, 0):
                        amplitude = c[k, 2] if k == 2 else after[k+1]
                        after[k] = np.maximum(before[k] + c[k, 0]*(c[k, 1]-before[k])*h
                                              + amplitude*np.sqrt(before[k])*dw[k], 0.)
                    np.testing.assert_allclose(record['state_after'], after, atol=1e-14)
                    current = np.concatenate([current[1:], record['state_after'][None]], axis=0)
        joined = np.concatenate([trajectories[0], trajectories[1][1:]], axis=0)
        np.testing.assert_array_equal(joined, expected)
        np.testing.assert_array_equal(trajectories[0][-1], trajectories[1][0])
        np.testing.assert_array_equal(current, final_history)
        with np.load(self.output/'year_0002/restart.npz') as checkpoint:
            np.testing.assert_array_equal(checkpoint['history'], final_history)
            np.testing.assert_array_equal(checkpoint['history_dt'], final_dt)

    def test_nonannual_horizon_is_rejected_before_creating_a_year(self):
        with self.assertRaisesRegex(ValueError, 'one year'):
            workflow.run_years(self.output, history_fixture(), workflow.TENORS,
                               steps_per_year=2, dt=1/252)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_broadcast_history_bound_precedes_materialization(self):
        view = np.broadcast_to(np.ones((1,3,8)), (100000000,3,8))
        with mock.patch.object(recursive, '_numeric', side_effect=AssertionError('premature allocation')):
            with self.assertRaisesRegex(ValueError, 'memory bound'):
                recursive.simulate_walk(view, workflow.TENORS)

    def test_impossible_workload_fails_before_data_or_calibration(self):
        destination = self.output/'oversized'
        with mock.patch.object(workflow, 'read_yield_panel') as read, \
                mock.patch.object(workflow, 'calibrate_panel') as fit, \
                mock.patch('sys.stderr', new_callable=StringIO), \
                self.assertRaises(SystemExit) as failure:
            workflow.main(['--output', str(destination), '--substeps', '1000000000'])
        self.assertEqual(failure.exception.code, 2)
        read.assert_not_called()
        fit.assert_not_called()
        self.assertFalse(destination.exists())

    def test_completion_json_is_exclusive_and_atomic_on_failure(self):
        destination = self.output/'manifest.json'
        with self.assertRaises(ValueError):
            workflow._json_file(destination, {'bad': float('nan')})
        self.assertEqual(list(self.output.iterdir()), [])
        with mock.patch.object(workflow.os, 'link', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                workflow._json_file(destination, {'status': 'complete'})
        self.assertEqual(list(self.output.iterdir()), [])
        workflow._json_file(destination, {'status': 'complete'})
        before = destination.read_bytes()
        with self.assertRaises(FileExistsError):
            workflow._json_file(destination, {'status': 'changed'})
        self.assertEqual(destination.read_bytes(), before)
        self.assertEqual(list(self.output.iterdir()), [destination])

    def test_failure_never_publishes_a_completed_year(self):
        with mock.patch.object(workflow, 'simulate_walk', side_effect=ValueError('fit failure')):
            with self.assertRaisesRegex(ValueError, 'fit failure'):
                workflow.run_years(self.output, history_fixture(), workflow.TENORS)
        self.assertFalse((self.output/'year_0001/manifest.json').exists())
        self.assertFalse((self.output/'year_0001/covariance/manifest.json').exists())
        self.assertFalse((self.output/'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
