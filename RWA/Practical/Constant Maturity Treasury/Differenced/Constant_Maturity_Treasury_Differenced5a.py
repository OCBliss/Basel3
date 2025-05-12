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
CLEANED_DIR = os.path.join(PRACT_DIR, "Constant Maturity Treasury", "Cleaned")
TRANSFORM_DIR = os.path.join(PRACT_DIR, "Constant Maturity Treasury", "Differenced")

# Step 3: Process files in CLEANED_DIR and save to TRANSFORM_DIR
def process_cleaned_files(cleaned_dir, transform_dir, offset=252, threshold=0.0):
    if not os.path.exists(transform_dir):
        os.makedirs(transform_dir)
    
    for file in os.listdir(cleaned_dir):
        if file.endswith(".csv"):
            file_path = os.path.join(cleaned_dir, file)
            output_path = os.path.join(transform_dir, f"differenced_{file}")
            
            df = pd.read_csv(file_path)

            if df.shape[1] < 2 or df.shape[0] <= offset:
                print(f"Skipping {file}: Not enough rows or columns.")
                continue
            
            transformed_df = pd.DataFrame()
            transformed_df["observation_date"] = df["observation_date"][offset:].reset_index(drop=True)
            
            for col in df.columns[1:]:
                col_curr = df[col].iloc[offset:].reset_index(drop=True)
                col_past = df[col].iloc[:-offset].reset_index(drop=True)
                diff_values = col_curr - col_past

                filtered_diff = diff_values.apply(lambda x: x if x > threshold else '')

                transformed_df[col] = filtered_diff

            transformed_df.to_csv(output_path, index=False)
            print(f"Processed and saved: {output_path}")

# Run it with proper settings
process_cleaned_files(CLEANED_DIR, TRANSFORM_DIR, offset=252, threshold=0.0)
