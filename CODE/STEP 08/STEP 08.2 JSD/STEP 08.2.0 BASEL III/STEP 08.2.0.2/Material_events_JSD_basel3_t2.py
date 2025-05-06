import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import importlib.util
import numpy as np
import pandas as pd

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

# Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

ROOT_DIR = paths.BASEL3_ROOT
MAT_DIR  = os.path.join(ROOT_DIR, "Material Events")

class JSDComparer:
    """
    A class to handle Jensen-Shannon Divergence computations 
    between CSV files in Survivors, Failures, and Mergers directories.
    """

    def __init__(self,
                 survivors_dir: str,
                 failures_dir: str,
                 mergers_dir: str,
                 output_dir: str):
        self.survivors_dir = survivors_dir
        self.failures_dir  = failures_dir
        self.mergers_dir   = mergers_dir
        self.output_dir    = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    # ----- Divergence Functions -----
    def kl_divergence(self, p: np.ndarray, q: np.ndarray, eps=1e-15) -> float:
        p = np.where(p < eps, eps, p)
        q = np.where(q < eps, eps, q)
        return np.sum(p * np.log(p / q))

    def js_divergence(self, p: np.ndarray, q: np.ndarray, eps=1e-15) -> float:
        m = 0.5 * (p + q)
        return 0.5 * self.kl_divergence(p, m, eps) + 0.5 * self.kl_divergence(q, m, eps)

    def compute_jsd(self, p: np.ndarray, q: np.ndarray, eps=1e-15) -> float:
        return np.sqrt(self.js_divergence(p, q, eps))

    # ----- Old single file comparison -----
    def compare_single_files(self, control_type: str, other_type: str) -> None:
        control_dir = self._get_directory(control_type)
        other_dir   = self._get_directory(other_type)

        control_file = self._get_single_csv(control_dir, control_type)
        other_file   = self._get_single_csv(other_dir,   other_type)

        df_control = pd.read_csv(os.path.join(control_dir, control_file))
        df_other   = pd.read_csv(os.path.join(other_dir,   other_file))

        common_cols = [c for c in df_control.columns if c in df_other.columns and c != "Bin"]
        if not common_cols:
            raise ValueError(f"No matching columns besides 'Bin' in {control_file} and {other_file}.")

        jsd_results = {}

        for col in common_cols:
            p = pd.to_numeric(df_control[col], errors='coerce').fillna(0).values
            q = pd.to_numeric(df_other[col],   errors='coerce').fillna(0).values
            p_sum, q_sum = p.sum(), q.sum()
            if p_sum > 0: p = p / p_sum
            if q_sum > 0: q = q / q_sum
            jsd_val = self.compute_jsd(p, q)
            jsd_results[col] = jsd_val

        jsd_df = pd.DataFrame([jsd_results])
        jsd_df.insert(0, "Bin", "JSD")

        out_filename = f"JSD_{control_type}_vs_{other_type}.csv"
        out_path = os.path.join(self.output_dir, out_filename)
        jsd_df.to_csv(out_path, index=False)
        print(f"[INFO] Compared {control_type} vs. {other_type}: {out_path}")

    # ----- NEW: Multiple file comparison -----
    def compare_multiple_files(self):
        survivors_map = self._get_csvs_by_suffix(self.survivors_dir)
        failures_map  = self._get_csvs_by_suffix(self.failures_dir)
        mergers_map   = self._get_csvs_by_suffix(self.mergers_dir)

        common_suffixes = set(survivors_map.keys()) & set(failures_map.keys()) & set(mergers_map.keys())

        if not common_suffixes:
            print("[WARN] No common suffixes found across directories.")
            return

        print(f"[INFO] Found common suffixes: {sorted(common_suffixes)}")

        for suffix in common_suffixes:
            print(f"[INFO] Comparing files with suffix: _{suffix}")

            survivor_file = os.path.join(self.survivors_dir, survivors_map[suffix])
            failure_file  = os.path.join(self.failures_dir,  failures_map[suffix])
            merger_file   = os.path.join(self.mergers_dir,   mergers_map[suffix])

            df_survivor = pd.read_csv(survivor_file)
            df_failure  = pd.read_csv(failure_file)
            df_merger   = pd.read_csv(merger_file)

            # Compare: survivor vs failure
            self._compare_and_save(df_survivor, df_failure, f'JSD_survivors_vs_failures_{suffix}.csv')
            # Compare: survivor vs merger
            self._compare_and_save(df_survivor, df_merger, f'JSD_survivors_vs_mergers_{suffix}.csv')
            # Compare: merger vs failure
            self._compare_and_save(df_merger, df_failure, f'JSD_mergers_vs_failures_{suffix}.csv')

    # ----- Helpers -----
    def _compare_and_save(self, df_control, df_other, output_filename):
        common_cols = [c for c in df_control.columns if c in df_other.columns and c != "Bin"]
        if not common_cols:
            print(f"[WARN] No matching columns in {output_filename}. Skipping.")
            return
        
        jsd_results = {}
        for col in common_cols:
            p = pd.to_numeric(df_control[col], errors='coerce').fillna(0).values
            q = pd.to_numeric(df_other[col],   errors='coerce').fillna(0).values
            p_sum, q_sum = p.sum(), q.sum()
            if p_sum > 0: p = p / p_sum
            if q_sum > 0: q = q / q_sum
            jsd_val = self.compute_jsd(p, q)
            jsd_results[col] = jsd_val

        jsd_df = pd.DataFrame([jsd_results])
        jsd_df.insert(0, "Bin", "JSD")

        out_path = os.path.join(self.output_dir, output_filename)
        jsd_df.to_csv(out_path, index=False)
        print(f"[INFO] Output saved: {out_path}")

    def _get_csvs_by_suffix(self, directory: str) -> dict:
        """
        Returns a dict mapping suffix (e.g., '20') to CSV filename.
        """
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
        suffix_map = {}
        for f in csv_files:
            # Assumes filenames end like _20.csv
            suffix = f.split('_')[-1].replace('.csv', '')
            suffix_map[suffix] = f
        return suffix_map

    def _get_directory(self, which_type: str) -> str:
        which_type = which_type.lower()
        if which_type == 'survivors':
            return self.survivors_dir
        elif which_type == 'failures':
            return self.failures_dir
        elif which_type == 'mergers':
            return self.mergers_dir
        else:
            raise ValueError(f"Invalid directory type: {which_type}")

    def _get_single_csv(self, directory: str, label: str) -> str:
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
        if len(csv_files) == 0:
            raise FileNotFoundError(f"No CSV files found in {label} directory: {directory}")
        elif len(csv_files) > 1:
            raise ValueError(f"Expected exactly 1 CSV in {label} directory, but found {len(csv_files)}.")
        return csv_files[0]

# ------------------------- USAGE EXAMPLE -------------------------
if __name__ == "__main__":
    survivors_dir = os.path.join(MAT_DIR, "Survivors", "JS Divergence", "Basel III T+2", "Probabilities")
    failures_dir  = os.path.join(MAT_DIR, "Failures",  "JS Divergence", "Basel III T+2", "Probabilities")
    mergers_dir   = os.path.join(MAT_DIR, "Mergers",   "JS Divergence", "Basel III T+2", "Probabilities")
    output_dir    = os.path.join(MAT_DIR, "JSD", "BASEL III T+2")

    comparer = JSDComparer(
        survivors_dir=survivors_dir,
        failures_dir=failures_dir,
        mergers_dir=mergers_dir,
        output_dir=output_dir
    )

    # Run multiple file comparisons
    comparer.compare_multiple_files()
