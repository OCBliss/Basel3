import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
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
interleaved_directory = os.path.join(ROOT_DIR, "Call Report/CSV/Interleaved")
distributed_directory = os.path.join(ROOT_DIR, "Call Report/CSV/Distributed_Lag/RAW")
quarters_file = os.path.join(ROOT_DIR, "Call Report/CSV/quarters.csv")

# Ensure the output directory exists
os.makedirs(distributed_directory, exist_ok=True)

# Load the quarters file
quarters_df = pd.read_csv(quarters_file, header=None)

# Process each row in the quarters file
for i in range(len(quarters_df) - 3):
    # Current quarter
    current_date = str(quarters_df.iloc[i, 0])
    current_file = f'Cleaned_Call_Report_{current_date}.csv'
    current_path = os.path.join(interleaved_directory, current_file)

    # Load current file
    if os.path.exists(current_path):
        current_df = pd.read_csv(current_path)
    else:
        print(f"File not found: {current_file}")
        continue

    # Get the three following quarters
    previous_dates = [str(quarters_df.iloc[i + j + 1, 0]) for j in range(3)]

    # Append previous quarters
    appended_df = current_df.copy()
    for prev_date in previous_dates:
        prev_file = f'Cleaned_Call_Report_{prev_date}.csv'
        prev_path = os.path.join(interleaved_directory, prev_file)

        if os.path.exists(prev_path):
            prev_df = pd.read_csv(prev_path)
            appended_df = appended_df.merge(prev_df, on='CERT', how='left', suffixes=('', f'_{prev_date}'))
        else:
            print(f"File for previous quarter {prev_date} not found: {prev_file}")

    # Save the appended DataFrame
    output_file = os.path.join(distributed_directory, f'Distributed_{current_file}')
    appended_df.to_csv(output_file, index=False)
    print(f"Processed and saved: {output_file}")
