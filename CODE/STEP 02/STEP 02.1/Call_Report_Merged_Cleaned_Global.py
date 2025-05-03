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
schedules_directory = os.path.join(ROOT_DIR, "Call Report/CSV/Schedules")
output_directory = os.path.join(ROOT_DIR, "Call Report/CSV/Cleaned")

# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)

# Function to merge files and skip duplicate columns
def merge_files_sequentially(base_file_path, files_to_append, output_path):
    """
    Sequentially append columns from a list of files to a base file.
    Parameters:
        base_file_path (str): Path to the base file.
        files_to_append (list): List of file paths to append to the base file.
        output_path (str): Path to save the final merged output file.
    """
    base_df = pd.read_csv(base_file_path, low_memory=False)
    seen_columns = set(base_df.columns)

    for file_path in files_to_append:
        if os.path.exists(file_path):
            append_df = pd.read_csv(file_path, low_memory=False)
            columns_to_add = [col for col in append_df.columns if col not in seen_columns or col == 'IDRSSD']
            append_df = append_df[columns_to_add]
            base_df = pd.merge(base_df, append_df, on='IDRSSD', how='left')
            seen_columns.update(columns_to_add)

    base_df.to_csv(output_path, index=False)
    print(f"Processed and saved: {output_path}")

# Helper function to determine files to append
def determine_files_to_append(input_directory, subfolder):
    folder_date = int(subfolder)  # Convert folder name to an integer for comparison
    mmddyyyy = convert_to_mmddyyyy(subfolder)

    if folder_date >= 20170331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRI {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(1 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(2 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(3 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(4 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    elif 20150331 <= folder_date < 20170331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRI {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(1 of 3).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(2 of 3).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(3 of 3).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    elif 20140331 <= folder_date < 20150331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRIA {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRIB {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    elif 20090331 <= folder_date < 20140331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCR {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCR {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    else:
        files_to_append = []  # Default to an empty list if the folder_date doesn't match any range

    return files_to_append

# Helper function to convert YYYYMMDD to MMDDYYYY
def convert_to_mmddyyyy(yyyymmdd):
    return f"{yyyymmdd[4:6]}{yyyymmdd[6:]}{yyyymmdd[:4]}"

# Process subfolders
for subfolder in sorted(os.listdir(schedules_directory)):
    subfolder_path = os.path.join(schedules_directory, subfolder)
    if os.path.isdir(subfolder_path):
        try:
            input_directory = subfolder_path
            base_file_name = f"FFIEC CDR Call Schedule ENT {convert_to_mmddyyyy(subfolder)}.csv"
            base_file_path = os.path.join(input_directory, base_file_name)
            output_file_name = f"Cleaned_Call_Report_{subfolder}.csv"
            output_file_path = os.path.join(output_directory, output_file_name)
            files_to_append = determine_files_to_append(input_directory, subfolder)

            if os.path.exists(base_file_path):
                merge_files_sequentially(base_file_path, files_to_append, output_file_path)
            else:
                print(f"Base file not found: {base_file_path}")
        except Exception as e:
            print(f"Error processing folder {subfolder}: {e}")