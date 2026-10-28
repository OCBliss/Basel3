"""Apply Basel3's reporting-date cleanup through the CallReports library."""

import argparse
from pathlib import Path

import pandas as pd

from callreports import clean_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data/CSV/Cleaned")
    args = parser.parse_args(argv)
    for path in sorted(args.input_dir.glob("Cleaned_Call_Report_*.csv")):
        reporting_date = path.stem.rsplit("_", 1)[-1]
        clean_report(pd.read_csv(path, low_memory=False), reporting_date).to_csv(path, index=False)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
