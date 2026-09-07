"""Write quarterly peer-group files for explicitly selected event horizons."""

import argparse
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import Basel3_Global_Filepath as paths


GROUPS = ("Failures", "Mergers", "Survivors")


def peer_filename(filename, group):
    if group == "Mergers":
        return filename
    if filename.startswith("Mergers_"):
        return filename.replace("Mergers_", group + "_", 1)
    return group + "_" + filename


def build_peer_groups(material_dir, horizons, input_dir=None):
    material_dir = Path(material_dir)
    input_dir = Path(input_dir) if input_dir is not None else material_dir / "Mergers" / "Call Reports"
    horizons = list(dict.fromkeys(horizons))
    outputs = {
        (horizon, group): material_dir / group / "Horizons" / ("Basel III T+" + str(horizon))
        for horizon in horizons for group in GROUPS
    }
    for directory in outputs.values():
        directory.mkdir(parents=True, exist_ok=True)

    filenames = [name for name in os.listdir(input_dir) if name.endswith(".csv")]
    if not filenames:
        print("No CSV files found in {}.".format(input_dir))

    written = []
    for filename in filenames:
        data = pd.read_csv(input_dir / filename)
        for horizon in horizons:
            failure_flag = "FAILURE_T" + str(horizon)
            merger_flag = "MERGER_T" + str(horizon)
            failures = data[data[failure_flag] == 1]
            mergers = data[data[merger_flag] == 1]

            # The original survivor stage alone coerces these two flag columns.
            survivors = data.copy()
            survivors[failure_flag] = pd.to_numeric(survivors[failure_flag], errors="coerce")
            survivors[merger_flag] = pd.to_numeric(survivors[merger_flag], errors="coerce")
            drop_condition = (survivors[failure_flag] == 1) | (survivors[merger_flag] == 1)
            survivors = survivors[~drop_condition]

            for group, frame in zip(GROUPS, (failures, mergers, survivors)):
                target = outputs[horizon, group] / peer_filename(filename, group)
                frame.to_csv(target, index=False)
                written.append(target)
                print("Processed {} for {} and saved to {}.".format(filename, group, target))
    return written


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizons", nargs="+", type=int, choices=(1, 2, 3, 4), required=True)
    parser.add_argument("--material-dir", type=Path, default=Path(paths.MAT_DIR))
    parser.add_argument("--input-dir", type=Path,
                        help="Flagged reports; defaults to <material-dir>/Mergers/Call Reports.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    written = build_peer_groups(args.material_dir, args.horizons, args.input_dir)
    print("Wrote {} quarterly peer-group files.".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
