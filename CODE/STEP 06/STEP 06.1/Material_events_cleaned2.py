import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import numpy as np
import csv
import importlib.util

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))  # Start from script's directory
    while current_dir and os.path.basename(current_dir) != "CODE":  # Traverse up until "CODE" is found
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Stop if we reach the root directory
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir  # Now 'CODE' directory is located

# Step 2: Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)  # Ensure CODE directory is in the import path

# Step 3: Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Step 4: Use the Dynamically Determined ROOT_DIR
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)
quarters_file = os.path.join(ROOT_DIR, "Call Report/CSV/quarters.csv")

# Define Material Events base directory
MAT_DIR = os.path.join(ROOT_DIR, "Material Events")

# Define folder structures for processing
folders = [
    {
        "input_folder": os.path.join(MAT_DIR, "DE NOVO/RAW/"),
        "output_folder": os.path.join(MAT_DIR, "DE NOVO/Cleaned/"),
        "use_cert": True  # Indicates this folder already uses "CERT"
    },
    {
        "input_folder": os.path.join(MAT_DIR, "Failures/RAW/"),
        "output_folder": os.path.join(MAT_DIR, "Failures/Cleaned/"),
        "use_cert": False  # Requires "OUT_CERT" to be renamed to "CERT"
    },
    {
        "input_folder": os.path.join(MAT_DIR, "Mergers/RAW/"),
        "output_folder": os.path.join(MAT_DIR, "Mergers/Cleaned/"),
        "use_cert": False  # Requires "OUT_CERT" to be renamed to "CERT"
    }
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
            data = pd.read_csv(input_file_path, error_bad_lines=False, warn_bad_lines=True)

            # For folders that use "OUT_CERT", rename to "CERT"
            if not use_cert and "OUT_CERT" in data.columns:
                data.rename(columns={"OUT_CERT": "CERT"}, inplace=True)

            # Ensure all desired columns exist, fill missing columns with blank values
            for column in desired_columns:
                if column not in data.columns:
                    data[column] = ''

            # Reorder columns to match the desired order
            data = data[desired_columns]

            # Save the processed file to the output folder
            data.to_csv(output_file_path, index=False)
            print(f"Processed {file} and saved to {output_file_path}.")

        except pd.errors.ParserError as e:
            print(f"ParserError while processing {input_file_path}: {e}")
        except Exception as e:
            print(f"Unexpected error with {input_file_path}: {e}")
