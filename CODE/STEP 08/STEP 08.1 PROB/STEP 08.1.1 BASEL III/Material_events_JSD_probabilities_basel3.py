import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import importlib.util
import pandas as pd
import numpy as np
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
MERG_JSD_DIR = os.path.join(ROOT_DIR, "Material Events", "Mergers", "JS Divergence")
FAIL_JSD_DIR = os.path.join(ROOT_DIR, "Material Events", "Failures", "JS Divergence")
SURV_JSD_DIR = os.path.join(ROOT_DIR, "Material Events", "Survivors", "JS Divergence")

# -----------------------------
# Helper Function to Filter & Concatenate
# -----------------------------
def filter_and_concatenate(process_dir, output_dir, output_filename, label):
    """Reads CSV files from process_dir, filters by valid_dates (comparing last 8 chars in filename),
    then concatenates and writes to output_dir with output_filename."""
    # Step 3: Create the binned_path directory if it does not exist
    os.makedirs(output_dir, exist_ok=True)

    # Step 4: Process files in the dynamically located directory
    files_in_gamma_path = sorted([f for f in os.listdir(process_dir) if f.endswith('.csv')])
    if not files_in_gamma_path:
        raise FileNotFoundError(f"No CSV files found in the directory {process_dir}.")

    # Step 5: Process each file in the binned directory
    for file_name in files_in_gamma_path:
        file_path = os.path.join(process_dir, file_name)
        print(f"Processing file: {file_name}")
        
        # Load the data
        binned_data_basel3 = pd.read_csv(file_path)
        
        # Exclude the 'Bin' column for calculations
        columns_to_process = [col for col in binned_data_basel3.columns if col != 'Bin']
        
        # Create a new DataFrame for probabilities
        probabilities = binned_data_basel3[['Bin']].copy()
        
        # Calculate probabilities for each column
        for column in columns_to_process:
            total = binned_data_basel3[column].sum()
            if total == 0:
                print(f"Column {column} in file {file_name} has a total of 0. Skipping.")
                probabilities[column] = 0
            else:
                probabilities[column] = binned_data_basel3[column] / total
        
        # Save the probabilities to a new CSV file
        gamma_file_path = os.path.join(output_dir, f"probabilities_{file_name}")
        probabilities.to_csv(gamma_file_path, index=False)
        
        print(f"Probabilities saved to {output_dir}")

# -----------------------------
# Now we define each input CSV path (or directory) and its output directory.

# -----------------------------
# 1) Mergers
# -----------------------------
process_mergers_t1 = os.path.join(MERG_JSD_DIR, "Basel III T+1", "Binned")
output_mergers_t1  = os.path.join(MERG_JSD_DIR, "Basel III T+1", "Probabilities")
filter_and_concatenate(
    process_dir     = process_mergers_t1,
    output_dir      = output_mergers_t1,
    output_filename = "Peer_Group_Mergers_Basel3_binned.csv",
    label           = "Mergers_t1"
)

process_mergers_t2 = os.path.join(MERG_JSD_DIR, "Basel III T+2", "Binned")
output_mergers_t2  = os.path.join(MERG_JSD_DIR, "Basel III T+2", "Probabilities")
filter_and_concatenate(
    process_dir     = process_mergers_t2,
    output_dir      = output_mergers_t2,
    output_filename = "Peer_Group_Mergers_Basel3_binned.csv",
    label           = "Mergers_t2"
)

process_mergers_t3 = os.path.join(MERG_JSD_DIR, "Basel III T+3", "Binned")
output_mergers_t3  = os.path.join(MERG_JSD_DIR, "Basel III T+3", "Probabilities")
filter_and_concatenate(
    process_dir     = process_mergers_t3,
    output_dir      = output_mergers_t3,
    output_filename = "Peer_Group_Mergers_Basel3_binned.csv",
    label           = "Mergers_t3"
)

