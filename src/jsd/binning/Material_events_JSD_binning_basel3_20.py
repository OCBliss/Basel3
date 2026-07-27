import requests
import pandas as pd
import os
import sys
sys.stdout.reconfigure(line_buffering=True)
import numpy as np
import re

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

# Load global filepaths for local root directory finder to aid dynamic folder locations
import Basel3_Global_Filepath as paths

ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)
DYNAMIC_DIR = paths.DYNAMIC_DIR # Dynamic (as in folder name) which is the end stage of preprocessing for the Call Reports lag ratios
MAT_DIR = paths.MAT_DIR # Material Events subroot folder

# ==============================
# PROCESSING FOR JSD BINNING
# ==============================

# -----------------------------
# Load Valid Dates from quarters_basel3.csv
# -----------------------------
quarters_file = os.path.join(MAT_DIR, "quarters_basel3.csv")
quarters_df   = pd.read_csv(quarters_file)
# Replace 'Quarters' with the actual column name in quarters_basel3.csv that holds dates in YYYYMMDD.
valid_dates   = set(quarters_df['Quarters'].astype(str))

# -----------------------------
# Helper Function to Bin Columns
# -----------------------------
def filter_and_concatenate(process_dir, output_dir, output_filename, label):
    """
    Reads CSV files from process_dir (or a single CSV file if process_dir is actually a file),
    bins each numeric column (ignoring the first two columns) into:
      - 20 bins from -1 to 1   (linspace(-1, 1, 211))
      - 5  bins for (1, 2]
      - 1  bin for > 2
    Then saves the binned counts for each CSV as a new file, adding "_binned.csv" to the original name.
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- Define Bin Edges ---
    # 20 equal bins between -1 and 1 (if you really want B_k = 30, 50, or 100 bins, change  B_k => B_k + 1).
    bins1 = np.linspace(-1, 1, 21)

    # 5 equal bins between 1 and 2 => edges [1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
    # Skipping the first edge if you don't want overlap with bins1
    bins2 = np.linspace(1, 2, 6)[1:]  

    # 1 bin for values > 2
    bins3 = np.array([2, np.inf])

    # Combine all bin edges
    bin_edges = np.concatenate((bins1, bins2, bins3))

    # Create human-readable bin labels
    bin_labels = []
    for i in range(len(bin_edges) - 1):
        lower = bin_edges[i]
        upper = bin_edges[i+1]
        if np.isinf(upper):
            label_bin = f"> {lower:.2f}"
        else:
            label_bin = f"[{lower:.2f}, {upper:.2f})"
        bin_labels.append(label_bin)

    # ---------------------------------------------------------
    # If process_dir is actually a file, process just that file.
    # If process_dir is a directory, process all CSVs in that directory.
    # ---------------------------------------------------------
    if os.path.isfile(process_dir):
        # It's a single CSV file
        csv_files = [os.path.basename(process_dir)]
        dir_for_reading = os.path.dirname(process_dir)
    else:
        # It's a directory
        dir_for_reading = process_dir
        csv_files = [f for f in os.listdir(process_dir) if f.endswith('.csv')]

    if not csv_files:
        print(f"[INFO] No CSV files found in {process_dir}.")
        return

    # --- Process Each CSV File ---
    for file in csv_files:
        file_path = os.path.join(dir_for_reading, file)
        if not os.path.isfile(file_path):
            print(f"[WARNING] Could not find file: {file_path}")
            continue
        
        df = pd.read_csv(file_path)
        
        # Ignore the first two columns (e.g., CERT and RCON9999) they are keys: CERT is the bank-specific ID and RCON9999 is the reporting quarter in YYYYMMDD format
        data = df.iloc[:, 2:]
        
        # Prepare a DataFrame to hold the histogram counts.
        hist_df = pd.DataFrame(index=bin_labels)
        
        # Loop through each column (header) and compute its histogram.
        for col in data.columns:
            # Convert the column to numeric (non-numeric => NaN) and drop NaNs.
            col_data = pd.to_numeric(data[col], errors='coerce').dropna()
            
            # Compute histogram counts
            counts, _ = np.histogram(col_data, bins=bin_edges)
            
            # Add the counts as a column
            hist_df[col] = counts

        # label the index as "Bin" in the output CSV
        hist_df.rename_axis("Bin", inplace=True)

        # Construct output filename:
        out_name = os.path.splitext(file)[0] + "_binned_20.csv"
        out_path = os.path.join(output_dir, out_name)

        hist_df.to_csv(out_path)
        print(f"[INFO] Binned data for file '{file}' saved to '{out_path}'.")


# -----------------------------
# Now we define each input CSV path (or directory) and its output directory.
# -----------------------------
# 1) Mergers
# -----------------------------
process_mergers_t1 = os.path.join(MAT_DIR, "Mergers", "Horizons", "Peer_Group_Mergers_Basel3_t1.csv") # This measures Mergers to occur T+1 or one (1) quarter from measurement period.
output_mergers_t1  = os.path.join(MAT_DIR, "Mergers", "JS Divergence", "Basel III T+1", "Binned")
filter_and_concatenate(
    process_dir     = process_mergers_t1,
    output_dir      = output_mergers_t1,
    output_filename = "Peer_Group_Mergers_Basel3_binned_20.csv",
    label           = "Mergers_t1"
)

process_mergers_t2 = os.path.join(MAT_DIR, "Mergers", "Horizons", "Peer_Group_Mergers_Basel3_t2.csv") # This measures Mergers to occur T+2 or two (2) quarters from measurement period.
output_mergers_t2  = os.path.join(MAT_DIR, "Mergers", "JS Divergence", "Basel III T+2", "Binned")
filter_and_concatenate(
    process_dir     = process_mergers_t2,
    output_dir      = output_mergers_t2,
    output_filename = "Peer_Group_Mergers_Basel3_binned_20.csv",
    label           = "Mergers_t2"
)

process_mergers_t3 = os.path.join(MAT_DIR, "Mergers", "Horizons", "Peer_Group_Mergers_Basel3_t3.csv") # This measures Mergers to occur T+3 or three (3) quarters from measurement period.
output_mergers_t3  = os.path.join(MAT_DIR, "Mergers", "JS Divergence", "Basel III T+3", "Binned")
filter_and_concatenate(
    process_dir     = process_mergers_t3,
    output_dir      = output_mergers_t3,
    output_filename = "Peer_Group_Mergers_Basel3_binned_20.csv",
    label           = "Mergers_t3"
)

process_mergers_t4 = os.path.join(MAT_DIR, "Mergers", "Horizons", "Peer_Group_Mergers_Basel3_t4.csv") # This measures Mergers to occur T+4 or four (4) quarters from measurement period.
output_mergers_t4  = os.path.join(MAT_DIR, "Mergers", "JS Divergence", "Basel III T+4", "Binned")
filter_and_concatenate(
    process_dir     = process_mergers_t4,
    output_dir      = output_mergers_t4,
    output_filename = "Peer_Group_Mergers_Basel3_binned_20.csv",
    label           = "Mergers_t4"
)

# -----------------------------
# 2) Failures
# -----------------------------
process_failures_t1 = os.path.join(MAT_DIR, "Failures", "Horizons", "Peer_Group_Failures_Basel3_t1.csv") # This measures Failures to occur T+1 or one (1) quarter from measurement period.
output_failures_t1  = os.path.join(MAT_DIR, "Failures", "JS Divergence", "Basel III T+1", "Binned")
filter_and_concatenate(
    process_dir     = process_failures_t1,
    output_dir      = output_failures_t1,
    output_filename = "Peer_Group_Failures_Basel3_binned_20.csv",
    label           = "Failures_t1"
)

process_failures_t2 = os.path.join(MAT_DIR, "Failures", "Horizons", "Peer_Group_Failures_Basel3_t2.csv") # This measures Mergers to occur T+2 or two (2) quarters from measurement period.
output_failures_t2  = os.path.join(MAT_DIR, "Failures", "JS Divergence", "Basel III T+2", "Binned")
filter_and_concatenate(
    process_dir     = process_failures_t2,
    output_dir      = output_failures_t2,
    output_filename = "Peer_Group_Failures_Basel3_binned_20.csv",
    label           = "Failures_t2"
)

process_failures_t3 = os.path.join(MAT_DIR, "Failures", "Horizons", "Peer_Group_Failures_Basel3_t3.csv") # This measures Mergers to occur T+3 or three (3) quarters from measurement period.
output_failures_t3  = os.path.join(MAT_DIR, "Failures", "JS Divergence", "Basel III T+3", "Binned")
filter_and_concatenate(
    process_dir     = process_failures_t3,
    output_dir      = output_failures_t3,
    output_filename = "Peer_Group_Failures_Basel3_binned_20.csv",
    label           = "Failures_t3"
)

process_failures_t4 = os.path.join(MAT_DIR, "Failures", "Horizons", "Peer_Group_Failures_Basel3_t4.csv") # This measures Mergers to occur T+4 or four (4) quarters from measurement period.
output_failures_t4  = os.path.join(MAT_DIR, "Failures", "JS Divergence", "Basel III T+4", "Binned")
filter_and_concatenate(
    process_dir     = process_failures_t4,
    output_dir      = output_failures_t4,
    output_filename = "Peer_Group_Failures_Basel3_binned_20.csv",
    label           = "Failures_t4"
)

# -----------------------------
# 3) Survivors -- The disjoint set of banks remaining after removing failures and mergers
# -----------------------------
process_survivors_t1 = os.path.join(MAT_DIR, "Survivors", "Horizons", "Peer_Group_Survivors_Basel3_t1.csv") # This measures Survivors to occur T+1 or one (1) quarters from measurement period.
output_survivors_t1  = os.path.join(MAT_DIR, "Survivors", "JS Divergence", "Basel III T+1", "Binned") # This is important because a bank that fails at T+1 may still show survival at T+2
filter_and_concatenate(
    process_dir     = process_survivors_t1,
    output_dir      = output_survivors_t1,
    output_filename = "Peer_Group_Survivors_Basel3_binned_20.csv",
    label           = "Survivors_t1"
)

process_survivors_t2 = os.path.join(MAT_DIR, "Survivors", "Horizons", "Peer_Group_Survivors_Basel3_t2.csv")
output_survivors_t2  = os.path.join(MAT_DIR, "Survivors", "JS Divergence", "Basel III T+2", "Binned")
filter_and_concatenate(
    process_dir     = process_survivors_t2,
    output_dir      = output_survivors_t2,
    output_filename = "Peer_Group_Survivors_Basel3_binned_20.csv",
    label           = "Survivors_t2"
)

process_survivors_t3 = os.path.join(MAT_DIR, "Survivors", "Horizons", "Peer_Group_Survivors_Basel3_t3.csv")
output_survivors_t3  = os.path.join(MAT_DIR, "Survivors", "JS Divergence", "Basel III T+3", "Binned")
filter_and_concatenate(
    process_dir     = process_survivors_t3,
    output_dir      = output_survivors_t3,
    output_filename = "Peer_Group_Survivors_Basel3_binned_20.csv",
    label           = "Survivors_t3"
)

process_survivors_t4 = os.path.join(MAT_DIR, "Survivors", "Horizons", "Peer_Group_Survivors_Basel3_t4.csv")
output_survivors_t4  = os.path.join(MAT_DIR, "Survivors", "JS Divergence", "Basel III T+4", "Binned")
filter_and_concatenate(
    process_dir     = process_survivors_t4,
    output_dir      = output_survivors_t4,
    output_filename = "Peer_Group_Survivors_Basel3_binned_20.csv",
    label           = "Survivors_t4"
)
