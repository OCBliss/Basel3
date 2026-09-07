"""Bin peer-group ratio columns for explicitly selected horizons and bin counts."""

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd


sys.path.append(str(Path(__file__).resolve().parents[2]))
import Basel3_Global_Filepath as paths


GROUPS = ("Mergers", "Failures", "Survivors")


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("bin counts must be positive integers")
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizons", nargs="+", type=int, choices=(1, 2, 3, 4), required=True)
    parser.add_argument("--bins1", nargs="+", type=positive_int, required=True,
                        help="Selected bin counts across -1 to 1, for example 20 30 50 100.")
    parser.add_argument("--bins2", type=positive_int, default=5,
                        help="Bin count across 1 to 2 (default: 5).")
    parser.add_argument("--bins3", type=int, choices=(1,), default=1,
                        help="One unbounded final bin (default: 1).")
    parser.add_argument("--material-dir", type=Path, default=Path(paths.MAT_DIR))
    return parser.parse_args(argv)


def make_bin_edges(bins1, bins2=5, bins3=1):
    if bins1 < 1 or bins2 < 1 or bins3 != 1:
        raise ValueError("bins1 and bins2 must be positive; bins3 must be 1")
    # Each shared boundary occurs once. The old repeated 2 edge added an
    # always-empty [2, 2) row; all other histogram intervals stay unchanged.
    return np.concatenate((
        np.linspace(-1, 1, bins1 + 1),
        np.linspace(1, 2, bins2 + 1)[1:],
        np.array([np.inf]),
    ))


def bin_ratios(frame, edges):
    labels = [f"[{lower:.2f}, inf)" if np.isinf(upper)
              else f"[{lower:.2f}, {upper:.2f})"
              for lower, upper in zip(edges[:-1], edges[1:])]
    counts = {}
    # Preserve the original positional exclusion of CERT and reporting quarter.
    for column in frame.columns[2:]:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        counts[column], _ = np.histogram(values, bins=edges)
    result = pd.DataFrame(counts, index=labels)
    result.rename_axis("Bin", inplace=True)
    return result


def main(argv=None):
    args = parse_args(argv)
    horizons = list(dict.fromkeys(args.horizons))
    specifications = {count: make_bin_edges(count, args.bins2, args.bins3)
                      for count in dict.fromkeys(args.bins1)}
    for group in GROUPS:
        for horizon in horizons:
            source = args.material_dir / group / "Horizons" / f"Peer_Group_{group}_Basel3_t{horizon}.csv"
            frame = pd.read_csv(source)
            output = args.material_dir / group / "JS Divergence" / f"Basel III T+{horizon}" / "Binned"
            output.mkdir(parents=True, exist_ok=True)
            for count, edges in specifications.items():
                target = output / f"{source.stem}_binned_{count}.csv"
                bin_ratios(frame, edges).to_csv(target)
                print(f"[INFO] Binned data for file '{source.name}' saved to '{target}'.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
