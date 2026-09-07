"""Regression tests for pipeline configuration and barrier ordering."""

import sys
import unittest
import importlib.util
import ast
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import tempfile
import copy
from unittest import mock

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
            if phase.kind == "sequential" and "8.2" in phase.payload
        )
        filter_position = next(
            index
            for index, phase in enumerate(phases)
            if phase.kind == "intermediate_steps" and "8.3.0.1" in phase.payload
        )

        self.assertLess(pmf_position, jsd_position)
        self.assertLess(jsd_position, filter_position)

    def test_selected_parameters_control_arguments_and_all_artifacts(self):
        raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
        raw["parameters"]["horizons"] = [1, 3]
        raw["parameters"]["bins1"] = [20, 50]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selected.yaml"
            path.write_text(yaml.safe_dump(raw))
            config = manager.load_config(path)
        for step in ["7.0", "7.1", "8.0", "8.1.1", "8.2", "8.3.0.1"]:
            spec = config.scripts[step]
            index = spec.args.index("--horizons")
            self.assertEqual(("1", "3"), spec.args[index + 1:index + 3])
            for artifact in spec.inputs + spec.outputs + spec.create_dirs:
                self.assertNotIn("{", str(artifact))
                self.assertNotIn("T+2", str(artifact))
                self.assertNotIn("T+4", str(artifact))
                self.assertNotIn("Basel3_t2", str(artifact))
                self.assertNotIn("Basel3_t4", str(artifact))
        self.assertEqual(12, len(config.scripts["8.0"].outputs))
        self.assertEqual(12, len(config.scripts["8.2"].outputs))
        self.assertTrue(all(str(p).endswith(("_20.csv", "_50.csv"))
                            for p in config.scripts["8.0"].outputs))

    def test_default_configuration_runs_all_original_horizons_and_bin_specifications(self):
        for step in ["7.0", "7.1", "8.0", "8.1.1", "8.2", "8.3.0.1"]:
            args = self.config.scripts[step].args
            index = args.index("--horizons")
            self.assertEqual(("1", "2", "3", "4"), args[index + 1:index + 5])
            if step.startswith("8."):
                index = args.index("--bins1" if step == "8.0" else "--bins")
                self.assertEqual(("20", "30", "50", "100"), args[index + 1:index + 5])
                self.assertEqual(48, len(self.config.scripts[step].outputs))

    def test_configuration_without_parameters_preserves_literal_braces(self):
        raw = {
            "scripts": {"one": {"path": "one.py", "args": ["--label", "{CERT}"],
                                 "outputs": ["Material Events/{archive}/result.csv"]}},
            "dependencies": {}, "execution": [{"sequential": ["one"]}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "literal.yaml"
            path.write_text(yaml.safe_dump(raw))
            config = manager.load_config(path)
        self.assertEqual(("--label", "{CERT}"), config.scripts["one"].args)
        self.assertEqual((PROJECT_ROOT / "Material Events/{archive}/result.csv",),
                         config.scripts["one"].outputs)

    def test_prep_receives_the_active_alternate_configuration_path(self):
        raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
        raw["parameters"]["horizons"] = [1, 3]
        with tempfile.TemporaryDirectory() as directory:
            # Braces in the real path must not be interpreted as parameters.
            path = Path(directory) / "alternate {horizons}.yaml"
            path.write_text(yaml.safe_dump(raw))
            config = manager.load_config(path)
            prep = config.scripts["0.0"]
            self.assertEqual(config.path, path.resolve())
            self.assertEqual(
                ("--config", str(path.resolve()), "--txt-dir", "data/TXT",
                 "--cache-dir", "data/FFIEC", "--manifest", "data/FFIEC/prepared.json"),
                prep.args,
            )
            self.assertNotIn(str(manager.DEFAULT_CONFIG), prep.args)

    def test_config_path_token_works_without_user_parameters(self):
        raw = {
            "scripts": {"one": {"path": "one.py",
                                 "args": ["--config", "{config_path}", "--label", "{CERT}"]}},
            "dependencies": {}, "execution": [{"sequential": ["one"]}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config {CERT}.yaml"
            path.write_text(yaml.safe_dump(raw))
            config = manager.load_config(path)
            self.assertEqual(("--config", str(path.resolve()), "--label", "{CERT}"),
                             config.scripts["one"].args)

    def test_user_parameters_cannot_override_config_path(self):
        raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
        raw["parameters"]["config_path"] = "some_other_configuration.yaml"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "collision.yaml"
            path.write_text(yaml.safe_dump(raw))
            with self.assertRaisesRegex(manager.ConfigError, "config_path.*reserved"):
                manager.load_config(path)

    def test_prep_runs_before_conversion_and_declares_completed_artifacts(self):
        self.assertEqual("sequential", self.config.execution[0].kind)
        self.assertEqual(("0.0", "1.0", "2.0", "2.1"), self.config.execution[0].payload)
        self.assertEqual((), self.config.prerequisites["0.0"])
        self.assertEqual(("0.0",), self.config.prerequisites["1.0"])
        prep = self.config.scripts["0.0"]
        self.assertEqual(PROJECT_ROOT / "src/call reports/prepare_call_reports.py", prep.path)
        self.assertEqual((PROJECT_ROOT / "data/FFIEC/prepared.json", PROJECT_ROOT / "data/TXT/*/*.txt"),
                         prep.outputs)
        self.assertEqual((PROJECT_ROOT / "data/FFIEC",), prep.create_dirs)
        self.assertNotIn("--start-date", prep.args)
        self.assertNotIn("--end-date", prep.args)

    def test_failed_preparation_stops_the_real_pipeline_before_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            txt_dir = root / "data/TXT"
            cache_dir = root / "data/FFIEC"
            manifest = cache_dir / "prepared.json"
            marker = root / "consumer-ran"
            consumer = root / "consumer.py"
            consumer.write_text("from pathlib import Path\nPath('consumer-ran').write_text('ran')\n")
            stub_dir = root / "offline"
            stub_dir.mkdir()
            (stub_dir / "sitecustomize.py").write_text(
                "from pathlib import Path\n"
                "import requests\n"
                "def deny_network(*args, **kwargs):\n"
                "    Path(__file__).with_name('network-attempted').write_text('attempted')\n"
                "    raise AssertionError('This fixture must not make HTTP requests')\n"
                "requests.sessions.Session.request = deny_network\n"
            )
            raw = {
                "scripts": {
                    "0.0": {
                        "path": str(PROJECT_ROOT / "src/call reports/prepare_call_reports.py"),
                        "args": ["--config", "{config_path}", "--txt-dir", str(txt_dir),
                                 "--cache-dir", str(cache_dir), "--manifest", str(manifest)],
                        "outputs": [str(manifest), str(txt_dir / "*/*.txt")],
                        "create_dirs": [str(cache_dir)], "cwd": str(root),
                    },
                    "1.0": {"path": str(consumer), "outputs": [str(marker)], "cwd": str(root)},
                    "6.0.1": {
                        "path": str(PROJECT_ROOT / "src/material events/FDIC API/Material_events_download.py"),
                        "args": ["--events", "failures", "--start-date", "not-a-date",
                                 "--end-date", "2024-03-31", "--material-dir", str(root / "Material Events")],
                        "cwd": str(root),
                    },
                },
                "dependencies": {"0.0": ["1.0"], "1.0": ["6.0.1"]},
                "execution": [{"sequential": ["0.0", "1.0", "6.0.1"]}],
                "log_root": str(root / "logs"),
            }
            config_path = root / "alternate {fixture}.yaml"
            config_path.write_text(yaml.safe_dump(raw))
            config = manager.load_config(config_path)
            runner = manager.PipelineRunner(config, run_id="invalid_prep_dates")
            runner.preflight()
            runner.initialize_logs()
            with mock.patch.dict(os.environ, {"PYTHONPATH": str(stub_dir)}):
                with redirect_stdout(StringIO()):
                    with self.assertRaisesRegex(manager.StepFailure, "step 0.0 exited with status 1"):
                        runner.run()
            self.assertEqual(set(), runner.completed)
            self.assertFalse(marker.exists())
            self.assertFalse(txt_dir.exists())
            self.assertFalse(manifest.exists())
            self.assertFalse((stub_dir / "network-attempted").exists())
            prep_log = (runner.log_dir / "0.0.log").read_text()
            self.assertIn(str(config_path), prep_log)
            self.assertIn("Invalid material-event dates in step 6.0.1", prep_log)
            self.assertFalse((runner.log_dir / "1.0.log").exists())
            self.assertFalse((runner.log_dir / "6.0.1.log").exists())

    def test_parameter_errors_are_reported_before_execution(self):
        raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
        for parameters in ({"horizons": []}, {"horizons": {"invalid": 1}}, {}):
            with self.subTest(parameters=parameters), tempfile.TemporaryDirectory() as directory:
                raw["parameters"] = parameters
                path = Path(directory) / "invalid.yaml"
                path.write_text(yaml.safe_dump(raw))
                with self.assertRaises(manager.ConfigError):
                    manager.load_config(path)

    def test_repeated_parameter_in_one_path_uses_the_same_selection(self):
        self.assertEqual(
            ["T+1/report_t1_20.csv", "T+1/report_t1_50.csv",
             "T+3/report_t3_20.csv", "T+3/report_t3_50.csv"],
            manager._expand_parameter("T+{h}/report_t{h}_{b}.csv",
                                      {"h": ("1", "3"), "b": ("20", "50")}, "test"),
        )

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

    def test_material_event_arguments_match_scripts_and_artifacts(self):
        events_by_step = {
            "6.0.1": ["de_novo"],
            "6.0.2": ["failures"],
            "6.0.3": ["mergers"],
            "6.1": ["de_novo", "failures", "mergers"],
            "6.1.1": ["de_novo", "failures", "mergers"],
            "6.2": ["de_novo"],
            "6.3": ["failures"],
            "6.4": ["mergers"],
        }
        for step, events in events_by_step.items():
            with self.subTest(step=step):
                spec = self.config.scripts[step]
                self.assertIn("--events", spec.args)
                module_spec = importlib.util.spec_from_file_location(
                    "material_step_" + step.replace(".", "_"), spec.path
                )
                module = importlib.util.module_from_spec(module_spec)
                original_import_path = sys.path[:]
                sys.path.insert(0, str(spec.path.parent))
                try:
                    module_spec.loader.exec_module(module)
                    args = module.parse_args(list(spec.args))
                    if step.startswith("6.0.") or step in {"6.2", "6.3", "6.4"}:
                        error_output = StringIO()
                        with redirect_stderr(error_output), self.assertRaises(SystemExit) as error:
                            module.parse_args([])
                        self.assertEqual(2, error.exception.code)
                        self.assertIn("--events", error_output.getvalue())
                finally:
                    sys.path[:] = original_import_path

                def from_working_directory(value):
                    value = Path(value)
                    return (value if value.is_absolute() else spec.cwd / value).resolve()

                self.assertEqual(events, args.events)
                self.assertEqual(
                    PROJECT_ROOT / "Material Events",
                    from_working_directory(args.material_dir),
                )
                if step.startswith("6.0."):
                    self.assertEqual("2014-01-01", args.start_date)
                    self.assertEqual("2024-12-31", args.end_date)
                    self.assertEqual(10000, args.limit)
                elif step in {"6.2", "6.3", "6.4"}:
                    self.assertEqual(
                        spec.inputs[0].parent,
                        from_working_directory(args.input_dir),
                    )
                    self.assertEqual(
                        spec.outputs[0].parent,
                        from_working_directory(args.output_dir),
                    )
                    self.assertEqual(
                        spec.inputs[-1],
                        from_working_directory(args.quarter_map),
                    )

    def test_material_steps_call_four_shared_implementations(self):
        expected = {
            "6.0.1": "material events/FDIC API/Material_events_download.py",
            "6.0.2": "material events/FDIC API/Material_events_download.py",
            "6.0.3": "material events/FDIC API/Material_events_download.py",
            "6.1": "material events/FDIC API/Material_events_cleaned.py",
            "6.1.1": "material events/FDIC API/Material_events_delete_api.py",
            "6.2": "material events/Material_events_flag.py",
            "6.3": "material events/Material_events_flag.py",
            "6.4": "material events/Material_events_flag.py",
        }
        actual = {
            step: spec.path.relative_to(PROJECT_ROOT / "src").as_posix()
            for step, spec in self.config.scripts.items()
            if step.startswith("6.")
        }
        self.assertEqual(expected, actual)
        self.assertEqual(4, len(set(actual.values())))

    def test_material_event_barriers_preserve_stage_order(self):
        downloads = {"6.0.1", "6.0.2", "6.0.3"}
        phases = self.config.execution
        download_position = next(
            index
            for index, phase in enumerate(phases)
            if phase.kind == "concurrent_groups"
            and any(set(steps) == downloads for _, steps in phase.payload)
        )
        flag_phase = phases[download_position + 1]
        self.assertEqual("sequential", flag_phase.kind)
        self.assertEqual(("6.1", "6.1.1", "6.2", "6.3", "6.4"), flag_phase.payload)
        self.assertEqual(downloads, set(self.config.prerequisites["6.1"]))
        for before, after in zip(flag_phase.payload, flag_phase.payload[1:]):
            self.assertEqual((before,), self.config.prerequisites[after])


if __name__ == "__main__":
    unittest.main()
