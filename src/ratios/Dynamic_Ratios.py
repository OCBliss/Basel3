"""Build current and three-quarter Call Report ratio changes."""

import argparse
from pathlib import Path
import re
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1]
CALL_REPORT_DIR = SRC_DIR / "call reports"
for import_path in (CALL_REPORT_DIR, SRC_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import Basel3_Global_Filepath as paths  # noqa: E402
from Call_Report import QuarterCache  # noqa: E402
from Call_Reports_v4_0 import FEATURE_COLUMNS, process_dataframe  # noqa: E402


REPORT_QUARTER = re.compile(r"(\d{8})$")
RATIO_COLUMNS = FEATURE_COLUMNS[3:]


def relative_change(current, previous):
    current = pd.to_numeric(current, errors="coerce")
    previous = pd.to_numeric(previous, errors="coerce")
    change = pd.Series(float("nan"), index=current.index, dtype="float64")
    known = current.notna() & previous.notna()
    zero_baseline = known & previous.eq(0)
    nonzero_baseline = known & previous.ne(0)
    change.loc[zero_baseline] = 0.0
    change.loc[nonzero_baseline] = (
        current.loc[nonzero_baseline]
        .div(previous.loc[nonzero_baseline])
        .sub(1)
    )
    return change


def _check_certificates(report, label):
    if "CERT" not in report.columns:
        raise ValueError("Required CERT column missing from {}".format(label))
    if report["CERT"].isna().any():
        raise ValueError("Missing CERT value in {}".format(label))
    if report["CERT"].duplicated().any():
        raise pd.errors.MergeError("Duplicate CERT value in {}".format(label))


def _lag_values(current, lagged, ratio_columns, label):
    _check_certificates(lagged, label)
    missing = [column for column in ratio_columns if column not in lagged]
    if missing:
        raise ValueError(
            "Missing ratio columns in {}: {}".format(label, ", ".join(missing))
        )
    return current[["CERT"]].merge(
        lagged[["CERT"] + list(ratio_columns)],
        on="CERT",
        how="left",
        sort=False,
        validate="one_to_one",
    )


def _certificate_roots(source, history, date):
    required = ("IDRSSD", "RCON9999", "FDIC Certificate Number")
    missing = [column for column in required if column not in source]
    if missing:
        raise ValueError(
            "Missing cleaned source columns: {}".format(", ".join(missing))
        )

    roots = source.copy()
    roots["IDRSSD"] = float("nan")
    anchors = pd.to_numeric(source["RCON9999"], errors="coerce")
    certificates = pd.to_numeric(
        source["FDIC Certificate Number"],
        errors="coerce",
    )

    for anchor in anchors.dropna().unique():
        actual = history.resolve(int(anchor), date)
        historical = history.frame(actual)
        if historical is None:
            continue
        if "FDIC Certificate Number" not in historical:
            raise ValueError(
                "Historical quarter {} has no FDIC Certificate Number".format(
                    actual
                )
            )

        historical_certificates = pd.to_numeric(
            historical["FDIC Certificate Number"],
            errors="coerce",
        )
        populated = historical_certificates.notna()
        if historical_certificates.loc[populated].duplicated().any():
            raise pd.errors.MergeError(
                "Duplicate CERT value in historical quarter {}".format(actual)
            )
        rssd_by_certificate = pd.Series(
            historical.index[populated],
            index=historical_certificates.loc[populated],
        )
        rows = anchors.eq(anchor)
        roots.loc[rows, "IDRSSD"] = certificates.loc[rows].map(
            rssd_by_certificate
        )

    roots = roots.loc[roots["IDRSSD"].notna()].copy()
    if not roots.empty:
        roots["IDRSSD"] = roots["IDRSSD"].astype("int64")
    return roots


def build_dynamic_report(
    current,
    previous_quarter,
    previous_two_quarters,
    previous_three_quarters,
    ratio_columns=None,
):
    if ratio_columns is None:
        ratio_columns = RATIO_COLUMNS
    ratio_columns = tuple(ratio_columns)

    required = ("CERT", "RCON9999") + ratio_columns
    missing = [column for column in required if column not in current]
    if missing:
        raise ValueError(
            "Missing current-quarter columns: {}".format(", ".join(missing))
        )
    _check_certificates(current, "P0")

    current = current.loc[:, list(required)].reset_index(drop=True)
    p1q = _lag_values(current, previous_quarter, ratio_columns, "P1Q")
    p2q = _lag_values(current, previous_two_quarters, ratio_columns, "P2Q")
    p3q = _lag_values(current, previous_three_quarters, ratio_columns, "P3Q")

    calculated = {
        "CERT": current["CERT"],
        "RCON9999": current["RCON9999"],
    }
    for column in ratio_columns:
        calculated["{}_q0".format(column)] = pd.to_numeric(
            current[column], errors="coerce"
        )

    for lag, report in ((1, p1q), (2, p2q), (3, p3q)):
        for column in ratio_columns:
            calculated["{}_q0q{}".format(column, lag)] = relative_change(
                current[column], report[column]
            )

    return pd.DataFrame(calculated)


def _quarter_from_name(path):
    match = REPORT_QUARTER.search(Path(path).stem)
    if match is None:
        raise ValueError("No reporting quarter in {}".format(path))
    return match.group(1)


def build_dynamic_reports(
    cleaned_dir,
    interleaved_dir,
    output_dir,
    history=None,
    map_file=None,
):
    cleaned_dir = Path(cleaned_dir)
    interleaved_dir = Path(interleaved_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if history is None:
        history = QuarterCache(
            map_file=map_file,
            data_dir=cleaned_dir,
        )

    written = []
    for current_path in sorted(
        interleaved_dir.glob("Cleaned_Call_Report_*.csv")
    ):
        source_path = cleaned_dir / current_path.name
        if not source_path.is_file():
            raise FileNotFoundError(
                "Cleaned source missing for {}".format(current_path.name)
            )

        current = pd.read_csv(current_path, low_memory=False)
        source = pd.read_csv(source_path, low_memory=False)

        p1q_source = _certificate_roots(
            source,
            history,
            "P1Q",
        )
        p2q_source = _certificate_roots(
            source,
            history,
            "P2Q",
        )
        p3q_source = _certificate_roots(
            source,
            history,
            "P3Q",
        )

        previous_quarter = process_dataframe(
            p1q_source,
            history=history,
            date="P1Q",
        )
        previous_two_quarters = process_dataframe(
            p2q_source,
            history=history,
            date="P2Q",
        )
        previous_three_quarters = process_dataframe(
            p3q_source,
            history=history,
            date="P3Q",
        )

        dynamic = build_dynamic_report(
            current,
            previous_quarter,
            previous_two_quarters,
            previous_three_quarters,
        )
        quarter = _quarter_from_name(current_path)
        output_path = output_dir / (
            "Dynamic_Cleaned_Call_Report_{}.csv".format(quarter)
        )
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        dynamic.to_csv(temporary_path, index=False)
        temporary_path.replace(output_path)
        written.append(output_path)
        print("Built dynamic report: {}".format(output_path))

    return written


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cleaned-dir",
        type=Path,
        default=Path(paths.CLEANED_DIR),
    )
    parser.add_argument(
        "--interleaved-dir",
        type=Path,
        default=Path(paths.INTERLEAVED_DIR),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(paths.DYNAMIC_DIR) / "Cleaned",
    )
    parser.add_argument("--quarter-map", type=Path)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    written = build_dynamic_reports(
        args.cleaned_dir,
        args.interleaved_dir,
        args.output_dir,
        map_file=args.quarter_map,
    )
    print("Built {} dynamic report files".format(len(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
