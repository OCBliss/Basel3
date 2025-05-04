import sys
sys.stdout.reconfigure(line_buffering=True)
import os

# Step 1: Determine the Basel3 root dynamically
BASEL3_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Step 2: Define other important directories
CODE_DIR = os.path.join(BASEL3_ROOT, "CODE")
DATA_DIR = os.path.join(BASEL3_ROOT, "DATA")
RESULTS_DIR = os.path.join(BASEL3_ROOT, "RESULTS")

# Step 3: Debugging prints (optional)
if __name__ == "__main__":
    print(f"Using Basel3 Root: {BASEL3_ROOT}")
    print(f"Code Directory: {CODE_DIR}")
    print(f"Data Directory: {DATA_DIR}")
    print(f"Results Directory: {RESULTS_DIR}")
