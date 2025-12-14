import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import importlib.util
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

parser = argparse.ArgumentParser(description="Zero → blank for *_q0 columns")
parser.add_argument("--peer_group")
parser.add_argument("--bin", type=int)
args = parser.parse_args()

# ----------------------------
# RESOLVE INPUT FROM PIPELINE OR ARGS
# ----------------------------

PIPE_INPUT_DIR = os.environ.get("PIPE_INPUT_DIR")

PEER_GROUP = None
BIN = None

if PIPE_INPUT_DIR:
    # Expect: .../RAW/<peer_group>/<bin>
    parts = os.path.normpath(PIPE_INPUT_DIR).split(os.sep)
    try:
        PEER_GROUP = parts[-2].lower()
        BIN = int(parts[-1])
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
        ROOT_DIR, "Material Events", "IG", "RAW", PEER_GROUP, str(BIN)
    )

# ----------------------------
# OUTPUT DIR (DERIVED, NOT ARGUED)
# ----------------------------

OUTPUT_DIR = os.path.join(INPUT_DIR, "Zeros")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------
# ZERO DETECTION
# ----------------------------

def is_zero_series(s: pd.Series) -> pd.Series:
    s_str = s.astype(str)
    s_norm = (
        s_str.str.strip()
             .str.replace(",", "", regex=False)
             .str.replace("\uFEFF", "", regex=False)
             .str.replace("+", "", regex=False)
             .str.lower()
    )
    empty_mask = s_norm.eq("")
    s_num = pd.to_numeric(s_norm, errors="coerce")
    return s_num.eq(0) & ~empty_mask

# ----------------------------
# PROCESS FILES
# ----------------------------

for fname in os.listdir(INPUT_DIR):
    if not fname.lower().endswith(".csv"):
        continue

    in_path = os.path.join(INPUT_DIR, fname)
    out_path = os.path.join(OUTPUT_DIR, fname)

    df = pd.read_csv(in_path, dtype=str)

    # Normalize column names
    df.columns = [
        c.replace("\uFEFF", "").strip() if isinstance(c, str) else c
        for c in df.columns
    ]

    q0_cols = [c for c in df.columns if isinstance(c, str) and c.endswith("_q0")]

    total_replaced = 0
    for col in q0_cols:
        mask = is_zero_series(df[col])
        total_replaced += int(mask.sum())
        df.loc[mask, col] = ""

    print(
        f"{fname}: blanked {total_replaced} zero cells "
        f"across {len(q0_cols)} _q0 columns"
    )

    df.to_csv(out_path, index=False)

print(f"Zero → blank completed.")
print(f"Input from: {INPUT_DIR}")
print(f"Output to: {OUTPUT_DIR}")
