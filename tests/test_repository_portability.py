"""Checkout-independent path discovery without executing historical pipelines."""

import ast
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPERS = (
    Path('Basel3_Global_Filepath.py'),
    Path('pipeline/Basel3_Global_Filepath.py'),
    Path('src/Basel3_Global_Filepath.py'),
)
LEGACY_RESOLVERS = (
    ('RWA/Experimental/RWA_Heston_MLE4.py', 'find_code_dir'),
    ('RWA/Experimental/RWA_Heston_MLE_vol_test.py', 'find_code_dir'),
    ('RWA/Practical/Constant Maturity Treasury/Cleaned/Constant_Treasury_Maturity_Cleaned2a.py', 'find_global_filepath'),
    ('RWA/Practical/Constant Maturity Treasury/Differenced/Constant_Maturity_Treasury_Differenced5a.py', 'find_global_filepath'),
    ('RWA/Practical/Constant Maturity Treasury/EXP_COUPON/autoregressive_fitting_v3a.py', 'find_code_dir'),
    ('RWA/Practical/Constant Maturity Treasury/EXP_DRIFT/Constant_Maturity_Treasury_exp_drift_v3.py', 'find_global_filepath'),
)


def resolver(relative_path, function_name, checkout):
    """Load only path discovery; old experiment modules can execute on import."""
    parsed = ast.parse((ROOT/relative_path).read_text())
    function = next(node for node in parsed.body
                    if isinstance(node, ast.FunctionDef) and node.name == function_name)
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {'os': os, '__file__': str(checkout/relative_path)}
    exec(compile(module, str(relative_path), 'exec'), namespace)
    return namespace[function_name]


class RepositoryPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_global_helpers_resolve_the_checkout_without_a_fixed_name_or_terminal(self):
        for name in ('Basel3', 'renamed checkout'):
            checkout = self.directory/name
            for relative in HELPERS:
                namespace = {'__name__': 'path_fixture', '__file__': str(checkout/relative)}
                with self.subTest(checkout=name, helper=str(relative)), mock.patch('sys.stdout', StringIO()):
                    exec(compile((ROOT/relative).read_text(), str(relative), 'exec'), namespace)
                self.assertEqual(Path(namespace['BASEL3_ROOT']), checkout)
                self.assertEqual(Path(namespace['CODE_DIR']), checkout/'src')
                self.assertEqual(Path(namespace['CALL_DIR']), checkout/'data')
                self.assertEqual(Path(namespace['PIPE_DIR']), checkout/'pipeline')

    def test_unsupported_python_fails_once_without_relaunching_any_interpreter(self):
        for relative in HELPERS:
            namespace = {'__name__': 'path_fixture', '__file__': str(self.directory/relative)}
            with self.subTest(helper=str(relative)), mock.patch.object(sys, 'version_info', (3, 7, 0)), \
                    mock.patch.object(subprocess, 'run') as launch, self.assertRaisesRegex(SystemExit, '3.8'):
                exec(compile((ROOT/relative).read_text(), str(relative), 'exec'), namespace)
            launch.assert_not_called()

    def test_every_legacy_resolver_stays_in_its_own_renamed_checkout(self):
        checkout = self.directory/'Basel3 with spaces'
        helper = checkout/'src/Basel3_Global_Filepath.py'
        helper.parent.mkdir(parents=True)
        helper.write_text('# isolated path fixture\n')
        # An unrelated sibling helper must never influence discovery.
        unrelated = self.directory/'unrelated/src/Basel3_Global_Filepath.py'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('# another checkout\n')
        for relative, function in LEGACY_RESOLVERS:
            with self.subTest(script=relative), \
                    mock.patch.object(os, 'walk', side_effect=AssertionError('filesystem traversal')):
                located = Path(resolver(relative, function, checkout)())
            self.assertEqual(located, helper.parent if function == 'find_code_dir' else helper)

    def test_missing_local_helper_never_falls_back_to_another_ancestor_checkout(self):
        checkout = self.directory/'incomplete clone'
        # The real source helper exists above this fixture. Discovery must stop
        # at the fixture's RWA boundary instead of using that unrelated helper.
        for relative, function in LEGACY_RESOLVERS:
            with self.subTest(script=relative), \
                    mock.patch.object(os, 'walk', side_effect=AssertionError('filesystem traversal')), \
                    self.assertRaisesRegex(FileNotFoundError, 'src/Basel3_Global_Filepath.py'):
                resolver(relative, function, checkout)()


if __name__ == '__main__':
    unittest.main()
