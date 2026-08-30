import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import numpy as np
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
DYNAMIC_DIR = paths.DYNAMIC_DIR # see Basel3_Global_Filepath.py
CALL_DIR = paths.CALL_DIR # see Basel3_Global_Filepath.py

input_directory = os.path.join(DYNAMIC_DIR, "RAW")
output_directory = os.path.join(DYNAMIC_DIR, "Cleaned")
quarters_file = os.path.join(paths.CSV_DIR, "quarters.csv")

# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)

# List of columns to remove
columns_to_remove = [
    "IDRSSD_q0", "IDRSSD_q0q1", "IDRSSD_q0q2", "IDRSSD_q0q3",
    "RCON9999_q0q1", "RCON9999_q0q2", "RCON9999_q0q3", "CERT_q0"
]

# Columns to rename
columns_to_rename = {
    # "CERT_q0": "CERT",
    "RCON9999_q0": "RCON9999"
}

# Prefix for new filenames
new_prefix = "Dynamic_Cleaned_"
old_prefix = "Dynamic_Raw_"

# Process each file in the input directory
csv_files = [file for file in os.listdir(input_directory) if file.endswith('.csv')]

if not csv_files:
    print(f"No CSV files found in {input_directory}.")
else:
    for file in csv_files:
        input_file_path = os.path.join(input_directory, file)

        # Rename the output file
        if file.startswith(old_prefix):
            new_filename = new_prefix + file[len(old_prefix):]
        else:
            new_filename = new_prefix + file

        output_file_path = os.path.join(output_directory, new_filename)

        try:
            # Load the CSV file
            data = pd.read_csv(input_file_path)

            # Remove specified columns if they exist
            data.drop(columns=[col for col in columns_to_remove if col in data.columns], inplace=True)

            # Rename the specified columns if they exist
            for old_name, new_name in columns_to_rename.items():
                if old_name in data.columns:
                    data.rename(columns={old_name: new_name}, inplace=True)

            # Save the cleaned file
            data.to_csv(output_file_path, index=False)
            print(f"Processed {file} and saved as {new_filename} in {output_directory}.")

        except Exception as e:
            print(f"Error processing {file}: {e}")
