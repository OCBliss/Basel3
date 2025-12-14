import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import importlib.util
import numpy as np
import pandas as pd
import argparse

# ----------------------------
# LOCATE CODE DIR
# ----------------------------

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# ----------------------------
# LOAD GLOBAL PATHS
# ----------------------------

filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

ROOT_DIR = paths.BASEL3_ROOT

# ----------------------------
# ARGPARSE (OPTIONAL)
# ----------------------------

parser = argparse.ArgumentParser(description="Compute column means from Zeros output")
parser.add_argument("--peer_group")
parser.add_argument("--bin", type=int)
args = parser.parse_args()

# ----------------------------
# RESOLVE INPUT DIR
# ----------------------------

PIPE_INPUT_DIR = os.environ.get("PIPE_INPUT_DIR")

PEER_GROUP = None
BIN = None

if PIPE_INPUT_DIR:
    # Expect: .../RAW/<peer_group>/<bin>/Zeros
    parts = os.path.normpath(PIPE_INPUT_DIR).split(os.sep)
    try:
        if parts[-1].lower() != "zeros":
            raise RuntimeError
        BIN = int(parts[-2])
        PEER_GROUP = parts[-3].lower()
        INPUT_DIR = PIPE_INPUT_DIR
    except Exception:
        raise RuntimeError(f"Invalid PIPE_INPUT_DIR: {PIPE_INPUT_DIR}")
else:
    if args.peer_group is None or args.bin is None:
        raise RuntimeError(
            "Must supply --peer_group and --bin when not run via pipeline"
        )
    PEER_GROUP = args.peer_group.lower()
    BIN = args.bin
    INPUT_DIR = os.path.join(
        ROOT_DIR,
        "Material Events",
        "IG",
        "RAW",
        PEER_GROUP,
        str(BIN),
        "Zeros",
    )

# ----------------------------
# OUTPUT DIR (DERIVED)
# ----------------------------

OUTPUT_DIR = os.path.join(
    os.path.dirname(INPUT_DIR),  # .../<peer_group>/<bin>
    "Means",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------
# PROCESS FILES
# ----------------------------

EXCLUDE_COLS = {"CERT", "RCON9999"}

for fname in os.listdir(INPUT_DIR):
    if not fname.lower().endswith(".csv"):
        continue

    in_path = os.path.join(INPUT_DIR, fname)
    out_path = os.path.join(OUTPUT_DIR, fname)

    df = pd.read_csv(in_path, dtype=str)

    means = {}

    for col in df.columns:
        if col in EXCLUDE_COLS:
            means[col] = ""
            continue

        series = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
        means[col] = series.mean()

    mean_df = pd.DataFrame([means], columns=df.columns)
    mean_df.to_csv(out_path, index=False)

print("Column means generated.")
print(f"Input from: {INPUT_DIR}")
print(f"Output to: {OUTPUT_DIR}")
