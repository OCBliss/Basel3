"""Independent statistical, causal, numerical and file-contract hierarchy checks."""

import importlib
import importlib.util
import json
import os
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / "src/RWA" / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = importlib.import_module("src.RWA.models.parameter_hierarchy.core")
workflow = importlib.import_module("src.RWA.models.parameter_hierarchy.workflow")


def rates(n=160, seed=8, d=3):
    rng = np.random.default_rng(seed)
    values = np.empty((n, d))
    means = np.linspace(3, 5, d)
    values[0] = means
    for t in range(1, n):
        values[t] = (values[t-1] + 8 * (means - values[t-1]) / 252 +
                     .4 * np.sqrt(values[t-1] / 252) * rng.normal(size=d))
    return pd.DataFrame(values, index=pd.bdate_range("2020-01-01", periods=n),
                        columns=list(workflow.TENORS[:d])).rename_axis("observation_date")


class ProfileLikelihoodTests(unittest.TestCase):
    def test_independent_optimizer_and_original_likelihood_agree(self):
        # An independently parameterized nonlinear optimizer, not the new solver.
        x = rates(1500, d=1).iloc[:, 0].to_numpy()
        dt = 1 / 252

        def objective(p):
            theta, mu, sigma = np.exp(p)
            variance = sigma**2 * x[:-1] * dt
            residual = np.diff(x) - theta * (mu - x[:-1]) * dt
            return .5 * np.sum(np.log(2*np.pi*variance) + residual**2 / variance)

        answer = minimize(objective, np.log([8., 3., .4]), method="BFGS", tol=1e-8)
        fitted = core.fit_cir(x)
        self.assertAlmostEqual(fitted.nll, answer.fun, places=6)
        np.testing.assert_allclose([fitted.theta, fitted.mu, fitted.sigma],
                                   np.exp(answer.x), rtol=2e-4)

    def test_scale_equivariance_including_ridge_repair(self):
        panel = rates(100, d=3)
        first, a = core.stabilize_panel(panel.to_numpy(), panel.columns)
        converted, b = core.stabilize_panel(panel.to_numpy() / 100, panel.columns)
        for f, c, x, y in zip(first, converted, a, b):
            self.assertAlmostEqual(f.theta, c.theta, places=8)
            self.assertAlmostEqual(f.mu/100, c.mu, places=8)
            self.assertAlmostEqual(f.sigma/10, c.sigma, places=8)
            self.assertAlmostEqual(x['nll_cost'], y['nll_cost'], places=8)

    def test_ridge_repair_is_coupled_and_likelihood_budgeted(self):
        # A near-linear upward path drives theta to its zero boundary.
        rng = np.random.default_rng(12)
        x = 3 + .002*np.arange(150) + rng.normal(0, .004, 150)
        raw = core.fit_cir(x)
        self.assertTrue(raw.weak)
        fits, audit = core.stabilize_panel(x[:, None], [1], nll_budget=.1,
                                          fallback_theta=10.)
        fitted = fits[0]
        self.assertGreater(fitted.theta, 0)
        self.assertTrue(np.isfinite(fitted.mu))
        self.assertLessEqual(fitted.nll - raw.nll, .1 + 1e-9)
        self.assertAlmostEqual(fitted.a, fitted.theta * fitted.mu)
        self.assertTrue(audit[0]['weak'])
        self.assertEqual(audit[0]['anchor_source'], 'explicit_fallback')
        # Directly evaluate the original Euler likelihood after healing.
        variance = fitted.sigma**2*x[:-1]/252
        residual = np.diff(x) - fitted.theta*(fitted.mu-x[:-1])/252
        nll = .5*np.sum(np.log(2*np.pi*variance)+residual**2/variance)
        self.assertAlmostEqual(nll, fitted.nll, places=8)

    def test_ridge_detection_and_repair_apply_to_every_maturity_position(self):
        healthy = rates(800, d=1).iloc[:, 0].to_numpy()
        weak = 3 + .0005*np.arange(800)
        for j in range(8):
            sample = np.tile(healthy[:, None], (1, 8))
            sample[:, j] = weak
            fits, audit = core.stabilize_panel(sample, workflow.TENORS)
            self.assertTrue(audit[j]['weak'])
            self.assertEqual(audit[j]['anchor_source'], 'tenor_anchors')
            self.assertLessEqual(audit[j]['nll_cost'], 2 + 1e-8)
            for k in range(8):
                if k != j:
                    self.assertFalse(audit[k]['regularized'])

    def test_constant_and_zero_histories_are_explicitly_unidentified(self):
        for x in [np.ones(10)*4, np.zeros(10)]:
            fit = core.fit_cir(x)
            self.assertTrue(fit.weak)
            self.assertTrue(fit.deterministic)
            self.assertEqual(fit.sigma, 0.)
            self.assertEqual(fit.a-fit.theta*x[-1], 0.)
        with self.assertRaisesRegex(ValueError, 'boundary-aware'):
            core.fit_cir([1., 0., 1., 2.])

    def test_bad_inputs_are_rejected(self):
        for x in [[1,2,3], [1,2,np.nan,4], [1,2,np.inf,4], [1,2,-1,4]]:
            with self.assertRaises(ValueError):
                core.fit_cir(x)
        for dt in [0, -1, np.nan, True]:
            with self.assertRaises(ValueError):
                core.fit_cir([1,2,3,4], dt)
        with self.assertRaises(ValueError):
            core.stabilize_panel(np.ones((10,2)), [1,1])


