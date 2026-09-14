"""Deterministic artifact replay, integrity chains and malformed-input guards."""

import csv
from copy import deepcopy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
workflow = importlib.import_module('src.RWA.models.parameter_hierarchy.workflow')
recursive = importlib.import_module('src.RWA.models.parameter_hierarchy.recursive')
verify = importlib.import_module('src.RWA.models.parameter_hierarchy.verify')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def load(path):
    return json.loads(path.read_text())


class FixedShockGenerator:
    """A deterministic test double; it generates no random observations."""
    def __init__(self, seed):
        self.bit_generator = np.random.PCG64(seed)

    def standard_normal(self, shape):
        state = self.bit_generator.state
        state['state']['state'] = (state['state']['state'] + 1) % 2**128
        self.bit_generator.state = state
        return np.linspace(-.05, .05, np.prod(shape)).reshape(shape)


def fixture_run(output):
    t = np.arange(40.)[:, None]
    j = np.arange(1., 3.)[None, :]
    history = np.stack([3 + .2*np.sin(t*j*.17) + .05*j,
                        .4 + .015*np.cos(t*j*.23) + .004*j,
                        .1 + .007*np.sin(t*j*.31 + .2) + .001*j], axis=1)
    output.mkdir()
    dates = (np.datetime64('2000-01-01') + np.arange(len(history))).astype(str)
    np.savez_compressed(output/'initial_history.npz', history=history,
                        history_dt=np.full(len(history)-1, .25), maturities=[1, 2],
                        state_names=np.array(['rate', 'sigma', 'xi']), dates=dates)
    for name in ('yield_parameters.csv', 'parameter_dynamics.csv', 'transition_intervals.csv'):
        (output/name).write_text('fixture\n1\n')
    (output/'RAW').mkdir()
    (output/'CURVE').mkdir()
    for maturity in (1, 2):
        (output/'RAW'/('DGS%d_with_parameters.csv' % maturity)).write_text('fixture\n1\n')
    for parameter in ('mu', 'theta', 'sigma'):
        (output/'CURVE'/(parameter + '_curve.csv')).write_text('fixture\n1\n')
    with mock.patch.object(recursive.np.random, 'default_rng', side_effect=FixedShockGenerator):
        years = workflow.run_years(output, history, [1, 2], years=2, steps_per_year=4,
                                   dt=.25, substeps=2, seed=123, regularization=.02)
    files = {path.relative_to(output).as_posix(): digest(path) for path in output.rglob('*')
             if path.is_file() and not path.relative_to(output).parts[0].startswith('year_')}
    manifest = {'schema_version': 2, 'status': 'complete', 'files_sha256': files,
                'settings': {'years': 2, 'steps_per_year': 4, 'substeps': 2, 'dt': .25,
                             'nll_budget': 2., 'fallback_theta': .25, 'correlation_regularization': .02,
                             'history_window': len(history), 'maturities': [1, 2], 'time_basis': 'observation'},
                'walk_history_rows': len(history), 'walk_history_start': dates[0],
                'forecast_origin': dates[-1], 'state_names': ['rate', 'sigma', 'xi'], 'years': years}
    dump(output/'manifest.json', manifest)
    return manifest


