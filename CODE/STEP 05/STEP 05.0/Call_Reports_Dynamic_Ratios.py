import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import numpy as np
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
processed_directory = os.path.join(CALL_DIR, "CSV/Dynamic_Lag/RAW")
cleaned_directory = os.path.join(CALL_DIR, "CSV/Distributed_Lag/Cleaned")
quarters_file = os.path.join(CALL_DIR, "CSV/quarters.csv")

os.makedirs(processed_directory, exist_ok=True)

# Load the quarters file as a list of quarters
quarters_df = pd.read_csv(quarters_file)
quarters_list = quarters_df['Quarters'].astype(str).tolist()  # Convert to string for consistency

# Function to extract relevant quarters based on the current file
def get_quarters(filename):
    # Extract the current quarter from the filename
    current_quarter = filename.split('_')[-1].split('.')[0]
    if current_quarter not in quarters_list:
        raise ValueError(f"Quarter {current_quarter} not found in quarters file.")
    
    # Find index of the current quarter in the quarters list
    current_index = quarters_list.index(current_quarter)
    
    # Ensure there are three rows below for previous quarters
    if current_index + 3 >= len(quarters_list):
        raise ValueError(f"Not enough previous quarters for {current_quarter}.")
    
    # Get the three subsequent rows below as the previous quarters
    prev_quarters = quarters_list[current_index + 1:current_index + 4]
    return current_quarter, prev_quarters

# Function to process a single file
def process_file(filepath):
    filename = os.path.basename(filepath)
    current_quarter, prev_quarters = get_quarters(filename)

    # Load data from the file
    df = pd.read_csv(filepath)
    
    # Extract columns without date suffixes
    base_columns = [col for col in df.columns if '_' not in col]
    
    # Initialize a dictionary to store calculated columns
    # output_dict = {'IDRSSD': df['IDRSSD']}
    output_dict = {'CERT': df['CERT']}
    
    # Calculate columns for each variable
    for col in base_columns:
        # Current quarter (_q0)
        output_dict[f"{col}_q0"] = df[col]
        
        # Previous quarter (_q0q1)
        if f"{col}_{prev_quarters[0]}" in df.columns:
            prev_col = df[f"{col}_{prev_quarters[0]}"]
            output_dict[f"{col}_q0q1"] = np.where(prev_col != 0, df[col] / prev_col - 1, 0)
        
        # Two quarters ago (_q0q2)
        if f"{col}_{prev_quarters[1]}" in df.columns:
            prev_col = df[f"{col}_{prev_quarters[1]}"]
            output_dict[f"{col}_q0q2"] = np.where(prev_col != 0, df[col] / prev_col - 1, 0)
        
        # Three quarters ago (_q0q3)
        if f"{col}_{prev_quarters[2]}" in df.columns:
            prev_col = df[f"{col}_{prev_quarters[2]}"]
            output_dict[f"{col}_q0q3"] = np.where(prev_col != 0, df[col] / prev_col - 1, 0)
    
    # Create a DataFrame in the required order
    column_order = (
        [f"{col}_q0" for col in base_columns] +
        [f"{col}_q0q1" for col in base_columns if f"{col}_q0q1" in output_dict] +
        [f"{col}_q0q2" for col in base_columns if f"{col}_q0q2" in output_dict] +
        [f"{col}_q0q3" for col in base_columns if f"{col}_q0q3" in output_dict]
    )
    
    # Ensure IDRSSD is first
    # result_df = pd.DataFrame(output_dict)[['IDRSSD'] + column_order]
    result_df = pd.DataFrame(output_dict)[['CERT'] + column_order]
    
    # Save the processed DataFrame
    output_path = os.path.join(processed_directory, f"Dynamic_{filename}")
    result_df.to_csv(output_path, index=False)
    print(f"Processed and saved: {output_path}")

# Batch process all files in the directory
for file in os.listdir(cleaned_directory):
    if file.endswith('.csv') and file.startswith('Distributed_Cleaned_Call_Report'):
        file_path = os.path.join(cleaned_directory, file)
        process_file(file_path)
