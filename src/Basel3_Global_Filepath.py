#!/usr/bin/env python3

import sys

# ---- HARD GATE (must be first, no modern features before this) ----
if sys.version_info < (3, 6):
    try:
        import shutil
        import subprocess

        py3 = shutil.which("python3")
        if py3:
            print("🔄 Re-launching with Python 3...\n")
            subprocess.run([py3] + sys.argv)
        else:
            print("❌ Python 3 not found.")
            print("👉 Install via: brew install python\n")
    except Exception:
        print("❌ Python 3.6+ required. Please install Python 3.")
    sys.exit(1)

# ---- SAFE ZONE: Python 3+ only below this line ----

sys.stdout.reconfigure(line_buffering=True)

import os

# Step 1: Determine the Basel3 root dynamically
BASEL3_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Canonical project directories. Pipeline scripts should import these instead
# of rebuilding paths with inconsistent spelling or capitalization.
CODE_DIR = os.path.join(BASEL3_ROOT, "src")
CALL_DIR = os.path.join(BASEL3_ROOT, "data")
TXT_DIR = os.path.join(CALL_DIR, "TXT")
CSV_DIR = os.path.join(CALL_DIR, "CSV")
CLEANED_DIR = os.path.join(CSV_DIR, "Cleaned")
SCHEDULES_DIR = os.path.join(CSV_DIR, "Schedules")
INTERLEAVED_DIR = os.path.join(CSV_DIR, "Interleaved")
INTER_DIR = INTERLEAVED_DIR
DISTRIBUTED_DIR = os.path.join(CSV_DIR, "Distributed_Lag")
DYNAMIC_DIR = os.path.join(CSV_DIR, "Dynamic_Lag")
MAT_DIR = os.path.join(BASEL3_ROOT, "Material Events")
PIPE_DIR = os.path.join(BASEL3_ROOT, "pipeline")

# Step 3: Debugging prints
if __name__ == "__main__":
    print(f"Using Basel3 Root: {BASEL3_ROOT}")
    print(f"Code Directory: {CODE_DIR}")
    print(f"Data Directory: {CALL_DIR}")
    print(f"Results Directory: {MAT_DIR}")
