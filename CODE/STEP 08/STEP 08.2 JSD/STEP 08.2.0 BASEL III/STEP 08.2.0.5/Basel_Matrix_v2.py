import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import pandas as pd
import csv
import importlib.util
import re
from collections import defaultdict

# Load Basel3_Global_Filepath.py dynamically
def load_global_filepath(filepath):
    spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
    global_filepath = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(global_filepath)
    return global_filepath

# Locate Basel3_Global_Filepath.py
def find_global_filepath():
    for root, _, files in os.walk(os.path.abspath(os.sep)):
        if "Basel3_Global_Filepath.py" in files:
            return os.path.join(root, "Basel3_Global_Filepath.py")
    raise FileNotFoundError("Could not locate 'Basel3_Global_Filepath.py' on the system.")

# Load the filepath module and get ROOT_DIR
global_filepath_path = find_global_filepath()
global_filepath = load_global_filepath(global_filepath_path)
ROOT_DIR = global_filepath.ROOT_DIR

JSD_DIR = os.path.join(ROOT_DIR, "Material Events", "JSD")
T_FOLDERS = ["BASEL III T+1", "BASEL III T+2", "BASEL III T+3", "BASEL III T+4"]

# Regex: capture everything before _q0... and the suffix
rcb_pattern = re.compile(r'^(.*?)_(q0(?:q1|q2|q3)?)$')

file_matrix = defaultdict(lambda: defaultdict(pd.DataFrame))

# Load all T+ horizon CSVs
for t in T_FOLDERS:
    t_path = os.path.join(JSD_DIR, t)
    for fname in os.listdir(t_path):
        if fname.startswith("JSD_") and fname.endswith(".csv"):
            full_path = os.path.join(t_path, fname)
            df = pd.read_csv(full_path)
            file_matrix[fname][t] = df

# Process each JSD file group
for fname, t_dict in file_matrix.items():
    peer_meta = fname.replace("JSD_", "").replace(".csv", "")
    example_df = t_dict.get("BASEL III T+1")
    if example_df is None:
        continue

    grouped_vars = defaultdict(list)

    for col in example_df.columns:
        match = rcb_pattern.match(col)
        if match:
            group, suffix = match.groups()
            grouped_vars[group].append(suffix)

    for group, suffixes in grouped_vars.items():
        result_df = pd.DataFrame(index=suffixes, columns=T_FOLDERS)
        for t in T_FOLDERS:
            df = t_dict.get(t)
            if df is not None:
                for suffix in suffixes:
                    colname = f"{group}_{suffix}"
                    if colname in df.columns:
                        result_df.at[suffix, t] = df[colname].iloc[0]

        output_fname = f"JSD_{peer_meta}_{group}.csv"
        output_path = os.path.join(JSD_DIR, "Matrix Outputs", output_fname)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        result_df.to_csv(output_path)
        print(f"✅ Saved: {output_path}")