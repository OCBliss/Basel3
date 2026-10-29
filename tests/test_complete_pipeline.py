"""Run all production stages with cached ZIPs, offline FDIC data and installed CallReports."""

import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import pandas as pd
import yaml

from test_call_reports_v4 import source_row
from test_material_events import EVENT_FILES, manager, write_fixture, write_http_stub


ROOT = Path(__file__).resolve().parents[1]


class CompletePipelineTests(unittest.TestCase):
    def test_all_twenty_stages_use_the_installed_package_without_local_definitions(self):
        temporary_root = ROOT / ".cache/tests/tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
            root = Path(directory)
            # Leave the package source out of the runnable checkout. Every child
            # must resolve CallReports from the active Python installation.
            shutil.copytree(ROOT / "src", root / "src",
                            ignore=shutil.ignore_patterns("RWA", "callreports", "__pycache__"))
            shutil.copytree(ROOT / "pipeline", root / "pipeline",
                            ignore=shutil.ignore_patterns("rwa_*", "__pycache__"))
            self.assertFalse((root / "src/callreports").exists())
            write_fixture(root)
            for path in (root / "data/CSV/Dynamic_Lag/Cleaned").glob("*.csv"):
                path.unlink()  # Ratios must be produced from ZIPs, never seeded.
            material = root / "Material Events"
            pd.DataFrame({"Quarters": [20200331]}).to_csv(
                material / "quarters_basel3.csv", index=False)
            stub = write_http_stub(root)
            with (stub / "sitecustomize.py").open("a") as handle:
                handle.write('\nimport callreports\n'
                             'assert "site-packages" in str(Path(callreports.__file__).resolve())\n'
                             '(root / "installed-package.txt").write_text(callreports.__file__)\n'
                             'def reject_live_http(*args, **kwargs):\n'
                             '    raise AssertionError("Unexpected live HTTP request in offline pipeline test")\n'
                             'requests.sessions.Session.request = reject_live_http\n')

            raw = copy.deepcopy(manager._load_yaml(manager.DEFAULT_CONFIG))
            for step in ("6.0.1", "6.0.2", "6.0.3"):
                args = raw["scripts"][step]["args"]
                for option, value in (("--start-date", "2019-01-01"),
                                      ("--end-date", "2021-12-31"), ("--limit", 137)):
                    args[args.index(option) + 1] = value
            config = root / "pipeline/pipeline_config_dynamic.yaml"
            config.write_text(yaml.safe_dump(raw, sort_keys=False))

            dates = pd.date_range("2018-06-30", "2021-12-31", freq=pd.offsets.QuarterEnd())
            archive_dir = root / "data/FFIEC/archives"
            archive_dir.mkdir(parents=True)
            certificates = list(range(101, 109)) + [9101]
            for index, quarter in enumerate(dates):
                stamp = quarter.strftime("%m%d%Y")
                date = int(quarter.strftime("%Y%m%d"))
                rows = []
                for offset, cert in enumerate(certificates):
                    row = source_row(date, rssd=cert + 10000)
                    row["FDIC Certificate Number"] = cert
                    for prefix in ("RCON", "RCFD"):
                        row.update({prefix + "2170": 1000 + cert,
                                    prefix + "JA22": 0, prefix + "3123": 0,
                                    prefix + "2143": 20 + index + offset,
                                    prefix + "3545": 20 + index + offset})
                    rows.append(row)
                frame = pd.DataFrame(rows)
                por = frame[["IDRSSD", "FDIC Certificate Number"]]
                ent = frame[["IDRSSD", "RCON9999"]].copy()
                ent["RCON9224"] = ["Bank " + str(cert) for cert in certificates]
                schedule = frame.drop(columns=["FDIC Certificate Number", "RCON9999"])
                schedule = schedule[["IDRSSD"] + [name for name in schedule if name != "IDRSSD"]]
                with zipfile.ZipFile(archive_dir / (str(date) + ".zip"), "w") as archive:
                    archive.writestr("FFIEC CDR Call Bulk POR " + stamp + ".txt",
                                     por.to_csv(index=False, sep="\t"))
                    for name, table in (("ENT", ent), ("RC", schedule)):
                        text = io.StringIO()
                        table.iloc[:0].to_csv(text, index=False, sep="\t")
                        text.write("\t".join([""] + ["DESCRIPTION"] * (len(table.columns) - 1)) + "\n")
                        table.to_csv(text, index=False, header=False, sep="\t")
                        archive.writestr("FFIEC CDR Call Schedule " + name + " " + stamp + ".txt",
                                         text.getvalue())
            calendar = []
            for quarter in dates:
                entry = {"P0": int(quarter.strftime("%Y%m%d")), "Quarter": quarter.quarter}
                for label, count in (("P1Q", 1), ("P2Q", 2), ("P3Q", 3), ("P1Y", 4)):
                    prior = quarter - pd.offsets.QuarterEnd(count)
                    entry[label] = int(prior.strftime("%Y%m%d"))
                calendar.append(entry)
            pd.DataFrame(calendar).to_csv(root / "data/CSV/quarter_flag.csv", index=False)

            environment = dict(os.environ, PYTHONPATH=str(stub))
            completed = subprocess.run(
                [sys.executable, str(root / "pipeline/Task_manager_Global_yaml_driven.py"),
                 "--config", str(config)], cwd=root, env=environment,
                capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(0, completed.returncode, completed.stdout[-18000:] + completed.stderr)
            for stage in raw["scripts"]:
                self.assertIn("DONE " + stage + "\n", completed.stdout)
            self.assertEqual(20, len(raw["scripts"]))
            self.assertEqual(15, len(json.loads((root / "data/FFIEC/prepared.json").read_text())["quarters"]))
            self.assertIn("site-packages", (root / "installed-package.txt").read_text())

            # Independent expectations connect the source fields to downstream
            # values, rather than comparing one pipeline function to another.
            current = pd.read_csv(root / "data/CSV/Interleaved/Cleaned_Call_Report_20200331.csv")
            self.assertAlmostEqual(27 / 1101, current.set_index("CERT").loc[101, "RC-Item10-Item12"])
            dynamic = pd.read_csv(root / "data/CSV/Dynamic_Lag/Cleaned/Dynamic_Cleaned_Call_Report_20200331.csv")
            self.assertEqual(306, len(dynamic.columns))
            for lag in (1, 2, 3):
                self.assertAlmostEqual(27 / (27 - lag) - 1,
                                       dynamic.set_index("CERT").loc[101, "RC-Item10-Item12_q0q" + str(lag)])
            failure = pd.read_csv(material / "Failures/Horizons/Peer_Group_Failures_Basel3_t1.csv")
            self.assertEqual([101, 102], sorted(failure["CERT"].tolist()))
            for event, (folder, filename) in EVENT_FILES.items():
                self.assertTrue((root / ("request_" + event + ".json")).is_file())
                self.assertTrue((material / folder / "Cleaned" / filename).is_file())
                self.assertFalse((material / folder / "RAW" / filename).exists())
                self.assertTrue((material / folder / "RAW/keep.txt").is_file())
            for horizon in raw["parameters"]["horizons"]:
                for bins in raw["parameters"]["bins1"]:
                    for group in ("Failures", "Mergers", "Survivors"):
                        pmf = pd.read_csv(material / group / (
                            "JS Divergence/Basel III T+" + str(horizon)) / "Probabilities" / (
                            "probabilities_Peer_Group_" + group + "_Basel3_t" + str(horizon) +
                            "_binned_" + str(bins) + ".csv"))
                        self.assertAlmostEqual(1, pmf["RC-Item10-Item12_q0"].sum())
                    for pair in ("survivors_vs_failures", "survivors_vs_mergers", "mergers_vs_failures"):
                        for stage in ("JSD", "IG"):
                            self.assertTrue((material / stage / ("BASEL III T+" + str(horizon)) /
                                             ("JSD_" + pair + "_" + str(bins) + ".csv")).is_file())


if __name__ == "__main__":
    unittest.main()
