import requests
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
DYNAMIC_DIR = paths.DYNAMIC_DIR
MAT_DIR = paths.MAT_DIR

# ==============================
# PROCESSING FOR FAILURES
# ==============================

# --- Define Processing and Output Directories for Failures ---
process_failures = os.path.join(MAT_DIR, "Mergers", "Call Reports")
output_failures = os.path.join(MAT_DIR, "Failures", "Horizons", "Basel III T+3")
os.makedirs(output_failures, exist_ok=True)

# --- Filter CSV Files in process_directory (Failures) ---
csv_files = [file for file in os.listdir(process_failures) if file.endswith('.csv')]

if not csv_files:
    print(f"No CSV files found in {process_failures} for Failures.")
else:
    processed_failures = []
    for file in csv_files:
        input_file_path = os.path.join(process_failures, file)
        data = pd.read_csv(input_file_path)
        
        # Keep only the rows with a '1' value in the header FAILURE_T3.
        data = data[data['FAILURE_T3'] == 1]
        
        # Save the processed file to the output directory (keeping the same filename)
        if file.startswith("Mergers_"):
            new_file = file.replace("Mergers_", "Failures_", 1)
        else:
            new_file = f"Failures_{new_file}"
        output_file_path = os.path.join(output_failures, new_file)
        data.to_csv(output_file_path, index=False)
        processed_failures.append(output_file_path)
        print(f"Processed {file} for Failures and saved to {output_file_path}.")

    # Print a summary of processed files for Failures
    print(f"Processed Failures files: {processed_failures}")

# ==============================
# PROCESSING FOR MERGERS
# ==============================

# --- Define Processing and Output Directories for Mergers ---
process_mergers = os.path.join(MAT_DIR, "Mergers", "Call Reports")
output_mergers = os.path.join(MAT_DIR, "Mergers", "Horizons", "Basel III T+3")
os.makedirs(output_mergers, exist_ok=True)

# --- Filter CSV Files in process_directory2 (Mergers) ---
csv_files2 = [file for file in os.listdir(process_mergers) if file.endswith('.csv')]

if not csv_files2:
    print(f"No CSV files found in {process_mergers} for Mergers.")
else:
    processed_mergers = []
    for file in csv_files2:
        input_file_path = os.path.join(process_mergers, file)
        data = pd.read_csv(input_file_path)
        
        # Keep only the rows with a '1' value in the header MERGER_T3.
        data = data[data['MERGER_T3'] == 1]
        
        # Save the processed file to the output directory (keeping the same filename)
        output_file_path = os.path.join(output_mergers, file)
        data.to_csv(output_file_path, index=False)
        processed_mergers.append(output_file_path)
        print(f"Processed {file} for Mergers and saved to {output_file_path}.")

    # Print a summary of processed files for Mergers
    print(f"Processed Mergers files: {processed_mergers}")

   # ==============================
# PROCESSING FOR SURVIVORS
# ==============================

# --- Define Processing and Output Directories for Survivors ---
process_survivors = os.path.join(MAT_DIR, "Mergers", "Call Reports")
output_survivors = os.path.join(MAT_DIR, "Survivors", "Horizons", "Basel III T+3")
os.makedirs(output_survivors, exist_ok=True)

# --- Filter CSV Files in process_directory3 (Survivors) ---
csv_files3 = [file for file in os.listdir(process_survivors) if file.endswith('.csv')]

if not csv_files3:
    print(f"No CSV files found in {process_survivors} for Survivors.")
else:
    processed_survivors = []
    for file in csv_files3:
        input_file_path = os.path.join(process_survivors, file)
        data = pd.read_csv(input_file_path)
        
       # Convert FAILURE_T3 and MERGER_T3 to numeric in case they are strings.
        data['FAILURE_T3'] = pd.to_numeric(data['FAILURE_T3'], errors='coerce')
        data['MERGER_T3'] = pd.to_numeric(data['MERGER_T3'], errors='coerce')
        
        # Define a drop condition: any row where FAILURE_T3 == 1 OR MERGER_T3 == 1 should be removed.
        drop_condition = (data['FAILURE_T3'] == 1) | (data['MERGER_T3'] == 1)
        data = data[~drop_condition]
        
        # Save the processed file to the output directory (keeping the same filename)
        if file.startswith("Mergers_"):
            new_file = file.replace("Mergers_", "Survivors_", 1)
        else:
            new_file = f"Failures_{new_file}"
        output_file_path = os.path.join(output_survivors, new_file)
        data.to_csv(output_file_path, index=False)
        processed_survivors.append(output_file_path)
        print(f"Processed {file} for Survivors and saved to {output_file_path}.")

    # Print a summary of processed files for Survivors
    print(f"Processed Survivors files: {processed_survivors}")
