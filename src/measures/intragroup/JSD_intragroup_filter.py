import requests
import argparse
import pandas as pd
import os
import sys
sys.stdout.reconfigure(line_buffering=True)
import numpy as np
import re

# Step 1: Locate CODE directory FIRST
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "src":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'src' directory.")
        current_dir = parent_dir
    return current_dir

CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# NOW import
import Basel3_Global_Filepath as paths

# Step 4: Use the Dynamically Determined ROOT_DIR
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)
MAT_DIR = paths.MAT_DIR

# ===============================
# PROCESSING FOR INTRAGROUP FILTER
# ===============================

JSD_DIR = os.path.join(MAT_DIR, "JSD")
IG_DIR = os.path.join(MAT_DIR, "IG")

# Function to process CSVs
def process_csvs(process_dir, output_dir, bins, threshold=0.3):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(process_dir):
        if any(filename.endswith(f"_{width}.csv") for width in bins):
            file_path = os.path.join(process_dir, filename)
            df = pd.read_csv(file_path)

            # Check first row beneath header
            first_row = df.iloc[0]
            columns_to_keep = [col for col in df.columns if pd.to_numeric(first_row[col], errors='coerce') >= threshold]

            cleaned_df = df[columns_to_keep]

            output_path = os.path.join(output_dir, filename)
            cleaned_df.to_csv(output_path, index=False)

            print(f"Processed: {filename} | Dropped: {len(df.columns) - len(columns_to_keep)} columns")

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Filter selected JSD horizons and bin specifications.")
    parser.add_argument("--horizons", type=int, choices=[1, 2, 3, 4], nargs="+", required=True)
    parser.add_argument("--bins", type=int, nargs="+", required=True)
    parser.add_argument("--material-dir", default=paths.MAT_DIR)
    parser.add_argument("--threshold", type=float, default=0.3)
    args = parser.parse_args(argv)
    if any(width <= 0 for width in args.bins):
        parser.error("--bins values must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    for horizon in dict.fromkeys(args.horizons):
        process_csvs(
            os.path.join(args.material_dir, "JSD", f"BASEL III T+{horizon}"),
            os.path.join(args.material_dir, "IG", f"BASEL III T+{horizon}"),
            args.bins,
            args.threshold,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
