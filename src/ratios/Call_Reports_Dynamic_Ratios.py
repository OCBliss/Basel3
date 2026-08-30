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
CALL_DIR = paths.CALL_DIR

# Step 4: Use the Dynamically Determined ROOT_DIR
processed_directory = os.path.join(paths.DYNAMIC_DIR, "RAW")
cleaned_directory = os.path.join(paths.DISTRIBUTED_DIR, "Cleaned")
quarters_file = os.path.join(paths.CSV_DIR, "quarters.csv")

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
        output_dict[f"{col}_q0"] = pd.to_numeric(df[col], errors='coerce')
        
        if f"{col}_{prev_quarters[0]}" in df.columns:
            prev = pd.to_numeric(df[f"{col}_{prev_quarters[0]}"], errors='coerce')
            curr = output_dict[f"{col}_q0"]
            output_dict[f"{col}_q0q1"] = np.where(prev != 0, curr / prev - 1, 0)
        
        if f"{col}_{prev_quarters[1]}" in df.columns:
            prev = pd.to_numeric(df[f"{col}_{prev_quarters[1]}"], errors='coerce')
            curr = output_dict[f"{col}_q0"]
            output_dict[f"{col}_q0q2"] = np.where(prev != 0, curr / prev - 1, 0)

        if f"{col}_{prev_quarters[2]}" in df.columns:
            prev = pd.to_numeric(df[f"{col}_{prev_quarters[2]}"], errors='coerce')
            curr = output_dict[f"{col}_q0"]
            output_dict[f"{col}_q0q3"] = np.where(prev != 0, curr / prev - 1, 0)
    
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
    if filename.startswith("Distributed_Cleaned_"):
        clean_name = filename[len("Distributed_Cleaned_"):]
    else:
        clean_name = filename

    output_filename = f"Dynamic_Raw_{clean_name}"
    output_path = os.path.join(processed_directory, output_filename)
    result_df.to_csv(output_path, index=False)
    print(f"Processed and saved: {output_path}")

# Batch process all files in the directory
for file in os.listdir(cleaned_directory):
    if file.endswith('.csv') and file.startswith('Distributed_Cleaned_Call_Report'):
        file_path = os.path.join(cleaned_directory, file)
        process_file(file_path)
