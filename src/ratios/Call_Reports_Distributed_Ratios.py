#!/usr/bin/env python3
"""Build four-quarter distributed-lag call-report datasets."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pandas as pd


SOURCE_DIR = Path(__file__).resolve().parents[1]
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

import Basel3_Global_Filepath as paths  # noqa: E402


def load_quarters(quarters_file: Path) -> List[str]:
    """Load ordered YYYYMMDD quarter identifiers from the first CSV column."""

    quarters = pd.read_csv(quarters_file).iloc[:, 0].astype(str)
    valid = quarters[quarters.str.fullmatch(r"\d{8}", na=False)]
    if valid.empty:
        raise ValueError(f"No YYYYMMDD quarters found in {quarters_file}")
    return valid.tolist()


def build_distributed_reports(
    interleaved_dir: Path,
    output_dir: Path,
    quarters_file: Path,
) -> List[Path]:
    """Merge each report with the following three configured quarters.

    Missing current-quarter files are skipped, matching the historical pipeline
    behavior. Missing comparison quarters yield a partial window and are reported.
    """

    quarters = load_quarters(quarters_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []

    for index, current_quarter in enumerate(quarters[:-3]):
        current_name = f"Cleaned_Call_Report_{current_quarter}.csv"
        current_path = interleaved_dir / current_name
        if not current_path.is_file():
            print(f"Skipping missing current report: {current_path}")
            continue

        distributed = pd.read_csv(current_path)
        if "CERT" not in distributed.columns:
            raise ValueError(f"Required CERT column missing from {current_path}")

        for comparison_quarter in quarters[index + 1 : index + 4]:
            comparison_path = (
                interleaved_dir / f"Cleaned_Call_Report_{comparison_quarter}.csv"
            )
            if not comparison_path.is_file():
                print(f"Skipping missing comparison report: {comparison_path}")
                continue
            comparison = pd.read_csv(comparison_path)
            if "CERT" not in comparison.columns:
                raise ValueError(f"Required CERT column missing from {comparison_path}")
            distributed = distributed.merge(
                comparison,
                on="CERT",
                how="left",
                suffixes=("", f"_{comparison_quarter}"),
                validate="one_to_one",
            )

        output_path = output_dir / f"Distributed_{current_name}"
        distributed.to_csv(output_path, index=False)
        written.append(output_path)
        print(f"Processed and saved: {output_path}")

    return written


def main() -> int:
    build_distributed_reports(
        Path(paths.INTERLEAVED_DIR),
        Path(paths.DISTRIBUTED_DIR) / "RAW",
        Path(paths.CSV_DIR) / "quarters.csv",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