class EndogenousHierarchyTests(unittest.TestCase):
    def test_three_branches_date_alignment_order_and_no_future_influence(self):
        source = rates(125)
        first = workflow.calibrate_panel(source, 64)
        second = workflow.calibrate_parameters(first, 32)
        self.assertEqual(set(second.parameter), {'mu','theta','sigma'})
        self.assertEqual(second.observation_date.min(), source.index[64+32-2])
        self.assertEqual(len(second), (125-64-32+2)*3*3)
        shuffled = workflow.calibrate_panel(source.sample(frac=1, random_state=2),64)
        pd.testing.assert_frame_equal(first, shuffled)
        early = workflow.calibrate_panel(source.iloc[:-4],64)
        pd.testing.assert_frame_equal(early, first.loc[first.observation_date<=source.index[-5]].reset_index(drop=True))
        earlier_second = workflow.calibrate_parameters(early,32)
        pd.testing.assert_frame_equal(earlier_second, second.loc[
            second.observation_date<=source.index[-5]].reset_index(drop=True))

    def test_known_parameter_histories_match_direct_cir_fits(self):
        source = rates(1500, d=1)
        records = []
        for date, row in source.iterrows():
            records.append(dict(observation_date=date, maturity=1,
                                mu=row[1], theta=row[1]*2, sigma=row[1]/10))
        first = pd.DataFrame(records)
        second = workflow.calibrate_parameters(first,1500)
        for p in workflow.PARAMETERS:
            fitted = core.fit_cir(first[p])
            row = second.loc[second.parameter==p].iloc[0]
            self.assertFalse(row.regularized)
            np.testing.assert_allclose(row[['theta','mu','sigma']].astype(float),
                                       [fitted.theta,fitted.mu,fitted.sigma])

    def test_second_pass_does_not_fill_missing_or_duplicate_parameter_states(self):
        first = workflow.calibrate_panel(rates(),64)
        for corrupt in ['missing','duplicate','zero']:
            bad = first.copy()
            if corrupt=='missing': bad.loc[10,'mu'] = np.nan
            if corrupt=='duplicate': bad = pd.concat([bad,bad.iloc[[10]]])
            if corrupt=='zero': bad.loc[10,'sigma'] = 0.
            with self.assertRaises(ValueError):
                workflow.calibrate_parameters(bad,32)

    def test_constant_parameter_histories_have_no_manufactured_volatility(self):
        first = pd.DataFrame([dict(observation_date=d,maturity=m,mu=4.,theta=.8,sigma=.3)
                              for d in pd.bdate_range('2020-01-01',periods=40)
                              for m in [1,2,3]])
        result = workflow.calibrate_parameters(first,32)
        self.assertTrue((result.sigma==0).all())
        self.assertTrue(result.deterministic.all())

