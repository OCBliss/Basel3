"""Regression tests for pipeline configuration and barrier ordering."""

import sys
import unittest
import importlib.util
import ast
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

import Task_manager_Global_yaml_driven as manager  # noqa: E402

path_spec = importlib.util.spec_from_file_location(
    "basel3_project_paths", PROJECT_ROOT / "src" / "Basel3_Global_Filepath.py"
)
project_paths = importlib.util.module_from_spec(path_spec)
path_spec.loader.exec_module(project_paths)


class PipelineConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = manager.load_config()

    def test_duplicate_yaml_keys_are_rejected(self):
        duplicate = "execution:\n  intermediate_steps: [one]\n  intermediate_steps: [two]\n"

        with self.assertRaisesRegex(yaml.YAMLError, "duplicate key"):
            yaml.load(duplicate, Loader=manager.UniqueKeyLoader)

    def test_every_configured_script_exists(self):
        for step, spec in self.config.scripts.items():
            with self.subTest(step=step):
                self.assertTrue(spec.path.is_file(), spec.path)

    def test_intermediate_barriers_surround_jsd_horizons(self):
        phases = self.config.execution
        pmf_position = next(
            index
            for index, phase in enumerate(phases)
            if phase.kind == "intermediate_steps" and "8.1.1" in phase.payload
        )
        jsd_position = next(
            index
            for index, phase in enumerate(phases)
            if phase.kind == "concurrent_branches"
        )
        filter_position = next(
            index
            for index, phase in enumerate(phases)
            if phase.kind == "intermediate_steps" and "8.3.0.1" in phase.payload
        )

        self.assertLess(pmf_position, jsd_position)
        self.assertLess(jsd_position, filter_position)

    def test_stage_steps_are_unique_and_complete(self):
        scheduled = manager._execution_steps(self.config.execution)

        self.assertEqual(len(scheduled), len(set(scheduled)))
        self.assertEqual(set(scheduled), set(self.config.scripts))

    def test_shared_pipeline_paths_are_defined(self):
        required = {
            "BASEL3_ROOT",
            "CALL_DIR",
            "CODE_DIR",
            "CSV_DIR",
            "DISTRIBUTED_DIR",
            "DYNAMIC_DIR",
            "MAT_DIR",
        }

        self.assertEqual(
            set(),
            {name for name in required if not hasattr(project_paths, name)},
        )

    def test_scripts_only_reference_defined_shared_paths(self):
        referenced = set()
        for script in (PROJECT_ROOT / "src").rglob("*.py"):
            tree = ast.parse(script.read_text(encoding="utf-8"))
            referenced.update(
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "paths"
            )

        missing = {name for name in referenced if not hasattr(project_paths, name)}
        self.assertEqual(set(), missing)

    def test_steps_declare_artifact_contracts(self):
        intentional_in_place_or_cleanup = {"2.1", "6.1.1"}
        missing_outputs = {
            step
            for step, spec in self.config.scripts.items()
            if not spec.outputs and step not in intentional_in_place_or_cleanup
        }

        self.assertEqual(set(), missing_outputs)


if __name__ == "__main__":
    unittest.main()
