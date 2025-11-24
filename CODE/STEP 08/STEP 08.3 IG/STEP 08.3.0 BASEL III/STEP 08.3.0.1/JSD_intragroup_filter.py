import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import importlib.util
import numpy as np
import pandas as pd

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

# Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

ROOT_DIR = paths.BASEL3_ROOT
MAT_DIR  = os.path.join(ROOT_DIR, "Material Events")
JSD_DIR = os.path.join(MAT_DIR, "JSD")
IG_DIR = os.path.join(MAT_DIR, "IG")

# Define processing and output directories (EXPLICITLY as you specified!)
process_dir_t1 = os.path.join(JSD_DIR, "BASEL III T+1")
process_dir_t2 = os.path.join(JSD_DIR, "BASEL III T+2")
process_dir_t3 = os.path.join(JSD_DIR, "BASEL III T+3")
process_dir_t4 = os.path.join(JSD_DIR, "BASEL III T+4")

output_dir_t1 = os.path.join(IG_DIR, "BASEL III T+1")
output_dir_t2 = os.path.join(IG_DIR, "BASEL III T+2")
output_dir_t3 = os.path.join(IG_DIR, "BASEL III T+3")
output_dir_t4 = os.path.join(IG_DIR, "BASEL III T+4")

# Function to process CSVs
def process_csvs(process_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(process_dir):
        if filename.endswith(".csv"):
            file_path = os.path.join(process_dir, filename)
            df = pd.read_csv(file_path)

            # Check first row beneath header
            first_row = df.iloc[0]
            columns_to_keep = [col for col in df.columns if pd.to_numeric(first_row[col], errors='coerce') >= 0.3]

            cleaned_df = df[columns_to_keep]

            output_path = os.path.join(output_dir, filename)
            cleaned_df.to_csv(output_path, index=False)

            print(f"Processed: {filename} | Dropped: {len(df.columns) - len(columns_to_keep)} columns")

# Apply function to each directory pair
process_csvs(process_dir_t1, output_dir_t1)
process_csvs(process_dir_t2, output_dir_t2)
process_csvs(process_dir_t3, output_dir_t3)
process_csvs(process_dir_t4, output_dir_t4)