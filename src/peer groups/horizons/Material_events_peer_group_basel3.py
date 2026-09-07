"""Filter quarterly peer-group files by calendar and concatenate selected horizons."""

import argparse
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import Basel3_Global_Filepath as paths


GROUPS = ("Mergers", "Failures", "Survivors")


def filter_and_concatenate(process_dir, output_dir, output_filename, valid_dates, label):
    process_dir = Path(process_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filenames = [name for name in os.listdir(process_dir) if name.endswith(".csv")]
    if not filenames:
        print("No CSV files found in {} for {}.".format(process_dir, label))
        return None

    frames = []
    for filename in filenames:
        file_date = os.path.splitext(filename)[0][-8:]
        if file_date in valid_dates:
            frames.append(pd.read_csv(process_dir / filename))
        else:
            print("Skipped {}; date {} not in quarter map for {}.".format(filename, file_date, label))

    if not frames:
        print("No matching files found for {}. No concatenation performed.".format(label))
        return None

    combined = pd.concat(frames, ignore_index=True)
    target = output_dir / output_filename
    combined.to_csv(target, index=False)
    print("Saved {}.".format(target))
    return target


def build_horizon_panels(material_dir, horizons, quarter_map=None):
    material_dir = Path(material_dir)
    quarter_map = Path(quarter_map) if quarter_map is not None else material_dir / "quarters_basel3.csv"
    quarters = pd.read_csv(quarter_map)
    valid_dates = set(quarters["Quarters"].astype(str))
    written = []
    for horizon in dict.fromkeys(horizons):
        for group in GROUPS:
            output_dir = material_dir / group / "Horizons"
            target = filter_and_concatenate(
                output_dir / ("Basel III T+" + str(horizon)),
                output_dir,
                "Peer_Group_{}_Basel3_t{}.csv".format(group, horizon),
                valid_dates,
                group,
            )
            if target is not None:
                written.append(target)
    return written


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizons", nargs="+", type=int, choices=(1, 2, 3, 4), required=True)
    parser.add_argument("--material-dir", type=Path, default=Path(paths.MAT_DIR))
    parser.add_argument("--quarter-map", type=Path,
                        help="Allowed filename dates; defaults to <material-dir>/quarters_basel3.csv.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    written = build_horizon_panels(args.material_dir, args.horizons, args.quarter_map)
    print("Wrote {} concatenated peer-group files.".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
