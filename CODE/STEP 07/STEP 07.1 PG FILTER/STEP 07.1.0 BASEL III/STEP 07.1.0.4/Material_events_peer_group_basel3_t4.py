import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import importlib.util
import pandas as pd

# --- Step 1: Find the CODE Directory ---
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

# --- Step 2: Locate CODE and Add to sys.path ---
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# --- Step 3: Import Basel3_Global_Filepath Dynamically ---
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# --- Step 4: Use the Dynamically Determined ROOT_DIR ---
ROOT_DIR = paths.BASEL3_ROOT
CALL_DIR = os.path.join(ROOT_DIR, "Call Report")
MAT_DIR  = os.path.join(ROOT_DIR, "Material Events")

# -----------------------------
# Load Valid Dates from quarters_basel3.csv
# -----------------------------
quarters_file = os.path.join(MAT_DIR, "quarters_basel3.csv")
quarters_df   = pd.read_csv(quarters_file)
# Replace 'Quarters' with the actual column name in quarters_basel3.csv that holds dates in YYYYMMDD.
valid_dates   = set(quarters_df['Quarters'].astype(str))

# -----------------------------
# Helper Function to Filter & Concatenate
# -----------------------------
def filter_and_concatenate(process_dir, output_dir, output_filename, valid_dates, label):
    """Reads CSV files from process_dir, filters by valid_dates (comparing last 8 chars in filename),
    then concatenates and writes to output_dir with output_filename."""
    os.makedirs(output_dir, exist_ok=True)
    
    csv_files = [f for f in os.listdir(process_dir) if f.endswith('.csv')]
    if not csv_files:
        print(f"No CSV files found in {process_dir} for {label}.")
        return
    
    df_list = []
    for file in csv_files:
        # Extract last 8 characters (e.g. YYYYMMDD)
        filename_no_ext = os.path.splitext(file)[0]
        file_date       = filename_no_ext[-8:]  # last 8 characters
        
        if file_date in valid_dates:
            file_path = os.path.join(process_dir, file)
            df        = pd.read_csv(file_path)
            df_list.append(df)
            # print(f"Included {file} for {label}")
        else:
            print(f"Skipped {file}; date {file_date} not in quarters_basel3.csv for {label}")
    
    if df_list:
        combined_df = pd.concat(df_list, ignore_index=True)
        output_path = os.path.join(output_dir, output_filename)
        combined_df.to_csv(output_path, index=False)
        # print(f"\nSuccessfully concatenated {len(df_list)} files for {label}.\nOutput saved to {output_path}\n")
    else:
        print(f"No matching files found for {label}. No concatenation performed.\n")

# -----------------------------
# 1) Mergers
# -----------------------------
process_directory3 = os.path.join(MAT_DIR, "Mergers/Peer Group Mergers/Basel III T+4")
output_directory   = os.path.join(MAT_DIR, "Mergers/Peer Group Mergers")
filter_and_concatenate(
    process_dir     = process_directory3,
    output_dir      = output_directory,
    output_filename = "Peer_Group_Mergers_Basel3_t4.csv",
    valid_dates     = valid_dates,
    label           = "Mergers"
)

# -----------------------------
# 2) Failures
# -----------------------------
process_failures = os.path.join(MAT_DIR, "Failures/Peer Group Failures/Basel III T+4")
output_failures  = os.path.join(MAT_DIR, "Failures/Peer Group Failures")
filter_and_concatenate(
    process_dir     = process_failures,
    output_dir      = output_failures,
    output_filename = "Peer_Group_Failures_Basel3_t4.csv",
    valid_dates     = valid_dates,
    label           = "Failures"
)

# -----------------------------
# 3) Survivors
# -----------------------------
process_survivors = os.path.join(MAT_DIR, "Survivors/Peer Group Survivors/Basel III T+4")
output_survivors  = os.path.join(MAT_DIR, "Survivors/Peer Group Survivors")
filter_and_concatenate(
    process_dir     = process_survivors,
    output_dir      = output_survivors,
    output_filename = "Peer_Group_Survivors_Basel3_t4.csv",
    valid_dates     = valid_dates,
    label           = "Survivors"
)
