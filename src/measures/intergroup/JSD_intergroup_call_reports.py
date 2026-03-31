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

# ===============================
# PROCESSING FOR INTERGROUP FILTER
# ===============================

# Define directories based on the global file paths
JSD_DIR  = os.path.join(MAT_DIR, "JSD")
IG_DIR   = os.path.join(MAT_DIR, "IG")
survivors_dir = os.path.join(MAT_DIR, "Survivors", "Horizons")
mergers_dir   = os.path.join(MAT_DIR, "Mergers", "Horizons")
failures_dir  = os.path.join(MAT_DIR, "Failures", "Horizons")

# Define the output directory and create it if it doesn't exist
output_dir = os.path.join(IG_DIR, "Call Reports", "RAW")
os.makedirs(output_dir, exist_ok=True)

# Define the time periods we want to process
time_periods = ["t1", "t2", "t3", "t4"]

def build_filename(group, time_period):
    """
    Build the expected filename based on the group (Survivors, Mergers, or Failures)
    and time period. For example, for group 'Survivors' and time period 't1',
    the file will be: Peer_Group_Survivors_Basel3_t1.csv
    """
    return f"Peer_Group_{group}_Basel3_{time_period}.csv"

# Process each time period
for time_period in time_periods:
    dataframes = []
    
    # Survivors
    survivors_file = os.path.join(survivors_dir, build_filename("Survivors", time_period))
    if os.path.exists(survivors_file):
        df = pd.read_csv(survivors_file)
        dataframes.append(df)
    else:
        print(f"File not found: {survivors_file}")
    
    # Mergers
    mergers_file = os.path.join(mergers_dir, build_filename("Mergers", time_period))
    if os.path.exists(mergers_file):
        df = pd.read_csv(mergers_file)
        dataframes.append(df)
    else:
        print(f"File not found: {mergers_file}")
    
    # Failures
    failures_file = os.path.join(failures_dir, build_filename("Failures", time_period))
    if os.path.exists(failures_file):
        df = pd.read_csv(failures_file)
        dataframes.append(df)
    else:
        print(f"File not found: {failures_file}")
    
    # If we found any files for this time period, concatenate them
    if dataframes:
        combined_df = pd.concat(dataframes, ignore_index=True)
        output_file = os.path.join(output_dir, f"Call_Report_Basel3_{time_period}.csv")
        combined_df.to_csv(output_file, index=False)
        print(f"Created concatenated file: {output_file}")
    else:
        print(f"No files found for time period {time_period}.")
