import os
import pandas as pd
import importlib.util

# ------------------------------
# SETUP
# ------------------------------

def find_global_filepath():
    for root, _, files in os.walk(os.path.abspath(os.sep)):
        if "Basel3_Global_Filepath.py" in files:
            return os.path.join(root, "Basel3_Global_Filepath.py")
    raise FileNotFoundError("Could not locate 'Basel3_Global_Filepath.py'.")

def load_global_filepath(filepath):
    spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
    global_filepath = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(global_filepath)
    return global_filepath

# Columns of interest
DRIFT_COLS = ["DGS1", "DGS3", "DGS5", "DGS10", "DGS20", "DGS30"]

# ------------------------------
# MAIN EXECUTION
# ------------------------------

def compute_drift_from_combined_file(transform_dir, drift_dir):
    files = [f for f in os.listdir(transform_dir) if f.startswith("differenced_") and f.endswith(".csv")]
    if not files:
        raise FileNotFoundError("No differenced_*.csv found.")
    file = files[0]
    file_path = os.path.join(transform_dir, file)

    df = pd.read_csv(file_path, usecols=DRIFT_COLS)
    print(f"✅ Loaded {file} with {len(df)} rows")

    # Convert all to numeric in one vectorized pass
    numeric_df = df.apply(pd.to_numeric, errors='coerce')
    means = numeric_df.mean(skipna=True).round(10)
    means["file"] = file

    # Construct and save summary DataFrame
    out_df = pd.DataFrame([means])
    out_df = out_df[["file"] + DRIFT_COLS]  # Ensure column order
    out_path = os.path.join(drift_dir, "expected_drift_summary.csv")
    out_df.to_csv(out_path, index=False)
    print(f"✅ Drift summary saved to {out_path}")

# ------------------------------
# ENTRY POINT
# ------------------------------

if __name__ == "__main__":
    import time
    start = time.time()

    global_filepath_path = find_global_filepath()
    global_filepath = load_global_filepath(global_filepath_path)
    ROOT_DIR = global_filepath.ROOT_DIR
    RWA_DIR = os.path.join(ROOT_DIR, "RWA")
    PRACT_DIR = os.path.join(RWA_DIR, "Practical")
    TRANSFORM_DIR = os.path.join(PRACT_DIR, "Constant Maturity Treasury", "Differenced")
    DRIFT_DIR = os.path.join(PRACT_DIR, "Constant Maturity Treasury", "EXP_DRIFT")
    os.makedirs(DRIFT_DIR, exist_ok=True)

    compute_drift_from_combined_file(TRANSFORM_DIR, DRIFT_DIR)

    print(f"\n⏱ Total time: {round(time.time() - start, 2)} seconds")
