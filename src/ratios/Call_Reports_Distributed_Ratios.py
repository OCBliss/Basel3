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
    available_reports = {
        path.stem.rsplit("_", 1)[-1]: path
        for path in interleaved_dir.glob("Cleaned_Call_Report_*.csv")
    }
    report_cache = {}

    def load_report(quarter: str) -> pd.DataFrame:
        if quarter not in report_cache:
            report_path = available_reports[quarter]
            report = pd.read_csv(report_path)
            if "CERT" not in report.columns:
                raise ValueError(f"Required CERT column missing from {report_path}")
            report_cache[quarter] = report
        return report_cache[quarter]

    for index, current_quarter in enumerate(quarters[:-3]):
        if current_quarter not in available_reports:
            continue

        current_name = available_reports[current_quarter].name
        distributed = load_report(current_quarter).copy()
        missing_comparisons = []

        for comparison_quarter in quarters[index + 1 : index + 4]:
            if comparison_quarter not in available_reports:
                missing_comparisons.append(comparison_quarter)
                continue
            distributed = distributed.merge(
                load_report(comparison_quarter),
                on="CERT",
                how="left",
                suffixes=("", f"_{comparison_quarter}"),
                validate="one_to_one",
            )

        if missing_comparisons:
            print(
                "Partial window for {}: missing {}".format(
                    current_quarter, ", ".join(missing_comparisons)
                )
            )

        output_path = output_dir / f"Distributed_{current_name}"
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        distributed.to_csv(temporary_path, index=False)
        temporary_path.replace(output_path)
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
