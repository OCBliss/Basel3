"""Normalize selected peer-group histogram files into probability mass functions."""

import argparse
from pathlib import Path
import re
import sys

import pandas as pd


sys.path.append(str(Path(__file__).resolve().parents[2]))
import Basel3_Global_Filepath as paths


GROUPS = ("Mergers", "Failures", "Survivors")
BIN_SUFFIX = re.compile(r"_binned_(\d+)\.csv$")


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("bin counts must be positive integers")
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizons", nargs="+", type=int, choices=(1, 2, 3, 4), required=True)
    parser.add_argument("--bins", nargs="+", type=positive_int, required=True,
                        help="Selected bins1 counts in _binned_<count>.csv filenames.")
    parser.add_argument("--material-dir", type=Path, default=Path(paths.MAT_DIR))
    return parser.parse_args(argv)


def selected_files(directory, bins):
    files = []
    found = set()
    for filename in sorted(directory.glob("*.csv")):
        match = BIN_SUFFIX.search(filename.name)
        if match and int(match.group(1)) in bins:
            files.append(filename)
            found.add(int(match.group(1)))
    missing = set(bins) - found
    if missing:
        raise FileNotFoundError(f"No binned CSV files for {sorted(missing)} in {directory}.")
    return files


def normalize_counts(binned, filename):
    probabilities = binned[["Bin"]].copy()
    for column in binned.columns:
        if column == "Bin":
            continue
        total = binned[column].sum()
        if total == 0:
            print(f"Column {column} in file {filename} has a total of 0. Skipping.", flush=True)
            probabilities[column] = 0
        else:
            probabilities[column] = binned[column] / total
    return probabilities


def main(argv=None):
    args = parse_args(argv)
    bins = set(args.bins)
    for group in GROUPS:
        for horizon in dict.fromkeys(args.horizons):
            directory = args.material_dir / group / "JS Divergence" / f"Basel III T+{horizon}"
            files = selected_files(directory / "Binned", bins)
            output = directory / "Probabilities"
            output.mkdir(parents=True, exist_ok=True)
            for filename in files:
                print(f"Processing file: {filename.name}", flush=True)
                binned = pd.read_csv(filename)
                target = output / f"probabilities_{filename.name}"
                normalize_counts(binned, filename.name).to_csv(target, index=False)
                print(f"Probabilities saved to {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
