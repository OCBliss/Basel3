import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
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
CALL_DIR = os.path.join(ROOT_DIR, "Call Report")
distributed_directory = os.path.join(CALL_DIR, "CSV/Distributed_Lag/RAW")
cleaned_directory = os.path.join(CALL_DIR, "CSV/Distributed_Lag/Cleaned")

# Ensure the output directory exists
os.makedirs(cleaned_directory, exist_ok=True)

def batch_process_files(input_directory, output_directory):
    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)
    
    # Iterate through all files in the input directory
    for filename in os.listdir(input_directory):
        if filename.endswith(".csv"):
            input_file_path = os.path.join(input_directory, filename)
            
            # Load the CSV file into a DataFrame
            df = pd.read_csv(input_file_path)
            
            # Identify rows where the first column is non-empty
            first_col = df.iloc[:, 0]  # First column
            rows_to_update = first_col.notna() & first_col.astype(str).str.strip().astype(bool)
            
            # Replace empty cells with 0 only in those rows
            df.loc[rows_to_update] = df.loc[rows_to_update].fillna(0)
            
            # Save the modified DataFrame to the output directory
            output_file_path = os.path.join(output_directory, filename)
            df.to_csv(output_file_path, index=False)
            print(f"Processed file saved: {output_file_path}")

# Run the batch processing function
batch_process_files(distributed_directory, cleaned_directory)
