import os
import pandas as pd
import numpy as np
import importlib.util

# Step 1: Locate 'Basel3_Global_Filepath.py'
def find_global_filepath():
    for root, _, files in os.walk(os.path.abspath(os.sep)):
        if "Basel3_Global_Filepath.py" in files:
            return os.path.join(root, "Basel3_Global_Filepath.py")
    raise FileNotFoundError("Could not locate 'Basel3_Global_Filepath.py' on the system.")

global_filepath_path = find_global_filepath()

# Step 2: Load 'Basel3_Global_Filepath.py' and extract paths
def load_global_filepath(filepath):
    spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
    global_filepath = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(global_filepath)
    return global_filepath

global_filepath = load_global_filepath(global_filepath_path)
ROOT_DIR = global_filepath.ROOT_DIR
RWA_DIR = os.path.join(ROOT_DIR, "RWA")
PRACT_DIR = os.path.join(RWA_DIR, "Practical")
RAW_DIR = os.path.join(RWA_DIR, "FRED")
CLEANED_DIR = os.path.join(PRACT_DIR, "Constant Maturity Treasury", "Cleaned")

# Step 3: Create the binned_path directory if it does not exist
os.makedirs(CLEANED_DIR, exist_ok=True)

# List of files in the order to be appended
file_list = ["DGS1.csv", "DGS3.csv", "DGS5.csv", "DGS10.csv", "DGS20.csv", "DGS30.csv"]

# Initialize the base DataFrame with the first file
base_file_path = os.path.join(RAW_DIR, file_list[0])
if not os.path.exists(base_file_path):
    raise FileNotFoundError(f"Base file {file_list[0]} does not exist in the directory.")

# Read the base file
base_data = pd.read_csv(base_file_path)

# Ensure 'observation_date' is treated as a key
if 'observation_date' not in base_data.columns:
    raise KeyError(f"Key column 'observation_date' not found in base file {file_list[0]}.")

# Set observation_date as the index for the base file
base_data.set_index('observation_date', inplace=True)

# Process and append remaining files
for file_name in file_list[1:]:
    file_path = os.path.join(RAW_DIR, file_name)
    if not os.path.exists(file_path):
        print(f"File {file_name} does not exist and will be skipped.")
        continue
    
    # Read the current file
    current_data = pd.read_csv(file_path)
    
    # Ensure 'observation_date' is treated as a key
    if 'observation_date' not in current_data.columns:
        print(f"Key column 'observation_date' not found in file {file_name}. Skipping.")
        continue
    
    # Set observation_date as the index for the current file
    current_data.set_index('observation_date', inplace=True)
    
    # Append (merge) the data horizontally
    base_data = base_data.join(current_data, how='outer', rsuffix=f"_{file_name.split('.')[0]}")
    print(f"Appended file: {file_name}")

# Reset index for final output
base_data.reset_index(inplace=True)

# Convert observation_date to datetime for proper sorting
base_data['observation_date'] = pd.to_datetime(base_data['observation_date'])

# Sort by observation_date in descending order
base_data.sort_values(by='observation_date', ascending=False, inplace=True)

# Fill missing values using the value from the cell below
base_data.fillna(method='bfill', inplace=True)

# Save the combined data to a new CSV file
output_file_path = os.path.join(CLEANED_DIR, "combined_fred_treasury_data.csv")
base_data.to_csv(output_file_path, index=False)

print(f"Combined data saved to {output_file_path}")
