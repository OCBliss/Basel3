import os
import sys
import importlib.util
import pandas as pd
import argparse
import json

# ----------------- Locate CODE_DIR & Import ROOT_DIR -----------------
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

filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

ROOT_DIR = paths.BASEL3_ROOT

# ----------------- Manifest Utilities -----------------
MANIFEST_FILE = os.path.join(ROOT_DIR, "Material Events", "IG", "JSD_intragroup_manifest.json")

def build_manifest(input_dirs):
    manifest = {}
    for folder in input_dirs:
        folder_manifest = {}
        if not os.path.exists(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if filename.endswith(".csv"):
                filepath = os.path.join(folder, filename)
                stat = os.stat(filepath)
                folder_manifest[filename] = {
                    "mtime": stat.st_mtime,
                    "size": stat.st_size
                }
        manifest[folder] = folder_manifest
    return manifest

def load_previous_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    return None

def save_current_manifest(manifest):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

def manifests_equal(m1, m2):
    return m1 == m2

# ----------------- CSV Processing -----------------
def process_csvs(process_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(process_dir):
        if filename.endswith(".csv"):
            file_path = os.path.join(process_dir, filename)
            df = pd.read_csv(file_path)

            # Check first row beneath header
            first_row = df.iloc[0]
            columns_to_keep = [col for col in df.columns if pd.to_numeric(first_row[col], errors='coerce') >= 0.3]

            cleaned_df = df[columns_to_keep]

            output_path = os.path.join(output_dir, filename)
            cleaned_df.to_csv(output_path, index=False)

            print(f"[INFO] Processed: {filename} | Dropped: {len(df.columns) - len(columns_to_keep)} columns")
    
    print(f"Output to: {output_dir}")

# ----------------- Main -----------------
def main():
    parser = argparse.ArgumentParser(description="Process Basel III CSVs by dropping columns <0.3")
    parser.add_argument('--process_dir_t1', required=True)
    parser.add_argument('--process_dir_t2', required=True)
    parser.add_argument('--process_dir_t3', required=True)
    parser.add_argument('--process_dir_t4', required=True)
    parser.add_argument('--output_dir_t1', required=True)
    parser.add_argument('--output_dir_t2', required=True)
    parser.add_argument('--output_dir_t3', required=True)
    parser.add_argument('--output_dir_t4', required=True)
    args = parser.parse_args()

    # Build full absolute paths
    process_dirs = [
        os.path.join(ROOT_DIR, args.process_dir_t1),
        os.path.join(ROOT_DIR, args.process_dir_t2),
        os.path.join(ROOT_DIR, args.process_dir_t3),
        os.path.join(ROOT_DIR, args.process_dir_t4)
    ]

    output_dirs = [
        os.path.join(ROOT_DIR, args.output_dir_t1),
        os.path.join(ROOT_DIR, args.output_dir_t2),
        os.path.join(ROOT_DIR, args.output_dir_t3),
        os.path.join(ROOT_DIR, args.output_dir_t4)
    ]

    # --- Build current manifest ---
    current_manifest = build_manifest(process_dirs)
    previous_manifest = load_previous_manifest()

    # --- Compare ---
    if previous_manifest and manifests_equal(previous_manifest, current_manifest):
        print("[INFO] No new or changed files detected. Skipping processing.")
        sys.exit(0)

    # --- Process ---
    for proc_dir, out_dir in zip(process_dirs, output_dirs):
        process_csvs(proc_dir, out_dir)

    # --- Save new manifest ---
    save_current_manifest(current_manifest)
    print("[INFO] Processing complete. Manifest updated.")

if __name__ == "__main__":
    main()
