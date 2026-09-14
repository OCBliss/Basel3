#!/usr/bin/env python3

import sys

# The project dependencies require Python 3.8 or newer. Do not relaunch an
# unknown python3 executable, which may be this same unsupported interpreter.
if sys.version_info < (3, 8):
    raise SystemExit("Python 3.8 or newer is required.")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import os

# Step 1: Determine the Basel3 root dynamically
BASEL3_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Step 2: Define code important directories
CODE_DIR = os.path.join(BASEL3_ROOT, "src")

# Step 3: Define data important directories
CALL_DIR = os.path.join(BASEL3_ROOT, "data")
###--data/TXT/
TXT_DIR = os.path.join(CALL_DIR, "TXT")
###--data/csv/
CSV_DIR = os.path.join(CALL_DIR, "CSV")
CLEANED_DIR = os.path.join(CSV_DIR, "Cleaned")
SCHEDULES_DIR = os.path.join(CSV_DIR, "Schedules")
INTER_DIR = os.path.join(CSV_DIR, "Interleaved")
INTERLEAVED_DIR = INTER_DIR
DYNAMIC_DIR = os.path.join(CSV_DIR, "Dynamic_Lag")

##--Material Events/
MAT_DIR = os.path.join(BASEL3_ROOT, "Material Events")

##--Material Events/
PIPE_DIR = os.path.join(BASEL3_ROOT, "pipeline")

# Step 4: Debugging prints
if __name__ == "__main__":
    print(f"Using Basel3 Root: {BASEL3_ROOT}")
    print(f"Code Directory: {CODE_DIR}")
    print(f"Data Directory: {CALL_DIR}")
    print(f"Data Directory: {TXT_DIR}")
    print(f"Data Directory: {CSV_DIR}")
    print(f"Data Directory: {CLEANED_DIR}")
    print(f"Data Directory: {INTER_DIR}")
    print(f"Data Directory: {DYNAMIC_DIR}")
    print(f"Results Directory: {MAT_DIR}")
