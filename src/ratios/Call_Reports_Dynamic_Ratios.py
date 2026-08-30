#!/usr/bin/env python3
"""Calculate current-to-prior-quarter changes for distributed Call Reports."""

from pathlib import Path
import re
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import Basel3_Global_Filepath as paths  # noqa: E402


REPORT_QUARTER = re.compile(r"(\d{8})$")


def load_quarters(quarters_file):
    quarters = pd.read_csv(quarters_file).iloc[:, 0].astype(str)
    valid = quarters[quarters.str.fullmatch(r"\d{8}", na=False)]
    if valid.empty:
        raise ValueError("No Call Report quarters found in {}".format(quarters_file))
    return valid.tolist()


def previous_quarters(filename, quarters):
    match = REPORT_QUARTER.search(Path(filename).stem)
    if match is None:
        raise ValueError("No quarter in distributed filename: {}".format(filename))
    current_quarter = match.group(1)
    if current_quarter not in quarters:
        raise ValueError("Quarter {} is not configured".format(current_quarter))
    position = quarters.index(current_quarter)
    prior = quarters[position + 1 : position + 4]
    if len(prior) != 3:
        raise ValueError("Three prior quarters are required for {}".format(current_quarter))
    return current_quarter, prior


def relative_change(current, previous):
    """Return current / previous - 1, with a true zero baseline mapped to zero."""

    change = pd.Series(0.0, index=current.index)
    nonzero_baseline = previous.ne(0)
    change.loc[nonzero_baseline] = (
        current.loc[nonzero_baseline]
        .div(previous.loc[nonzero_baseline])
        .sub(1)
    )
    return change


def build_dynamic_report(distributed, prior_quarters):
    base_columns = [column for column in distributed if "_" not in column]
    calculated = {"CERT": distributed["CERT"]}
    lag_columns = {1: [], 2: [], 3: []}

    for column in base_columns:
        current_name = "{}_q0".format(column)
        current = pd.to_numeric(distributed[column], errors="coerce")
        calculated[current_name] = current

        for lag, quarter in enumerate(prior_quarters, start=1):
            source_name = "{}_{}".format(column, quarter)
            if source_name not in distributed:
                continue
            change_name = "{}_q0q{}".format(column, lag)
            previous = pd.to_numeric(distributed[source_name], errors="coerce")
            calculated[change_name] = relative_change(current, previous)
            lag_columns[lag].append(change_name)

    current_columns = ["{}_q0".format(column) for column in base_columns]
    ordered = current_columns + lag_columns[1] + lag_columns[2] + lag_columns[3]
    return pd.DataFrame(calculated)[["CERT"] + ordered]


def build_dynamic_reports(cleaned_dir, output_dir, quarters_file):
    cleaned_dir = Path(cleaned_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    quarters = load_quarters(quarters_file)
    written = []

    for source_path in sorted(
        cleaned_dir.glob("Distributed_Cleaned_Call_Report_*.csv")
    ):
        _, prior = previous_quarters(source_path.name, quarters)
        dynamic = build_dynamic_report(pd.read_csv(source_path), prior)
        quarter = REPORT_QUARTER.search(source_path.stem).group(1)
        output_path = output_dir / "Dynamic_Raw_Call_Report_{}.csv".format(quarter)
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        dynamic.to_csv(temporary_path, index=False)
        temporary_path.replace(output_path)
        written.append(output_path)
        print("Built dynamic report: {}".format(output_path))

    return written


def main():
    written = build_dynamic_reports(
        Path(paths.DISTRIBUTED_DIR) / "Cleaned",
        Path(paths.DYNAMIC_DIR) / "RAW",
        Path(paths.CSV_DIR) / "quarters.csv",
    )
    print("Built {} dynamic report files".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
