import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import importlib.util

def find_code_dir():
    """
    Traverse up from this script's directory until a folder named 'CODE' is found.
    Returns the absolute path to the CODE directory.
    """
    current_dir = os.path.abspath(os.path.dirname(__file__))  # Start from script's directory
    while current_dir and os.path.basename(current_dir) != "CODE":  # Traverse up until "CODE" is found
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Stop if we reach the root directory
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir  # Now 'CODE' directory is located

# Step 2: Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)  # Ensure CODE directory is in the import path

# Step 3: Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Step 4: Use the Dynamically Determined ROOT_DIR
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)

# Define Material Events base directory
MAT_DIR = os.path.join(ROOT_DIR, "Material Events")

# -------------------------------------------------------------------
# FOLDER CONFIG + DELETION RULES
# -------------------------------------------------------------------

TARGET_PATTERNS = ["BankFind Suite"]  # core phrase, case-insensitive

folders = [
    {
        "input_folder": os.path.join(MAT_DIR, "DE NOVO", "Cleaned"),
    },
    {
        "input_folder": os.path.join(MAT_DIR, "Failures", "Cleaned"),
    },
    {
        "input_folder": os.path.join(MAT_DIR, "Mergers", "Cleaned"),
    },
]

def file_contains_any_pattern(filepath, patterns):
    """
    Returns True if the file at `filepath` contains *any* of the strings in `patterns`
    (case-insensitive) in its text content.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
    except Exception as e:
        print(f"[WARN] Could not read file: {filepath} ({e})")
        return False

    for p in patterns:
        if p.lower() in content:
            return True
    return False

def filename_matches_patterns(fname, patterns):
    """
    Returns True if the filename (case-insensitive) contains any of the patterns.
    """
    lower_name = fname.lower()
    for p in patterns:
        if p.lower() in lower_name:
            return True
    return False

def apply_deletion_rules():
    """
    Iterate over all configured folders and delete files whose:
    - filename contains 'BankFind Suite' (any case), OR
    - content contains 'BankFind Suite' (any case).
    """
    for config in folders:
        folder = config["input_folder"]

        if not os.path.isdir(folder):
            print(f"[INFO] Folder does not exist, skipping: {folder}")
            continue

        print(f"[INFO] Scanning folder (recursive): {folder}")

        # recursive walk in case files are nested
        for root, dirs, files in os.walk(folder):
            for fname in files:
                fpath = os.path.join(root, fname)

                # First, check filename rule
                name_hit = filename_matches_patterns(fname, TARGET_PATTERNS)

                # If filename doesn't match, fall back to content
                content_hit = False
                if not name_hit:
                    content_hit = file_contains_any_pattern(fpath, TARGET_PATTERNS)

                if name_hit or content_hit:
                    reason = []
                    if name_hit:
                        reason.append("filename")
                    if content_hit:
                        reason.append("content")
                    reason_str = " & ".join(reason)
                    try:
                        print(f"[DELETE] {fpath} (matched {reason_str}: {TARGET_PATTERNS})")
                        os.remove(fpath)
                    except Exception as e:
                        print(f"[ERROR] Failed to delete {fpath}: {e}")

if __name__ == "__main__":
    apply_deletion_rules()
