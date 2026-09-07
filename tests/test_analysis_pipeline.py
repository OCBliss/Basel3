"""Exercise horizon/bin selection through real downstream pipeline subprocesses."""
import contextlib
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import Task_manager_Global_yaml_driven as manager


class AnalysisPipelineTests(unittest.TestCase):
    def test_default_yaml_runs_all_four_horizons_and_all_four_bin_specifications(self):
        self.run_analysis_case()

    def test_selected_horizons_reach_every_stage_and_ignore_stale_other_bins(self):
        self.run_analysis_case(horizons=[1, 3], bins=[20])

    def run_analysis_case(self, horizons=None, bins=None):
        raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
        if horizons is not None:
            raw["parameters"]["horizons"] = horizons
        if bins is not None:
            raw["parameters"]["bins1"] = bins
        horizons = raw["parameters"]["horizons"]
        bins = raw["parameters"]["bins1"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            material = root / "Material Events"
            inputs = material / "Mergers/Call Reports"
            inputs.mkdir(parents=True)
            pd.DataFrame({
                "CERT": [1, 2, 3], "RCON9999": [20240331] * 3,
                "ratio": [-0.5, 0.5, 0.0],
                "FAILURE_T1": [1, 0, 0], "MERGER_T1": [0, 1, 0],
                "FAILURE_T2": [1, 0, 0], "MERGER_T2": [0, 1, 0],
                "FAILURE_T3": [0, 1, 0], "MERGER_T3": [1, 0, 0],
                "FAILURE_T4": [0, 1, 0], "MERGER_T4": [1, 0, 0],
            }).to_csv(inputs / "Mergers_Call_Report_20240331.csv", index=False)
            pd.DataFrame({"Quarters": [20240331]}).to_csv(
                material / "quarters_basel3.csv", index=False)
            stale_paths = []
            for stage, prefix in [("Binned", ""), ("Probabilities", "probabilities_")]:
                stale = material / "Failures/JS Divergence/Basel III T+1" / stage
                stale.mkdir(parents=True)
                path = stale / (prefix + "Peer_Group_Failures_Basel3_t1_binned_120.csv")
                path.write_text("unselected stale input must not be read\n")
                stale_paths.append(path)
            stale_jsd = material / "JSD/BASEL III T+1/JSD_survivors_vs_failures_120.csv"
            stale_jsd.parent.mkdir(parents=True)
            stale_jsd.write_text("unselected stale input must not be read\n")
            stale_paths.append(stale_jsd)
            before = {path: path.read_bytes() for path in stale_paths}

            selected = {step for step in raw["scripts"] if step.startswith(("7.", "8."))}
            raw["scripts"] = {step: spec for step, spec in raw["scripts"].items() if step in selected}
            for spec in raw["scripts"].values():
                spec["cwd"] = str(root)
                for key in ["inputs", "outputs", "create_dirs"]:
                    if key in spec:
                        spec[key] = [str(root / path) for path in spec[key]]
            raw["dependencies"] = {step: [child for child in children if child in selected]
                                   for step, children in raw["dependencies"].items()
                                   if step in selected and any(child in selected for child in children)}
            raw["execution"] = [phase for phase in raw["execution"]
                                if next(iter(phase)) in {"sequential", "intermediate_steps"}
                                and set(next(iter(phase.values()))) <= selected]
            raw["log_root"] = str(root / "logs")
            path = root / "analysis.yaml"
            path.write_text(yaml.safe_dump(raw, sort_keys=False))
            config = manager.load_config(path)
            runner = manager.PipelineRunner(config, run_id="selected")
            runner.preflight()
            runner.initialize_logs()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                try:
                    runner.run()
                except Exception:
                    self.fail(output.getvalue())
            self.assertEqual(selected, runner.completed)
            expected_failure = {1: 1, 2: 1, 3: 2, 4: 2}
            for horizon in horizons:
                peer = pd.read_csv(material / f"Failures/Horizons/Peer_Group_Failures_Basel3_t{horizon}.csv")
                self.assertEqual([expected_failure[horizon]], peer["CERT"].tolist())
                for group in ["Failures", "Mergers", "Survivors"]:
                    for count in bins:
                        binned = pd.read_csv(material / group / f"JS Divergence/Basel III T+{horizon}/Binned/Peer_Group_{group}_Basel3_t{horizon}_binned_{count}.csv")
                        self.assertEqual(count + 6, len(binned))
                        self.assertEqual(1, binned["ratio"].sum())
                for kind in ["JSD", "IG"]:
                    actual = {p.name for p in (material / kind / f"BASEL III T+{horizon}").glob("*.csv")
                              if p != stale_jsd}
                    self.assertEqual({f"JSD_{pair}_{count}.csv" for count in bins for pair in
                                      ["survivors_vs_failures", "survivors_vs_mergers", "mergers_vs_failures"]}, actual)
            self.assertEqual(before, {path: path.read_bytes() for path in stale_paths})
            for unselected in {1, 2, 3, 4} - set(horizons):
                self.assertFalse(any(f"T+{unselected}" in str(p) or f"Basel3_t{unselected}" in p.name
                                     for p in material.rglob("*")))
            self.assertFalse(list((material / "IG").rglob("*_120.csv")))


if __name__ == "__main__":
    unittest.main()
