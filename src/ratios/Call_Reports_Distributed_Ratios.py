import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import csv
# import importlib.util

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
CALL_DIR = paths.CALL_DIR

interleaved_directory = os.path.join(CALL_DIR, "CSV", "Interleaved")
distributed_directory = os.path.join(CALL_DIR, "CSV", "Distributed_lag", "RAW")
quarters_file = os.path.join(CALL_DIR, "CSV/quarters.csv")

# Ensure the output directory exists
os.makedirs(distributed_directory, exist_ok=True)

# Load the quarters file
quarters_df = pd.read_csv(quarters_file)
quarters_df = quarters_df.iloc[:, 0].astype(str)
quarters_df = quarters_df[quarters_df.str.match(r'^\d{8}$')]
quarters_df = quarters_df.reset_index(drop=True)

# Process each row in the quarters file
for i in range(len(quarters_df) - 3):
    # Current quarter
    current_date = quarters_df.iloc[i]
    current_file = f'Cleaned_Call_Report_{current_date}.csv'
    current_path = os.path.join(interleaved_directory, current_file)

    # Load current file
    if not os.path.exists(current_path):
        continue

    current_df = pd.read_csv(current_path)

    # Get the three following quarters
    previous_dates = [quarters_df.iloc[i + j + 1] for j in range(3)]

    # Append previous quarters
    appended_df = current_df.copy()
    for prev_date in previous_dates:
        prev_file = f'Cleaned_Call_Report_{prev_date}.csv'
        prev_path = os.path.join(interleaved_directory, prev_file)

        if os.path.exists(prev_path):
            prev_df = pd.read_csv(prev_path)
            appended_df = appended_df.merge(prev_df, on='CERT', how='left', suffixes=('', f'_{prev_date}'))
        pass
    # Save the appended DataFrame
    output_file = os.path.join(distributed_directory, f'Distributed_{current_file}')
    appended_df.to_csv(output_file, index=False)
    print(f"Processed and saved: {output_file}")
