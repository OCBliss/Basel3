import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import csv
import importlib.util

# Step 1: Function to Locate the CODE Directory Dynamically (Works from Any Depth)
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

CALL_DIR = os.path.join(ROOT_DIR, "Call Report")
INTERLEAVED_DIR = os.path.join(CALL_DIR, "CSV", "Interleaved")
CLEANED_DIR = os.path.join(CALL_DIR, "CSV", "Interleaved", "Cleaned")

# Ensure the output directory exists
os.makedirs(CLEANED_DIR, exist_ok=True)

for filename in os.listdir(INTERLEAVED_DIR):
    if filename.endswith('.csv'):
        file_path = os.path.join(INTERLEAVED_DIR, filename)
        df = pd.read_csv(file_path)

        # if 'RCRI-CET1-RWA+' in df.columns and 'RCRI-CET1-CCYB' in df.columns:
        if 'RCRI-CET1-RWA+' in df.columns and 'RCRI-CET1-THRES' in df.columns:
            # Clean and convert columns
            rwa_col = pd.to_numeric(df['RCRI-CET1-RWA+'], errors='coerce')

            # Remove % and convert to decimal
            ccyb_col = df['RCRI-CET1-THRES'].astype(str).str.replace('%', '', regex=False)
            ccyb_col = pd.to_numeric(ccyb_col, errors='coerce') / 100

            # Calculate and assign
            df['RCRI-CET1-CCYB+'] = rwa_col - ccyb_col
            df['RCRI-CET1-CCYB++'] = df['RCRI-CET1-CCYB+'] - 0.025

            df.drop(columns=['RCRI-CET1-THRES'], inplace=True)

            # Final cleanup of potential % residues in RWA+
            df['RCRI-CET1-RWA+'] = df['RCRI-CET1-RWA+'].astype(str).str.replace('%', '', regex=False)
            df['RCRI-CET1-RWA+'] = pd.to_numeric(df['RCRI-CET1-RWA+'], errors='coerce')
        else:
            print(f"Skipping {filename}: missing required columns.")

        output_path = os.path.join(CLEANED_DIR, filename)
        df.to_csv(output_path, index=False)
