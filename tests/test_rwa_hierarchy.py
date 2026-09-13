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

    def test_noise_benchmark_replays_both_passes_and_reports_estimator_variation(self):
        source = rates(100,d=2)
        first = workflow.calibrate_panel(source,48)
        second = workflow.calibrate_parameters(first,24)
        report = workflow.parameter_noise_diagnostic(source,first,second,48,24,
                                                     replicates=2,seed=15)
        self.assertTrue(report['comparable'],report['failures'])
        self.assertEqual(len(report['rows']),6)
        self.assertTrue(any(row['null_median']>0 for row in report['rows']))
        repeated = workflow.parameter_noise_diagnostic(source,first,second,48,24,
                                                       replicates=2,seed=15)
        self.assertEqual(report,repeated)


class JointSimulationTests(unittest.TestCase):
    def fixture(self):
        state = np.array([[4.],[3.],[1.],[.4]])
        c = np.array([[[.5],[3.],[.2]],[[.6],[1.],[.1]],[[.8],[.4],[.15]]])
        corr = np.array([[1.,.2,-.1,.55],[.2,1.,.1,.2],[-.1,.1,1.,-.1],[.55,.2,-.1,1.]])
        return state,c,np.linalg.cholesky(corr)

    def test_conditional_drift_covariance_and_cross_layer_dependence(self):
        state,c,l = self.fixture()
        rng = np.random.default_rng(53)
        z = rng.normal(size=(100000,4,1))
        z = np.concatenate([z,-z])  # antithetic exact zero mean
        s = np.broadcast_to(state,z.shape)
        dt = 1e-4
        future,hits = core.step_hierarchy(s,c,z,l,dt)
        self.assertEqual(hits.sum(),0)
        changes = (future-s).reshape(-1,4)
        expected_drift = np.array([-1.,0.,0.,0.])
        np.testing.assert_allclose(changes.mean(axis=0)/dt,expected_drift,atol=1e-10)
        diffusion = np.array([.4*2,.2*np.sqrt(3),.1,.15*np.sqrt(.4)])
        expected_cov = np.outer(diffusion,diffusion)*(l@l.T)*dt
        # Antithetic pairs provide 100,000 independent covariance observations.
        # Relative error is inappropriate for small off-diagonal covariances.
        covariance_se = np.sqrt((np.outer(np.diag(expected_cov), np.diag(expected_cov)) +
                                 expected_cov**2) / 100000)
        self.assertTrue(np.all(np.abs(np.cov(changes,rowvar=False,bias=True)-expected_cov)
                               < 6*covariance_se))

    def test_updated_volatility_would_introduce_the_predicted_drift(self):
        state,c,l = self.fixture()
        rng = np.random.default_rng(63)
        z = rng.normal(size=(200000,4))
        z = np.vstack([z,-z])
        dt = 1e-4
        dw = z@l.T*np.sqrt(dt)
        sigma_new = .4 + .15*np.sqrt(.4)*dw[:,3]
        wrong_noise = sigma_new*2*dw[:,0]
        predicted = .55*.15*np.sqrt(.4)*2
        self.assertAlmostEqual(wrong_noise.mean()/dt,predicted,delta=.001)

    def test_singular_and_constant_residuals_have_a_valid_joint_factor(self):
        rng = np.random.default_rng(8)
        x = rng.normal(size=(10,2))
        r = np.column_stack([x,x,np.ones(10),x[:,0]])
        corr,l,audit = core.innovation_correlation(r,.05)
        np.testing.assert_allclose(l@l.T,corr,atol=1e-12)
        np.testing.assert_allclose(np.diag(corr),1.)
        self.assertGreaterEqual(audit['min_eigenvalue'],.05-1e-12)
        self.assertEqual(audit['constant_columns'],[4])
        self.assertAlmostEqual(corr[0,2],.95)

    def test_reproducibility_projection_accounting_and_memory_limit(self):
        state,c,l = self.fixture()
        a,h = workflow.simulate(state,c,l,paths=20,steps=5,seed=8)
        b,j = workflow.simulate(state,c,l,paths=20,steps=5,seed=8)
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(h,j)
        c[:,:,0] = [[0,0,20],[0,0,20],[0,0,20]]
        s,hits = core.step_hierarchy(state,c,np.full_like(state,-10),np.eye(4),.1)
        self.assertTrue((s>=0).all())
        self.assertEqual(hits[1:].sum(),3)
        with self.assertRaisesRegex(ValueError,'memory'):
            workflow.simulate(state,c,l,paths=10**9)

    def test_large_mean_reversion_requires_a_smaller_step(self):
        state,c,l = self.fixture()
        c[0,0,0] = 3000.
        with self.assertRaisesRegex(ValueError,'substeps'):
            workflow.simulate(state,c,l,paths=2,steps=2,substeps=1)
        a,h = workflow.simulate(state,c,l,paths=2,steps=2,substeps=32)
        self.assertTrue(np.isfinite(a).all())

    def test_time_refinement_converges_to_known_deterministic_cir_mean(self):
        state = np.array([[4.],[3.],[8.],[0.]])
        c = np.zeros((3,3,1))
        exact = 3+np.exp(-8/12)
        errors = []
        for refinement in [1,4,16]:
            result,_ = workflow.simulate(state,c,np.eye(4),paths=1,steps=1,dt=1/12,
                                         substeps=refinement)
            errors.append(abs(result[0,-1,0,0]-exact))
        self.assertGreater(errors[0],errors[1])
        self.assertGreater(errors[1],errors[2])
        self.assertLess(errors[2],.01)


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

    def test_real_cli_exports_complete_hierarchy_and_existing_first_stage_schema(self):
        out = self.directory/'result'
        command = [sys.executable,'-B',str(ROOT/'src/RWA/models/parameter_hierarchy/workflow.py'),
                   '--input',str(self.input),'--output',str(out),'--maturities','1','2',
                   '--yield-window','64','--parameter-window','32','--paths','8','--steps','3']
        # An absolute script entry point must also work from another directory;
        # moving the source must not make data resolution depend on the caller.
        result = subprocess.run(command,cwd=self.directory,capture_output=True,text=True,
                                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode,0,result.stderr)
        manifest = json.loads((out/'manifest.json').read_text())
        self.assertEqual(manifest['status'],'complete')
        second = pd.read_csv(out/'parameter_dynamics.csv')
        self.assertEqual(set(second.parameter),set(workflow.PARAMETERS))
        raw = pd.read_csv(out/'RAW/DGS1_with_parameters.csv')
        self.assertEqual(list(raw.columns),['Unnamed: 0','observation_date','DGS1','yield_clean','theta','mu','sigma'])
        self.assertTrue(raw.iloc[:63][['theta','mu','sigma']].isna().all().all())
        with np.load(out/'scenarios.npz') as data:
            self.assertEqual(data['states'].shape,(8,4,4,2))
            self.assertEqual(data['correlation'].shape,(8,8))
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
        repeat = subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(repeat.returncode,0)
        self.assertEqual(snapshot,(out/'manifest.json').read_bytes())

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

    def test_pipeline_manager_executes_the_new_config_against_isolated_inputs(self):
        config = yaml.safe_load((ROOT/'pipeline/rwa_hierarchy/config.yaml').read_text())
        self.assertEqual(
            (ROOT/'src'/config['scripts']['rwa_hierarchy']['path']).resolve(),
            Path(workflow.__file__).resolve(),
        )
        config['parameters'].update(output_dir=str(self.directory/'managed'),
                                    yield_window=64,parameter_window=32,recent_rows=0,
                                    paths=8,steps=3)
        config['scripts']['rwa_hierarchy']['args'] += ['--input',str(self.input),'--maturities','1','2']
        config['scripts']['rwa_hierarchy']['inputs'] = [str(self.input/'DGS*.csv')]
        config['log_root'] = str(self.directory/'logs')
        path = self.directory/'workflow.yaml'
        path.write_text(yaml.safe_dump(config))
        result = subprocess.run([sys.executable,'-B',str(ROOT/'pipeline/Task_manager_Global_yaml_driven.py'),
                                 '--config',str(path)],cwd=ROOT,capture_output=True,text=True,
                                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((self.directory/'managed/manifest.json').is_file())

    def test_paths_cannot_escape_repository_including_symlinks(self):
        for path in ['../forbidden',ROOT.parent/'elsewhere']:
            with self.assertRaises(ValueError):
                workflow.repository_path(path)
        (self.directory/'escape').symlink_to('/private/tmp',target_is_directory=True)
        with self.assertRaises(ValueError):
            workflow.repository_path(self.directory/'escape'/'result')


if __name__=='__main__':
    unittest.main()