class WalkHistoryTests(unittest.TestCase):
    @staticmethod
    def inputs(rows=60, yield_window=8, parameter_window=6):
        dates = pd.bdate_range("2000-01-03", periods=rows)
        yields = pd.DataFrame({1: 3 + np.arange(rows)/1000,
                               2: 4 + np.arange(rows)/900}, index=dates)
        first = pd.DataFrame([
            dict(observation_date=date, maturity=tenor,
                 mu=30 + position/100, theta=2 + position/500,
                 sigma=.2 + position/1000 + tenor/100)
            for position, date in enumerate(dates) if position >= yield_window-1
            for tenor in (1, 2)])
        second = pd.DataFrame([
            dict(observation_date=date, maturity=tenor, parameter=parameter,
                 theta=3., mu=4., sigma=.01 + position/10000 + tenor/1000)
            for position, date in enumerate(dates)
            if position >= yield_window + parameter_window - 2
            for tenor in (1, 2) for parameter in workflow.PARAMETERS])
        return yields, first, second

    def test_rate_sigma_xi_mapping_and_exact_calibrated_history_warmup(self):
        source, first, second = self.inputs()
        history, dates = workflow.walk_history(source, first, second, 48)
        self.assertEqual(history.shape, (48, 3, 2))
        self.assertEqual(dates.tolist(), source.index[12:].tolist())
        np.testing.assert_array_equal(history[:, 0], source.iloc[12:].to_numpy())
        expected_sigma = first.pivot(index='observation_date', columns='maturity', values='sigma').loc[dates]
        expected_xi = second.loc[second.parameter == 'sigma'].pivot(
            index='observation_date', columns='maturity', values='sigma').loc[dates]
        np.testing.assert_array_equal(history[:, 1], expected_sigma)
        np.testing.assert_array_equal(history[:, 2], expected_xi)
        self.assertLess(history[:, 0].max(), 5.)  # fitted long-run mu is above 30
        with self.assertRaisesRegex(ValueError, 'insufficient calibrated history'):
            workflow.walk_history(source, first, second, 49)

    def test_ten_year_history_counts_calibrated_states_after_both_warmups(self):
        source, first, second = self.inputs(rows=2520+8+6-2)
        history, dates = workflow.walk_history(source, first, second, 2520)
        self.assertEqual(len(history), 2520)
        self.assertEqual(dates[0], source.index[12])
        with self.assertRaisesRegex(ValueError, '2520 complete'):
            workflow.walk_history(source.iloc[:-1],
                                  first.loc[first.observation_date <= source.index[-2]],
                                  second.loc[second.observation_date <= source.index[-2]], 2520)

    def test_cutoff_and_row_order_preserve_only_the_known_history(self):
        source, first, second = self.inputs()
        cutoff = source.index[-5]
        early_source = source.loc[:cutoff]
        early_first = first.loc[first.observation_date <= cutoff]
        early_second = second.loc[second.observation_date <= cutoff]
        expected, dates = workflow.walk_history(early_source, early_first, early_second, 12)
        actual, actual_dates = workflow.walk_history(early_source.iloc[::-1],
            early_first.sample(frac=1, random_state=3), early_second.sample(frac=1, random_state=4), 12)
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(actual_dates.tolist(), dates.tolist())
        self.assertEqual(actual_dates[-1], cutoff)
        np.testing.assert_array_equal(actual[:, 0], source.loc[dates].to_numpy())

    def test_missing_and_duplicate_endogenous_states_are_not_filled(self):
        source, first, second = self.inputs()
        latest = (second.parameter == 'sigma') & (second.observation_date == source.index[-1])
        bad = second.copy()
        bad.loc[latest, 'sigma'] = np.nan
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            workflow.walk_history(source, first, bad, 12)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            workflow.walk_history(source, first, pd.concat([second, second.loc[latest]]), 12)


class HierarchyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.input = self.directory/'FRED'
        self.input.mkdir()
        self.source = rates(110,d=2)
        for tenor in self.source:
            frame = self.source[[tenor]].rename(columns={tenor:'DGS%d'%tenor}).reset_index()
            frame.iloc[::-1].to_csv(self.input/('DGS%d.csv'%tenor),index=False)

    def test_relocated_package_entry_point_and_repository_boundary(self):
        self.assertEqual(workflow.ROOT, ROOT)
        self.assertEqual(workflow.repository_path('RWA/FRED'), ROOT/'RWA/FRED')
        result = subprocess.run(
            [sys.executable, '-B', '-m', 'src.RWA.models.parameter_hierarchy.workflow', '--help'],
            cwd=ROOT, capture_output=True, text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--parameter-window', result.stdout)

    def test_cli_defaults_export_full_year_contract_and_existing_rebuild_schema(self):
        out = self.directory/'result'
        command = ['--input',str(self.input),'--output',str(out),'--maturities','1','2',
                   '--yield-window','64','--parameter-window','32','--history-window','12']

        def fixed_walk(history, maturities, steps, dt, substeps, archive, **settings):
            # The serializer is tested independently of numerical evolution;
            # actual ordered updates and fixed-shock identities have engine tests.
            self.assertEqual((steps, dt, substeps), (252, 1/252, 1))
            d = len(maturities)
            states = history[-1] + np.arange(steps+1)[:, None, None]*.0001
            identity = np.broadcast_to(np.eye(d), (3, d, d)).copy()
            matrices = dict(factor_covariance=identity, correlation=identity,
                            cholesky=identity, brownian_covariance=dt*identity)
            for step in range(steps):
                archive.append(step, step*dt, dt, matrices, states[step], states[step+1])
            diagnostics = {'rng_state': {}, 'prior_thetas': np.ones((3,d)).tolist()}
            trailing = np.concatenate([history, states[1:]])[-len(history):]
            return states, np.zeros((3,d), dtype=int), diagnostics, trailing, np.full(len(history)-1, dt)

        with mock.patch.object(workflow, 'simulate_walk', side_effect=fixed_walk), redirect_stdout(StringIO()):
            workflow.main(command)
        manifest = json.loads((out/'manifest.json').read_text())
        self.assertEqual(manifest['status'],'complete')
        second = pd.read_csv(out/'parameter_dynamics.csv')
        self.assertEqual(set(second.parameter),set(workflow.PARAMETERS))
        raw = pd.read_csv(out/'RAW/DGS1_with_parameters.csv')
        self.assertEqual(list(raw.columns),['Unnamed: 0','observation_date','DGS1','yield_clean','theta','mu','sigma'])
        self.assertTrue(raw.iloc[:63][['theta','mu','sigma']].isna().all().all())
        self.assertEqual(manifest['schema_version'], 2)
        self.assertEqual(manifest['state_names'], ['rate', 'sigma', 'xi'])
        self.assertEqual(manifest['walk_history_rows'], 12)
        self.assertEqual(manifest['settings']['years'], 1)
        self.assertEqual(manifest['settings']['steps_per_year'], 252)
        self.assertEqual(manifest['settings']['dt'], 1/252)
        self.assertEqual(manifest['settings']['substeps'], 1)
        self.assertEqual(manifest['covariance_shape_per_set'], [3, 2, 2])
        year = out/'year_0001'
        with np.load(year/'trajectory.npz') as data:
            self.assertEqual(data['states'].shape, (253,3,2))
            self.assertEqual(data['state_names'].tolist(), ['rate', 'sigma', 'xi'])
            np.testing.assert_allclose(data['elapsed_years'], np.arange(253)/252, rtol=0, atol=2e-16)
        trajectory = pd.read_csv(year/'trajectory.csv')
        self.assertEqual(list(trajectory.columns), ['step','elapsed_years','state','maturity','value'])
        self.assertEqual(len(trajectory), 253*3*2)
        archive = json.loads((year/'covariance/manifest.json').read_text())
        self.assertEqual(archive['increments'], 252)
        self.assertEqual(len(list((year/'covariance').glob('step_*.npz'))), 252)
        with np.load(year/'covariance/step_000251.npz') as final:
            self.assertEqual(final['factor_covariance'].shape, (3,2,2))
            self.assertAlmostEqual(final['elapsed_end_years'].item(), 1.)
        self.assertFalse((out/'scenarios.npz').exists())
        self.assertFalse((out/'scenario_summary.csv').exists())
        # Exercise the actual existing rebuild consumer, not just CSV headers.
        rebuild = load_module('rwa_hierarchy_rebuild', 'data/parameters/rebuild.py')
        target = self.directory/'rebuilt'
        target.mkdir()
        curves = [pd.read_csv(out/'CURVE'/(p+'_curve.csv'),parse_dates=['observation_date'])
                  for p in ['mu','theta','sigma']]
        with mock.patch.object(rebuild,'DGS_RAW_DIR',str(out/'RAW')), \
                mock.patch.object(rebuild,'MLE_VOL_RAW_DIR',str(target)), redirect_stdout(StringIO()):
            for tenor in [1,2]:
                name = 'DGS%d'%tenor
                rebuild.rebuild_dgs_file(name,rebuild.MATURITY_MAP[name],*curves)
                rebuilt = pd.read_csv(target/(name+'_with_parameters.csv'))
                original = pd.read_csv(out/'RAW'/(name+'_with_parameters.csv')).drop(columns='Unnamed: 0')
                pd.testing.assert_frame_equal(rebuilt,original)
        snapshot = (out/'manifest.json').read_bytes()
        with self.assertRaises(SystemExit) as repeated, redirect_stdout(StringIO()), \
                mock.patch('sys.stderr', new_callable=StringIO):
            workflow.main(command)
        self.assertEqual(repeated.exception.code, 2)
        self.assertEqual(snapshot,(out/'manifest.json').read_bytes())

    def test_default_history_rejects_2520_raw_rows_before_any_calibration(self):
        source = rates(2520, d=2)
        with mock.patch.object(workflow, 'read_yield_panel', return_value=(source, [])), \
                mock.patch.object(workflow, 'calibrate_panel', side_effect=AssertionError('fit before warmup check')), \
                mock.patch('sys.stderr', new_callable=StringIO) as error, self.assertRaises(SystemExit) as failure:
            workflow.main(['--output', str(self.directory/'insufficient')])
        self.assertEqual(failure.exception.code, 2)
        self.assertIn('5290 common source observations', error.getvalue())
        self.assertIn('2520 complete calibrated', error.getvalue())
        self.assertFalse((self.directory/'insufficient').exists())

    def test_dates_causal_filling_and_as_of(self):
        frame = pd.read_csv(self.input/'DGS1.csv')
        frame.loc[5,'DGS1'] = np.nan
        frame.to_csv(self.input/'DGS1.csv',index=False)
        panel,meta = workflow.read_yield_panel(self.input,[1,2],str(self.source.index[-3].date()))
        self.assertEqual(panel.index.max(),self.source.index[-3])
        self.assertEqual(meta[0]['filled_quotes'],1)
        missing_date = pd.Timestamp(frame.loc[5,'observation_date'])
        position = panel.index.get_loc(missing_date)
        self.assertEqual(panel.iloc[position,0],panel.iloc[position-1,0])
        frame.loc[2,'observation_date'] = frame.loc[3,'observation_date']
        frame.to_csv(self.input/'DGS1.csv',index=False)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            workflow.read_yield_panel(self.input,[1,2])

    def test_pipeline_manager_resolves_serial_config_against_isolated_inputs(self):
        config = yaml.safe_load((ROOT/'pipeline/rwa_hierarchy/config.yaml').read_text())
        self.assertEqual(
            (ROOT/'src'/config['scripts']['rwa_hierarchy']['path']).resolve(),
            Path(workflow.__file__).resolve(),
        )
        config['parameters'].update(output_dir=str(self.directory/'managed'),
                                    yield_window=64,parameter_window=32,recent_rows=0,
                                    history_window=12,years=1,steps_per_year=252,substeps=1)
        config['scripts']['rwa_hierarchy']['args'] += ['--input',str(self.input),'--maturities','1','2']
        config['scripts']['rwa_hierarchy']['inputs'] = [str(self.input/'DGS*.csv')]
        config['log_root'] = str(self.directory/'logs')
        path = self.directory/'workflow.yaml'
        path.write_text(yaml.safe_dump(config))
        result = subprocess.run([sys.executable,'-B',str(ROOT/'pipeline/Task_manager_Global_yaml_driven.py'),
                                 '--config',str(path),'--dry-run'],cwd=ROOT,capture_output=True,text=True,
                                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('--history-window 12', result.stdout)
        self.assertIn('--years 1', result.stdout)
        self.assertNotIn('--paths ', result.stdout)
        self.assertFalse((self.directory/'managed').exists())

    def test_paths_cannot_escape_repository_including_symlinks(self):
        for path in ['../forbidden',ROOT.parent/'elsewhere']:
            with self.assertRaises(ValueError):
                workflow.repository_path(path)
        (self.directory/'escape').symlink_to('/private/tmp',target_is_directory=True)
        with self.assertRaises(ValueError):
            workflow.repository_path(self.directory/'escape'/'result')


if __name__=='__main__':
    unittest.main()