class WalkVerificationTests(unittest.TestCase):
    def test_likelihood_cost_roundoff_uses_the_subtracted_likelihood_scale(self):
        expected = {'raw_nll': -15000., 'nll_cost': 0.}
        rounded = {'raw_nll': -15000., 'nll_cost': 4*np.spacing(15000.)}
        verify._audit_equal(rounded, expected, 'calibration')
        with self.assertRaisesRegex(ValueError, 'nll_cost'):
            verify._audit_equal({'raw_nll': -15000., 'nll_cost': .0001}, expected, 'calibration')
        # Matrix and state comparisons retain their original tighter scaling.
        with self.assertRaises(ValueError):
            verify._same(np.array([1e-10]), np.array([0.]), 'covariance')

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        cls.base = Path(cls.temporary.name)
        cls.source = cls.base/'source'
        fixture_run(cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        import shutil
        self.temporary_run = tempfile.TemporaryDirectory(dir=self.base)
        self.addCleanup(self.temporary_run.cleanup)
        self.output = Path(self.temporary_run.name)/'run'
        shutil.copytree(self.source, self.output)

    def refresh_hashes(self):
        root = load(self.output/'manifest.json')
        for entry in root['years']:
            year = self.output/entry['directory']
            cov_dir = year/'covariance'
            cov = load(cov_dir/'manifest.json')
            records = [json.loads(line) for line in (cov_dir/'index.jsonl').read_text().splitlines()]
            for record in records:
                record['sha256'] = digest(cov_dir/record['file'])
            (cov_dir/'index.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in records))
            cov['inventory']['sha256'] = digest(cov_dir/'index.jsonl')
            dump(cov_dir/'manifest.json', cov)
            report = load(year/'manifest.json')
            report['files_sha256'] = {name: digest(year/name) for name in report['files_sha256']}
            dump(year/'manifest.json', report)
            entry['manifest_sha256'] = digest(year/'manifest.json')
        root['files_sha256'] = {name: digest(self.output/name) for name in root['files_sha256']}
        dump(self.output/'manifest.json', root)

    def modify_npz(self, relative, mutate):
        path = self.output/relative
        with np.load(path, allow_pickle=False) as artifact:
            arrays = {name: artifact[name].copy() for name in artifact.files}
        mutate(arrays)
        np.savez_compressed(path, **arrays)
        self.refresh_hashes()

    def test_every_increment_replays_and_recalibrates_without_new_draws_or_writes(self):
        before = {path.relative_to(self.output): digest(path) for path in self.output.rglob('*') if path.is_file()}
        with mock.patch.object(np.random, 'default_rng', side_effect=AssertionError('new random draw')):
            report = verify.verify_walk(self.output, recalibrate=True)
        self.assertEqual(report['status'], 'verified')
        self.assertEqual(report['years'], 2)
        self.assertEqual(report['increments'], 16)
        self.assertEqual(report['recalibrated_increments'], 16)
        self.assertEqual(report['new_random_draws'], 0)
        after = {path.relative_to(self.output): digest(path) for path in self.output.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_portable_cli_verifies_from_an_unrelated_working_directory(self):
        command = [sys.executable, '-B', str(ROOT/'src/RWA/models/parameter_hierarchy/verify.py'),
                   '--input', str(self.output), '--recalibrate']
        result = subprocess.run(command, cwd=self.base, capture_output=True, text=True,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['increments'], 16)

    def test_corrupt_bytes_fail_the_hash_chain_before_numerical_replay(self):
        with (self.output/'year_0002/covariance/step_000003.npz').open('ab') as stream:
            stream.write(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            verify.verify_walk(self.output)

    def test_omitting_a_required_historical_export_hash_is_rejected(self):
        manifest = load(self.output/'manifest.json')
        del manifest['files_sha256']['RAW/DGS1_with_parameters.csv']
        dump(self.output/'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'missing required artifact hashes.*RAW/DGS1'):
            verify.verify_walk(self.output)

    def test_rehashed_covariance_tampering_fails_independent_rolling_reconstruction(self):
        self.modify_npz('year_0002/covariance/step_000003.npz',
                        lambda arrays: arrays['factor_covariance'].__imul__(1.01))
        with self.assertRaisesRegex(ValueError, 'rolling level covariance'):
            verify.verify_walk(self.output)

    def test_rehashed_actual_diffusion_tampering_is_not_hidden_by_update_order(self):
        def mutate(arrays):
            arrays['coefficients'][0, 2] *= 1.1
        self.modify_npz('year_0001/covariance/step_000002.npz', mutate)
        with self.assertRaisesRegex(ValueError, 'actual rate diffusion'):
            verify.verify_walk(self.output)

    def test_rehashed_shock_tampering_fails_recorded_factor_transformation(self):
        def mutate(arrays):
            arrays['normal_shocks'][0, 0] += .01
        self.modify_npz('year_0001/covariance/step_000004.npz', mutate)
        with self.assertRaisesRegex(ValueError, 'shock transformation'):
            verify.verify_walk(self.output)

    def test_rehashed_restart_history_and_year_anchor_tampering_fail_continuity(self):
        def mutate(arrays):
            arrays['history'][0, 0, 0] += .01
        self.modify_npz('year_0001/restart.npz', mutate)
        with self.assertRaisesRegex(ValueError, 'restart history'):
            verify.verify_walk(self.output)

    def test_rehashed_initial_clock_must_match_its_declared_time_basis(self):
        def mutate(arrays):
            arrays['history_dt'][0] *= 2.
        self.modify_npz('initial_history.npz', mutate)
        with self.assertRaisesRegex(ValueError, 'time convention'):
            verify.verify_walk(self.output)

    def test_rehashed_initial_metadata_must_match_configuration_and_endpoints(self):
        manifest = load(self.output/'manifest.json')
        manifest['settings']['maturities'] = [1, 3]
        dump(self.output/'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'configured maturities'):
            verify.verify_walk(self.output)

    def test_relative_traversal_and_symlink_escape_are_rejected(self):
        manifest = load(self.output/'manifest.json')
        manifest['files_sha256']['../outside.txt'] = '0' * 64
        dump(self.output/'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'inside its archive'):
            verify.verify_walk(self.output)
        del manifest['files_sha256']['../outside.txt']
        (self.output/'yield_parameters.csv').unlink()
        outside = Path(self.temporary_run.name)/'outside.csv'
        outside.write_text('outside\n')
        (self.output/'yield_parameters.csv').symlink_to(outside)
        manifest['files_sha256']['yield_parameters.csv'] = digest(outside)
        dump(self.output/'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'symlink escapes'):
            verify.verify_walk(self.output)

    def test_missing_complete_status_duplicate_json_and_missing_year_are_rejected(self):
        manifest = load(self.output/'manifest.json')
        manifest['status'] = 'incomplete'
        dump(self.output/'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'not complete'):
            verify.verify_walk(self.output)
        manifest['status'] = 'complete'
        manifest['years'].pop()
        dump(self.output/'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'year inventory'):
            verify.verify_walk(self.output)
        (self.output/'manifest.json').write_text('{"status":"complete","status":"complete"}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            verify.verify_walk(self.output)

    def test_declared_oversized_npy_shape_is_rejected_before_numpy_allocation(self):
        path = Path(self.temporary_run.name)/'oversized.npz'
        header = io.BytesIO()
        np.lib.format.write_array_header_1_0(header, {'descr': '<f8', 'fortran_order': False, 'shape': (10**12,)})
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('history.npy', header.getvalue())
        with mock.patch.object(np, 'load', side_effect=AssertionError('allocation before header guard')):
            with self.assertRaisesRegex(ValueError, 'declared NPZ array allocation'):
                verify._npz(path, ('history',))

    def test_object_arrays_are_rejected_before_numpy_load(self):
        path = Path(self.temporary_run.name)/'objects.npz'
        np.savez(path, history=np.array([{'never': 'unpickle'}], dtype=object))
        with mock.patch.object(np, 'load', side_effect=AssertionError('object loader reached')):
            with self.assertRaisesRegex(ValueError, 'object/pickle'):
                verify._npz(path, ('history',))

    def test_zero_itemsize_string_shape_cannot_bypass_allocation_guard(self):
        path = Path(self.temporary_run.name)/'zero-size.npz'
        for descriptor in ('<U0', '|S0'):
            header = io.BytesIO()
            np.lib.format.write_array_header_1_0(header, {'descr': descriptor, 'fortran_order': False,
                                                        'shape': (10**12,)})
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('history.npy', header.getvalue())
            with mock.patch.object(np, 'load', side_effect=AssertionError('allocation before dtype guard')):
                with self.subTest(dtype=descriptor), self.assertRaisesRegex(ValueError, 'zero-itemsize'):
                    verify._npz(path, ('history',))


if __name__ == '__main__':
    unittest.main()
