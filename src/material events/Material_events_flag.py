"""Run the existing material-event flag stages, preserving their CSV boundaries."""

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(line_buffering=True)


def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "src":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'src' directory.")
        current_dir = parent_dir
    return current_dir


sys.path.append(find_code_dir())
import Basel3_Global_Filepath as paths


EVENTS = {
    "de_novo": {
        "folder": "DE NOVO",
        "input_dir": os.path.join(paths.DYNAMIC_DIR, "Cleaned"),
        "quarters": "quarters_de_novo.csv",
        "date": "ESTDATE",
        "ends": ["END_DATE"],
        "flags": ["DE_NOVO_FLAG"],
        "filename_pattern": r"(?i)Dynamic_Cleaned_",
        "filename_replacement": "DE NOVO_",
    },
    "failures": {
        "folder": "Failures",
        "input_dir": os.path.join(paths.MAT_DIR, "DE NOVO", "Call Reports"),
        "quarters": "quarters_failures.csv",
        "date": "EFFDATE",
        "ends": ["END_DATE1", "END_DATE2", "END_DATE3", "END_DATE4"],
        "flags": ["FAILURE_T1", "FAILURE_T2", "FAILURE_T3", "FAILURE_T4"],
        "filename_pattern": r"(?i)DE NOVO_",
        "filename_replacement": "Failures_",
    },
    "mergers": {
        "folder": "Mergers",
        "input_dir": os.path.join(paths.MAT_DIR, "Failures", "Call Reports"),
        "quarters": "quarters_failures.csv",
        "date": "EFFDATE",
        "ends": ["END_DATE1", "END_DATE2", "END_DATE3", "END_DATE4"],
        "flags": ["MERGER_T1", "MERGER_T2", "MERGER_T3", "MERGER_T4"],
        "filename_pattern": r"(?i)Failures",
        "filename_replacement": "Mergers",
    },
}


def load_events(event, config, material_dir):
    directory = os.path.join(material_dir, config["folder"], "Cleaned")
    files = [os.path.join(directory, name) for name in os.listdir(directory)
             if name.endswith(".csv")]
    if not files:
        label = "DE NOVO" if event == "de_novo" else "Mergers"
        raise FileNotFoundError(f"No {label} files found in the directory.")

    if event == "mergers":
        frames = []
        for filename in files:
            try:
                frame = pd.read_csv(filename)
                frame["source_file"] = os.path.basename(filename)
                frames.append(frame)
            except Exception as error:
                print(f"Error reading {filename}: {error}")
        data = pd.concat(frames, ignore_index=True)
        data["CERT"] = pd.to_numeric(data["CERT"], errors="coerce")
        finite = data["CERT"].apply(np.isfinite)
        bad_rows = data[~finite]
        if not bad_rows.empty:
            print("\n⚠️ Found non-finite CERT values in these rows:")
            print(bad_rows[["CERT", "source_file"]])
            print("\nThese rows will be dropped to avoid crash.\n")
        data = data[finite].copy()
        data["CERT"] = data["CERT"].astype(int).astype(str)
    else:
        data = pd.concat([pd.read_csv(filename) for filename in files])
        if event == "de_novo":
            data["CERT"] = data["CERT"].astype(str)
        else:
            data["CERT"] = data["CERT"].astype(float).astype(int).astype(str)

    date_column = config["date"]
    if date_column in data.columns:
        data[date_column] = pd.to_datetime(
            data[date_column], format="%Y-%m-%dT%H:%M:%S"
        ).dt.strftime("%Y%m%d")
        if event != "de_novo":
            data[date_column] = data[date_column].astype(int)
    return data


def build_lookups(event, config, events, quarters):
    # Preserve each stage's existing conversions and every duplicate event/window.
    quarters["Quarters"] = quarters["Quarters"].astype(str)
    boundary_columns = ["START_DATE"] + config["ends"]
    for column in boundary_columns:
        quarters[column] = quarters[column].astype(str if event == "de_novo" else int)

    event_dates = {}
    for cert, date in events[["CERT", config["date"]]].itertuples(index=False, name=None):
        event_dates.setdefault(cert, []).append(date)

    windows = {}
    for row in quarters[["Quarters"] + boundary_columns].itertuples(index=False, name=None):
        quarter = row[0] if event == "de_novo" else int(row[0])
        windows.setdefault(quarter, []).append(row[1:])
    return event_dates, windows


def flag_file(filename, event, config, event_dates, windows, output_directory):
    data = pd.read_csv(os.path.join(config["input_dir"], filename))
    if event == "de_novo":
        data["CERT"] = data["CERT"].astype(str)
        data["RCON9999"] = data["RCON9999"].astype(str)
    else:
        data["CERT"] = data["CERT"].astype(float).astype(int).astype(str)
        data["RCON9999"] = data["RCON9999"].astype(int)
    for flag in config["flags"]:
        data[flag] = 0

    for index, (cert, quarter) in zip(
        data.index, data[["CERT", "RCON9999"]].itertuples(index=False, name=None)
    ):
        for date in event_dates.get(cert, ()):
            for bounds in windows.get(quarter, ()):
                if pd.notna(date):
                    for flag, end_date in zip(config["flags"], bounds[1:]):
                        if bounds[0] <= date <= end_date:
                            data.at[index, flag] = 1
                    if event == "de_novo" and bounds[0] <= date <= bounds[1]:
                        break

    output_filename = re.sub(
        config["filename_pattern"], config["filename_replacement"], os.path.basename(filename)
    )
    output_path = os.path.join(output_directory, output_filename)
    data.to_csv(output_path, index=False)
    print(f"Processed {filename} and saved to {output_path}.")
    return output_path


def run_event(event, args):
    config = EVENTS[event].copy()
    if args.input_dir is not None:
        config["input_dir"] = args.input_dir
    elif event != "de_novo":
        upstream = "DE NOVO" if event == "failures" else "Failures"
        config["input_dir"] = os.path.join(args.material_dir, upstream, "Call Reports")
    output_directory = args.output_dir or os.path.join(
        args.material_dir, config["folder"], "Call Reports"
    )
    os.makedirs(output_directory, exist_ok=True)
    events = load_events(event, config, args.material_dir)
    quarters = pd.read_csv(args.quarter_map or os.path.join(args.material_dir, config["quarters"]))
    event_dates, windows = build_lookups(event, config, events, quarters)
    files = [name for name in os.listdir(config["input_dir"])
             if name.endswith(".csv") and (event != "failures" or "DE NOVO_" in name)]
    if not files:
        print(f"No CSV files found in {config['input_dir']}.")
    processed = [flag_file(name, event, config, event_dates, windows, output_directory)
                 for name in files]
    print(f"Processed files: {processed}")


def parse_args(argv=None, default_events=None):
    parser = argparse.ArgumentParser(
        description="Flag selected material events in de novo → failures → mergers order.",
        epilog="A selected stage reads the same upstream files as its original script."
    )
    parser.add_argument("--events", nargs="+", choices=list(EVENTS),
                        default=list(EVENTS) if default_events is None else default_events)
    parser.add_argument("--material-dir", type=Path, default=Path(paths.MAT_DIR))
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--quarter-map", type=Path)
    args = parser.parse_args(argv)
    if len(set(args.events)) != 1 and any(
        value is not None for value in (args.input_dir, args.output_dir, args.quarter_map)
    ):
        parser.error("--input-dir, --output-dir and --quarter-map require one selected event")
    return args


def run_events(args):
    for event in EVENTS:
        if event in args.events:
            run_event(event, args)
    return 0


def main(argv=None):
    return run_events(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
