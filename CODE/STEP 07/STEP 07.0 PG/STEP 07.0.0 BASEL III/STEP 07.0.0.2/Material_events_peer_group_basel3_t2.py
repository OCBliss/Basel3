import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import importlib.util
import pandas as pd
import re

# --- Step 1: Find the CODE Directory ---
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))  # Start from the script's directory
    while current_dir and os.path.basename(current_dir) != "CODE":  # Traverse up until "CODE" is found
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Reached the root directory
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir  # CODE directory is located

# --- Step 2: Locate CODE and Add to sys.path ---
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)  # Ensure CODE directory is in the import path

# --- Step 3: Import Basel3_Global_Filepath Dynamically ---
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# --- Step 4: Use the Dynamically Determined ROOT_DIR ---
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)
CALL_DIR = os.path.join(ROOT_DIR, "Call Report")
MAT_DIR = os.path.join(ROOT_DIR, "Material Events")

# ==============================
# PROCESSING FOR FAILURES
# ==============================

# --- Define Processing and Output Directories for Failures ---
process_failures = os.path.join(MAT_DIR, "Mergers/Call Reports")
output_failures = os.path.join(MAT_DIR, "Failures/Peer Group Failures/Basel III T+2")
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
        
        # Keep only the rows with a '1' value in the header FAILURE_T2.
        data = data[data['FAILURE_T2'] == 1]
        
        # Save the processed file to the output directory (keeping the same filename)
        output_file_path = os.path.join(output_failures, file)
        data.to_csv(output_file_path, index=False)
        processed_failures.append(output_file_path)
        print(f"Processed {file} for Failures and saved to {output_file_path}.")

    # Print a summary of processed files for Failures
    print(f"Processed Failures files: {processed_failures}")

# ==============================
# PROCESSING FOR MERGERS
# ==============================

# --- Define Processing and Output Directories for Mergers ---
process_mergers = os.path.join(MAT_DIR, "Mergers/Call Reports")
output_mergers = os.path.join(MAT_DIR, "Mergers/Peer Group Mergers/Basel III T+2")
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
        
        # Keep only the rows with a '1' value in the header MERGER_T2.
        data = data[data['MERGER_T2'] == 1]
        
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
process_survivors = os.path.join(MAT_DIR, "Mergers/Call Reports")
output_survivors = os.path.join(MAT_DIR, "Survivors/Peer Group Survivors/Basel III T+2")
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
        
       # Convert FAILURE_T2 and MERGER_T2 to numeric in case they are strings.
        data['FAILURE_T2'] = pd.to_numeric(data['FAILURE_T2'], errors='coerce')
        data['MERGER_T2'] = pd.to_numeric(data['MERGER_T2'], errors='coerce')
        
        # Define a drop condition: any row where FAILURE_T2 == 1 OR MERGER_T2 == 1 should be removed.
        drop_condition = (data['FAILURE_T2'] == 1) | (data['MERGER_T2'] == 1)
        data = data[~drop_condition]
        
        # Save the processed file to the output directory (keeping the same filename)
        output_file_path = os.path.join(output_survivors, file)
        data.to_csv(output_file_path, index=False)
        processed_survivors.append(output_file_path)
        print(f"Processed {file} for Survivors and saved to {output_file_path}.")

    # Print a summary of processed files for Survivors
    print(f"Processed Survivors files: {processed_survivors}")
