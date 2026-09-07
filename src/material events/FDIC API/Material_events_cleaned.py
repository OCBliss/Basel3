import argparse
import requests
import pandas as pd
import os
import sys
sys.stdout.reconfigure(line_buffering=True)
import importlib.util
import numpy as np

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "src":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'src' directory.")
        current_dir = parent_dir
    return current_dir

# Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Step 4: Use the Dynamically Determined ROOT_DIR
ROOT_DIR = paths.BASEL3_ROOT

MAT_DIR = paths.MAT_DIR
CSV_DIR = paths.CSV_DIR
quarters_file = os.path.join(CSV_DIR, "quarters.csv")

# Define Material Events base directory
MAT_DIR = paths.MAT_DIR

EVENT_FOLDERS = {
    "de_novo": ("DE NOVO", True),
    "failures": ("Failures", False),
    "mergers": ("Mergers", False),
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Clean FDIC material-event downloads.")
    parser.add_argument(
        "--events", nargs="+", choices=tuple(EVENT_FOLDERS),
        default=list(EVENT_FOLDERS), help="Event datasets to clean (default: all).",
    )
    parser.add_argument(
        "--material-dir", default=paths.MAT_DIR,
        help="Material Events directory (default: repository Material Events).",
    )
    return parser.parse_args(argv)


def build_folders(material_dir, events):
    return [
        {
            "input_folder": os.path.join(material_dir, EVENT_FOLDERS[event][0], "RAW"),
            "output_folder": os.path.join(material_dir, EVENT_FOLDERS[event][0], "Cleaned"),
            "use_cert": EVENT_FOLDERS[event][1],
        }
        for event in events
    ]


# The desired column order
desired_columns = [
    "CERT", "ACQ_CERT", "ACQ_CHARTAGENT", "ACQ_CLASS", "ACQ_INSAGENT1", "ACQ_INSTNAME",
    "ACQ_ORG_EFF_DTE", "ACQ_REGAGENT", "CHANGECODE", "CHANGECODE_DESC", "CLASS",
    "EFFDATE", "ESTDATE", "ESTYEAR", "FDICREGION", "FDICREGION_DESC", "FRM_CLASS",
    "FRM_INSAGENT1", "FRM_REGAGENT", "ID", "INSAGENT1", "OUT_CHARTAGENT", "OUT_CLASS",
    "OUT_FDICREGION", "OUT_FDICREGION_DESC", "OUT_INSAGENT1", "NEW_CHARTER_DENOVO_FLAG",
    "NEW_CHARTER_FLAG", "REGAGENT"
]

def main(argv=None):
    args = parse_args(argv)
    folders = build_folders(args.material_dir, args.events)

    # Process each folder
    for folder in folders:
        input_folder = folder["input_folder"]
        output_folder = folder["output_folder"]
        use_cert = folder["use_cert"]

        # Ensure the output folder exists
        os.makedirs(output_folder, exist_ok=True)

        # List all CSV files in the input folder
        csv_files = [file for file in os.listdir(input_folder) if file.endswith('.csv')]

        if not csv_files:
            print(f"No CSV files found in {input_folder}.")
            continue

        for file in csv_files:
            input_file_path = os.path.join(input_folder, file)
            output_file_path = os.path.join(output_folder, file)

            try:
                # Load the CSV file with error handling
                data = pd.read_csv(input_file_path, on_bad_lines="warn")

                # For folders that use "OUT_CERT", rename to "CERT"
                if not use_cert and "OUT_CERT" in data.columns:
                    data.rename(columns={"OUT_CERT": "CERT"}, inplace=True)

                # Preserve the acquiring bank as the common CERT key.
                if not use_cert and "ACQ_CERT" in data.columns:
                    data.rename(columns={"ACQ_CERT": "CERT"}, inplace=True)

                # Ensure all desired columns exist, fill missing columns with blank values
                for column in desired_columns:
                    if column not in data.columns:
                        data[column] = ''

                # Reorder columns to match the desired order
                data = data[desired_columns]

                # Save the processed file to the output folder
                data.to_csv(output_file_path, index=False)
                print(f"Processed {file} and saved to {output_file_path}.", flush=True)

            except pd.errors.ParserError as e:
                print(f"ParserError while processing {input_file_path}: {e}", flush=True)
            except Exception as e:
                print(f"Unexpected error with {input_file_path}: {e}", flush=True)


if __name__ == "__main__":
    main()
