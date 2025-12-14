import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import importlib.util
import pandas as pd
import argparse

# ----------------------------
# Locate CODE directory
# ----------------------------
def find_code_dir():
    d = os.path.abspath(os.path.dirname(__file__))
    while os.path.basename(d) != "CODE":
        parent = os.path.dirname(d)
        if parent == d:
            raise RuntimeError("Could not locate CODE directory")
        d = parent
    return d

CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# ----------------------------
# Load global paths
# ----------------------------
spec = importlib.util.spec_from_file_location(
    "Basel3_Global_Filepath",
    os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

ROOT_DIR = paths.BASEL3_ROOT

# ----------------------------
# Args (OPTIONAL)
# ----------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--peer_group")
parser.add_argument("--bin", type=int)
args = parser.parse_args()

PIPE_INPUT_DIR = os.environ.get("PIPE_INPUT_DIR")

# ----------------------------
# Resolve peer_group / bin / INPUT_DIR
# ----------------------------
if PIPE_INPUT_DIR:
    INPUT_DIR = os.path.normpath(PIPE_INPUT_DIR)
    parts = INPUT_DIR.split(os.sep)

    try:
        BIN = int(parts[-1])
        PEER_GROUP = parts[-2].lower()
    except Exception:
        raise RuntimeError(f"Bad PIPE_INPUT_DIR: {PIPE_INPUT_DIR}")

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
        "Mergers",
        "Call Reports"
    )

# ----------------------------
# Reference + output dirs
# ----------------------------
REF_FILENAME = f"JSD_survivors_vs_{PEER_GROUP}_{BIN}.csv"

REF_T1_DIR = os.path.join(
    ROOT_DIR,
    "Material Events",
    "IG",
    "BASEL III T+1",
    REF_FILENAME
)

OUTPUT_DIR = os.path.join(
    ROOT_DIR,
    "Material Events",
    "IG",
    "RAW",
    PEER_GROUP,
    str(BIN)
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------
# Load reference headers
# ----------------------------
ref_df = pd.read_csv(REF_T1_DIR, nrows=0)
ref_headers = set(ref_df.columns)

FORCE_KEEP = {
    "CERT",
    "RCON9999",
    "FAILURE_T1",
    "FAILURE_T2",
    "FAILURE_T3",
    "FAILURE_T4",
    "MERGER_T1",
    "MERGER_T2",
    "MERGER_T3",
    "MERGER_T4",
}

# ----------------------------
# Process files
# ----------------------------
for fname in os.listdir(INPUT_DIR):
    if not fname.lower().endswith(".csv"):
        continue

    in_path = os.path.join(INPUT_DIR, fname)
    out_path = os.path.join(OUTPUT_DIR, fname)

    df = pd.read_csv(in_path)

    if df.shape[1] < 2:
        raise RuntimeError(f"{fname} has fewer than two columns")

    first_two = list(df.columns[:2])

    allowed_cols = [
        c for c in df.columns[2:]
        if c in ref_headers or c in FORCE_KEEP
    ]

    df[first_two + allowed_cols].to_csv(out_path, index=False)

print("Column filtering complete.")
print(f"Output to: {OUTPUT_DIR}")
