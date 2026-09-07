"""Run every configured material-event stage with explicit, offline FDIC records.

The real runner launches real scripts in subprocesses. Only HTTP responses are
replaced; all inputs, outputs, logs, and deletion targets live in a temporary root.
"""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
import Task_manager_Global_yaml_driven as manager


STAGES = (
    "6.0.1", "6.0.2", "6.0.3", "6.1", "6.1.1", "6.2", "6.3", "6.4"
)
ENTRYPOINTS = {
    "6.0.1": "FDIC API/Material_events_download.py",
    "6.0.2": "FDIC API/Material_events_download.py",
    "6.0.3": "FDIC API/Material_events_download.py",
    "6.1": "FDIC API/Material_events_cleaned.py",
    "6.1.1": "FDIC API/Material_events_delete_api.py",
    "6.2": "Material_events_flag.py",
    "6.3": "Material_events_flag.py",
    "6.4": "Material_events_flag.py",
}
EVENT_FILES = {
    "de_novo": ("DE NOVO", "BankFind Suite API - de novo.csv"),
    "failures": ("Failures", "BankFind Suite API - Failures.csv"),
    "mergers": ("Mergers", "BankFind Suite API - mergers.csv"),
}
PATH_OPTIONS = {"--material-dir", "--input-dir", "--output-dir", "--quarter-map"}


def event_rows(event):
    """Dates are chosen explicitly around the fixture's quarter boundaries."""
    if event == "de_novo":
        dates = [(101, "2020-01-01"), (102, "2020-03-31"),
                 (103, "2020-04-01"), (108, "2019-12-31")]
    elif event == "failures":
        dates = [(101, "2020-03-31"), (102, "2020-06-30"),
                 (103, "2020-07-01"), (104, "2020-10-01"),
                 (105, "2021-03-31"), (106, "2020-03-30"),
                 (107, "2021-04-01"), (102, "2019-01-01")]
    else:
        dates = [(101, "2020-04-01"), (102, "2020-07-01"),
                 (103, "2020-09-30"), (104, "2020-12-31"),
                 (105, "2021-01-01"), (106, "2021-04-01"),
                 (107, "2020-03-31"), (101, "2021-04-01")]
    rows = []
    for index, (cert, date) in enumerate(dates):
        record = {
            "ID": "nested-{}".format(index),
            "ESTDATE": date + "T00:00:00" if event == "de_novo" else "2000-01-01T00:00:00",
            "EFFDATE": date + "T00:00:00",
        }
        if event == "de_novo":
            record["CERT"] = cert
        else:
            record["ACQ_CERT"] = cert
            # OUT_CERT is deliberately not in the downloader's requested fields.
            record["OUT_CERT"] = cert + 9000
        rows.append({"data": record, "ID": "metadata-{}".format(index)})
    return rows


def write_fixture(root):
    material = root / "Material Events"
    dynamic = root / "data/CSV/Dynamic_Lag/Cleaned"
    material.mkdir(parents=True)
    dynamic.mkdir(parents=True)
    panel = pd.DataFrame({
        "CERT": list(range(101, 109)) + [9101],
        "RCON9999": [20200331] * 9,
        "ratio_one": [-1.0, 0.0, 0.25, 2.0, 3.0, 0.5, -0.25, 1.0, 0.75],
        "ratio_two": list(range(9)),
    })
    panel.to_csv(dynamic / "Dynamic_Cleaned_20200331.csv", index=False)
    pd.DataFrame([{
        "Quarters": 20200331, "START_DATE": 20200101, "END_DATE": 20200331,
    }]).to_csv(material / "quarters_de_novo.csv", index=False)
    pd.DataFrame([{
        "Quarters": 20200331, "START_DATE": 20200331,
        "END_DATE1": 20200630, "END_DATE2": 20200930,
        "END_DATE3": 20201231, "END_DATE4": 20210331,
    }]).to_csv(material / "quarters_failures.csv", index=False)
    for folder, _ in EVENT_FILES.values():
        raw = material / folder / "RAW"
        raw.mkdir(parents=True)
        (raw / "keep.txt").write_text("Unrelated local file.", encoding="utf-8")
    return panel


