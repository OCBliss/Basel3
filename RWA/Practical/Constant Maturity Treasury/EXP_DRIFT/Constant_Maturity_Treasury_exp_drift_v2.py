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

# Define input and output directories
TRANSFORM_DIR = os.path.join(ROOT_DIR, "RWA/Constant Maturity Treasury/Differenced")
DRIFT_DIR     = os.path.join(ROOT_DIR, "RWA/Constant Maturity Treasury/EXP_DRIFT")

# Create output directory if it doesn't exist
os.makedirs(DRIFT_DIR, exist_ok=True)

# --- Drift Averaging Logic ---

DRIFT_COLS = ["DGS1", "DGS3", "DGS5", "DGS10", "DGS20", "DGS30"]

def compute_average_drift(transform_dir, drift_dir, target_cols):
    summary_rows = []

    for file in os.listdir(transform_dir):
        if file.endswith(".csv") and file.startswith("differenced_"):
            file_path = os.path.join(transform_dir, file)
            df = pd.read_csv(file_path, dtype=str)

            averages = {}
            for col in target_cols:
                if col in df.columns:
                    # Coerce to numeric, skip blank/empty entries
                    series = pd.to_numeric(df[col], errors='coerce')
                    avg = series.mean(skipna=True)
                    averages[col] = avg
                else:
                    averages[col] = ''

            summary_row = {"file": file}
            summary_row.update(averages)
            summary_rows.append(summary_row)

    # Save summary
    drift_df = pd.DataFrame(summary_rows)
    output_path = os.path.join(drift_dir, "expected_drift_summary.csv")
    drift_df.to_csv(output_path, index=False)
    print(f"Expected drifts written to: {output_path}")

# Run it
compute_average_drift(TRANSFORM_DIR, DRIFT_DIR, DRIFT_COLS)