process_mergers_t4 = os.path.join(MERG_JSD_DIR, "Basel III T+4", "Binned")
output_mergers_t4  = os.path.join(MERG_JSD_DIR, "Basel III T+4", "Probabilities")
filter_and_concatenate(
    process_dir     = process_mergers_t4,
    output_dir      = output_mergers_t4,
    output_filename = "Peer_Group_Mergers_Basel3_binned.csv",
    label           = "Mergers_t4"
)

# -----------------------------
# 2) Failures
# -----------------------------
process_failures_t1 = os.path.join(FAIL_JSD_DIR, "Basel III T+1", "Binned")
output_failures_t1  = os.path.join(FAIL_JSD_DIR, "Basel III T+1", "Probabilities")
filter_and_concatenate(
    process_dir     = process_failures_t1,
    output_dir      = output_failures_t1,
    output_filename = "Peer_Group_Failures_Basel3_binned.csv",
    label           = "Failures_t1"
)

process_failures_t2 = os.path.join(FAIL_JSD_DIR, "Basel III T+2", "Binned")
output_failures_t2  = os.path.join(FAIL_JSD_DIR, "Basel III T+2", "Probabilities")
filter_and_concatenate(
    process_dir     = process_failures_t2,
    output_dir      = output_failures_t2,
    output_filename = "Peer_Group_Failures_Basel3_binned.csv",
    label           = "Failures_t2"
)

process_failures_t3 = os.path.join(FAIL_JSD_DIR, "Basel III T+3", "Binned")
output_failures_t3  = os.path.join(FAIL_JSD_DIR, "Basel III T+3", "Probabilities")
filter_and_concatenate(
    process_dir     = process_failures_t3,
    output_dir      = output_failures_t3,
    output_filename = "Peer_Group_Failures_Basel3_binned.csv",
    label           = "Failures_t3"
)

process_failures_t4 = os.path.join(FAIL_JSD_DIR, "Basel III T+4", "Binned")
output_failures_t4  = os.path.join(FAIL_JSD_DIR, "Basel III T+4", "Probabilities")
filter_and_concatenate(
    process_dir     = process_failures_t4,
    output_dir      = output_failures_t4,
    output_filename = "Peer_Group_Failures_Basel3_binned.csv",
    label           = "Failures_t4"
)

# -----------------------------
# 3) Survivors
# -----------------------------
process_survivors_t1 = os.path.join(SURV_JSD_DIR, "Basel III T+1", "Binned")
output_survivors_t1  = os.path.join(SURV_JSD_DIR, "Basel III T+1", "Probabilities")
filter_and_concatenate(
    process_dir     = process_survivors_t1,
    output_dir      = output_survivors_t1,
    output_filename = "Peer_Group_Survivors_Basel3_binned.csv",
    label           = "Survivors_t1"
)

process_survivors_t2 = os.path.join(SURV_JSD_DIR, "Basel III T+2", "Binned")
output_survivors_t2  = os.path.join(SURV_JSD_DIR, "Basel III T+2", "Probabilities")
filter_and_concatenate(
    process_dir     = process_survivors_t2,
    output_dir      = output_survivors_t2,
    output_filename = "Peer_Group_Survivors_Basel3_binned.csv",
    label           = "Survivors_t2"
)

process_survivors_t3 = os.path.join(SURV_JSD_DIR, "Basel III T+3", "Binned")
output_survivors_t3  = os.path.join(SURV_JSD_DIR, "Basel III T+3", "Probabilities")
filter_and_concatenate(
    process_dir     = process_survivors_t3,
    output_dir      = output_survivors_t3,
    output_filename = "Peer_Group_Survivors_Basel3_binned.csv",
    label           = "Survivors_t3"
)

process_survivors_t4 = os.path.join(SURV_JSD_DIR, "Basel III T+4", "Binned")
output_survivors_t4  = os.path.join(SURV_JSD_DIR, "Basel III T+4", "Probabilities")
filter_and_concatenate(
    process_dir     = process_survivors_t4,
    output_dir      = output_survivors_t4,
    output_filename = "Peer_Group_Survivors_Basel3_binned.csv",
    label           = "Survivors_t4"
)