def isolate_material_config(root):
    """Retain production stage definitions, arguments, and phase order."""
    raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
    raw["scripts"] = {stage: raw["scripts"][stage] for stage in STAGES}
    for stage, spec in raw["scripts"].items():
        spec["path"] = str(PROJECT_ROOT / "src" / spec["path"])
        spec["cwd"] = str(root)
        for key in ("inputs", "outputs", "create_dirs"):
            spec[key] = [str(root / path) for path in spec.get(key, [])]
        args = spec["args"]
        for index, argument in enumerate(args[:-1]):
            if argument in PATH_OPTIONS:
                args[index + 1] = str(root / args[index + 1])
        if stage.startswith("6.0."):
            # Nondefault values prove the YAML arguments reach the HTTP request.
            for option, value in (("--start-date", "2019-01-01"),
                                  ("--end-date", "2021-12-31"), ("--limit", 137)):
                args[args.index(option) + 1] = value
    raw["dependencies"] = {
        parent: [child for child in children if child in STAGES]
        for parent, children in raw["dependencies"].items()
        if parent in STAGES and any(child in STAGES for child in children)
    }
    phases = []
    for phase in raw["execution"]:
        kind, payload = next(iter(phase.items()))
        if kind in {"sequential", "intermediate_steps"}:
            selected = [step for step in payload if step in STAGES]
        elif kind == "concurrent_groups":
            selected = {name: [step for step in steps if step in STAGES]
                        for name, steps in payload.items()
                        if any(step in STAGES for step in steps)}
        else:
            continue  # The material section currently has no concurrent branches.
        if selected:
            phases.append({kind: selected})
    raw["execution"] = phases
    raw["log_root"] = str(root / "logs")
    target = root / "material_pipeline.yaml"
    target.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return manager.load_config(target)


def write_http_stub(root):
    """Patch only child HTTP responses and observe their actual deletion calls."""
    stub_dir = root / "http_stub"
    stub_dir.mkdir()
    (stub_dir / "responses.json").write_text(json.dumps({
        event: event_rows(event) for event in EVENT_FILES
    }), encoding="utf-8")
    (stub_dir / "sitecustomize.py").write_text(textwrap.dedent('''
        import json
        import os
        from pathlib import Path
        import requests

        root = Path(__file__).resolve().parent.parent
        responses = json.loads((root / "http_stub/responses.json").read_text())
        code_events = {
            "CHANGECODE:110": "de_novo",
            "CHANGECODE:211": "failures",
            "CHANGECODE:221 OR CHANGECODE:222 OR CHANGECODE:223 OR CHANGECODE:224": "mergers",
        }

        class Response:
            status_code = 200
            text = "offline fixture"

            def __init__(self, event):
                self.event = event

            def json(self):
                return {"data": responses[self.event]}

        def get(url, params=None, **kwargs):
            assert url == "https://banks.data.fdic.gov/api/history", url
            prefix = "EFFDATE:[2019-01-01 TO 2021-12-31] AND ("
            assert params["filters"].startswith(prefix), params
            codes = params["filters"][len(prefix):-1]
            event = code_events[codes]
            assert params["limit"] == 137, params
            assert params["sort_by"] == "EFFDATE", params
            assert params["sort_order"] == "DESC", params
            assert params["format"] == "json", params
            fields = params["fields"].split(",")
            assert "CERT" in fields if event == "de_novo" else "ACQ_CERT" in fields
            assert "OUT_CERT" not in fields, fields
            (root / ("request_" + event + ".json")).write_text(json.dumps(params))
            return Response(event)

        requests.get = get
        original_remove = os.remove

        def remove(path, *args, **kwargs):
            target = Path(path)
            if target.parent.name == "RAW" and "bankfind suite" in target.name.lower():
                cleaned = target.parent.parent / "Cleaned" / target.name
                assert cleaned.is_file(), "RAW deletion ran before cleaning: " + str(target)
                marker = root / ("deleted_" + target.parent.parent.name + ".json")
                marker.write_text(json.dumps({"raw": str(target), "cleaned": str(cleaned)}))
            return original_remove(path, *args, **kwargs)

        os.remove = remove
    '''), encoding="utf-8")
    return stub_dir


