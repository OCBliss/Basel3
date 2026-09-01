#!/usr/bin/env python3
"""Replace missing distributed-lag values on populated Call Report rows."""

from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import Basel3_Global_Filepath as paths  # noqa: E402


def clean_distributed_frame(report):
    if report.empty:
        return report.copy()

    cleaned = report.copy()
    bank_identifier = cleaned.iloc[:, 0]
    populated_bank = (
        bank_identifier.notna()
        & bank_identifier.astype(str).str.strip().ne("")
    )
    cleaned.loc[populated_bank] = cleaned.loc[populated_bank].fillna(0)
    return cleaned


def clean_distributed_reports(raw_dir, cleaned_dir):
    raw_dir = Path(raw_dir)
    cleaned_dir = Path(cleaned_dir)
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    written = []

    for raw_path in sorted(raw_dir.glob("*.csv")):
        cleaned = clean_distributed_frame(pd.read_csv(raw_path))
        output_path = cleaned_dir / raw_path.name
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        cleaned.to_csv(temporary_path, index=False)
        temporary_path.replace(output_path)
        written.append(output_path)
        print("Cleaned distributed report: {}".format(output_path))

    return written


def main():
    written = clean_distributed_reports(
        Path(paths.DISTRIBUTED_DIR) / "RAW",
        Path(paths.DISTRIBUTED_DIR) / "Cleaned",
    )
    print("Cleaned {} distributed report files".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