class MaterialEventsTests(unittest.TestCase):
    def test_four_executables_have_working_cli_help(self):
        with tempfile.TemporaryDirectory() as directory:
            for relative in dict.fromkeys(ENTRYPOINTS.values()):
                script = PROJECT_ROOT / "src/material events" / relative
                with self.subTest(script=relative):
                    result = subprocess.run(
                        [sys.executable, str(script), "--help"], cwd=directory,
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("--events", result.stdout)
                    self.assertIn("--material-dir", result.stdout)
                    if relative == ENTRYPOINTS["6.0.1"]:
                        for option in ("--start-date", "--end-date", "--limit"):
                            self.assertIn(option, result.stdout)
                    if relative == ENTRYPOINTS["6.2"]:
                        for option in ("--input-dir", "--output-dir", "--quarter-map"):
                            self.assertIn(option, result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_shared_commands_require_events_before_writing(self):
        for relative in (ENTRYPOINTS["6.0.1"], ENTRYPOINTS["6.2"]):
            with self.subTest(script=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "src/material events" / relative),
                     "--material-dir", str(root / "output")],
                    cwd=root, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("required", result.stderr)
                self.assertIn("--events", result.stderr)
                self.assertEqual(list(root.iterdir()), [])

    def test_downloader_runs_only_selected_single_or_multiple_events(self):
        for selected in (("failures",), ("mergers", "de_novo")):
            with self.subTest(events=selected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stub = write_http_stub(root)
                env = os.environ.copy()
                env["PYTHONPATH"] = str(stub) + os.pathsep + env.get("PYTHONPATH", "")
                result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "src/material events" / ENTRYPOINTS["6.0.1"]),
                     "--events", *selected, "--material-dir", str(root / "Material Events"),
                     "--start-date", "2019-01-01", "--end-date", "2021-12-31", "--limit", "137"],
                    cwd=root, env=env, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for event, (folder, filename) in EVENT_FILES.items():
                    event_dir = root / "Material Events" / folder
                    self.assertEqual(event_dir.exists(), event in selected)
                    self.assertEqual((root / ("request_" + event + ".json")).exists(),
                                     event in selected)
                    if event in selected:
                        downloaded = pd.read_csv(event_dir / "RAW" / filename)
                        cert_column = "CERT" if event == "de_novo" else "ACQ_CERT"
                        self.assertEqual(downloaded[cert_column].tolist(),
                                         [row["data"][cert_column] for row in event_rows(event)])

    def test_flagger_runs_selected_stages_in_upstream_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = write_fixture(root)
            material = root / "Material Events"
            upstream = material / "DE NOVO/Call Reports"
            upstream.mkdir()
            panel["DE_NOVO_FLAG"] = [1, 1, 0, 0, 0, 0, 0, 0, 0]
            upstream_file = upstream / "DE NOVO_20200331.csv"
            panel.to_csv(upstream_file, index=False)
            upstream_bytes = upstream_file.read_bytes()
            for event in ("failures", "mergers"):
                folder, filename = EVENT_FILES[event]
                cleaned = material / folder / "Cleaned"
                cleaned.mkdir()
                pd.DataFrame([{"CERT": row["data"]["ACQ_CERT"],
                               "EFFDATE": row["data"]["EFFDATE"]}
                              for row in event_rows(event)]).to_csv(cleaned / filename, index=False)
            # No de novo event table exists: the selected stages must use the
            # prepared upstream panel without silently running de novo again.
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "src/material events" / ENTRYPOINTS["6.2"]),
                 "--events", "mergers", "failures", "--material-dir", str(material)],
                cwd=root, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(upstream_file.read_bytes(), upstream_bytes)
            failures = pd.read_csv(material / "Failures/Call Reports/Failures_20200331.csv")
            mergers = pd.read_csv(material / "Mergers/Call Reports/Mergers_20200331.csv")
            failure_flags = ["FAILURE_T{}".format(i) for i in range(1, 5)]
            merger_flags = ["MERGER_T{}".format(i) for i in range(1, 5)]
            self.assertEqual(failures[failure_flags].values.tolist(), [
                [1, 1, 1, 1], [1, 1, 1, 1], [0, 1, 1, 1],
                [0, 0, 1, 1], [0, 0, 0, 1], [0, 0, 0, 0],
                [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0],
            ])
            self.assertEqual(mergers[merger_flags].values.tolist(), [
                [1, 1, 1, 1], [0, 1, 1, 1], [0, 1, 1, 1],
                [0, 0, 1, 1], [0, 0, 0, 1], [0, 0, 0, 0],
                [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0],
            ])
            pd.testing.assert_frame_equal(failures[list(panel.columns)], panel)
            pd.testing.assert_frame_equal(mergers[list(failures.columns)], failures)

    def test_actual_yaml_runs_all_material_stages_and_preserves_expected_flags(self):
        production = manager.load_config()
        for stage, relative in ENTRYPOINTS.items():
            self.assertEqual(production.scripts[stage].path,
                             PROJECT_ROOT / "src/material events" / relative)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = write_fixture(root)
            config = isolate_material_config(root)
            stub = write_http_stub(root)
            python_path = str(stub)
            if os.environ.get("PYTHONPATH"):
                python_path += os.pathsep + os.environ["PYTHONPATH"]
            runner = manager.PipelineRunner(config, run_id="offline_material_events")
            runner.preflight()
            runner.initialize_logs()
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"PYTHONPATH": python_path}):
                with contextlib.redirect_stdout(output):
                    try:
                        runner.run()
                    except Exception:
                        self.fail(output.getvalue())
            self.assertEqual(runner.completed, set(STAGES))

            for event, (folder, filename) in EVENT_FILES.items():
                event_dir = root / "Material Events" / folder
                self.assertTrue((root / ("request_" + event + ".json")).is_file())
                self.assertTrue((root / ("deleted_" + folder + ".json")).is_file())
                self.assertEqual([path.name for path in (event_dir / "RAW").iterdir()],
                                 ["keep.txt"])
                cleaned = pd.read_csv(event_dir / "Cleaned" / filename)
                expected_cert = [record["data"]["CERT" if event == "de_novo" else "ACQ_CERT"]
                                 for record in event_rows(event)]
                self.assertEqual(cleaned["CERT"].tolist(), expected_cert)
                self.assertTrue(cleaned["ACQ_CERT"].isna().all())
                self.assertEqual(cleaned["ID"].tolist(),
                                 ["metadata-{}".format(i) for i in range(len(expected_cert))])
                self.assertEqual(cleaned.shape[1], 29)

            flags = ["DE_NOVO_FLAG"] + ["FAILURE_T{}".format(i) for i in range(1, 5)]
            flags += ["MERGER_T{}".format(i) for i in range(1, 5)]
            expected = panel.copy()
            expected_flags = [
                [1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 0, 1, 1, 1],
                [0, 0, 1, 1, 1, 0, 1, 1, 1],
                [0, 0, 0, 1, 1, 0, 0, 1, 1],
                [0, 0, 0, 0, 1, 0, 0, 0, 1],
                [0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 1, 1, 1, 1],
                [0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0],
            ]
            expected[flags] = pd.DataFrame(expected_flags, columns=flags)
            for folder, prefix, count in (("DE NOVO", "DE NOVO", 1),
                                          ("Failures", "Failures", 5),
                                          ("Mergers", "Mergers", 9)):
                target = root / "Material Events" / folder / "Call Reports"
                self.assertEqual([path.name for path in target.iterdir()],
                                 [prefix + "_20200331.csv"])
                actual = pd.read_csv(target / (prefix + "_20200331.csv"))
                pd.testing.assert_frame_equal(actual, expected[list(panel.columns) + flags[:count]])

            for stage, spec in config.scripts.items():
                log = (runner.log_dir / (stage + ".log")).read_text(encoding="utf-8")
                command = next(line[len("command: "):] for line in log.splitlines()
                               if line.startswith("command: "))
                self.assertEqual(shlex.split(command),
                                 [sys.executable, "-u", str(spec.path), *spec.args])


if __name__ == "__main__":
    unittest.main()
