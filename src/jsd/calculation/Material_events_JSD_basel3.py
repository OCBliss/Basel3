import argparse
import pandas as pd
import os
import sys
import numpy as np
import re

# Step 1: Locate CODE directory FIRST
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "src":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'src' directory.")
        current_dir = parent_dir
    return current_dir

CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# NOW import
import Basel3_Global_Filepath as paths


class JSDComparer:
    """
    A class to handle Jensen-Shannon Divergence computations
    between CSV files in Survivors, Failures, and Mergers directories.
    """

    def __init__(self,
                 survivors_dir: str,
                 failures_dir: str,
                 mergers_dir: str,
                 output_dir: str,
                 bins):
        self.survivors_dir = survivors_dir
        self.failures_dir  = failures_dir
        self.mergers_dir   = mergers_dir
        self.output_dir    = output_dir
        self.bins = {str(width) for width in bins}
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

    # ----- Compare the selected bin widths across all three groups -----
    def compare_multiple_files(self):
        survivors_map = self._get_csvs_by_suffix(self.survivors_dir)
        failures_map  = self._get_csvs_by_suffix(self.failures_dir)
        mergers_map   = self._get_csvs_by_suffix(self.mergers_dir)

        common_suffixes = set(survivors_map.keys()) & set(failures_map.keys()) & set(mergers_map.keys())

        if not common_suffixes:
            print("[WARN] No common suffixes found across directories.")
            return

        print(f"[INFO] Found common suffixes: {sorted(common_suffixes)}")

        for suffix in sorted(common_suffixes, key=int):
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
        # Ensure dataframes are aligned by Bin (index), filling missing bins with 0
        df_control = df_control.set_index("Bin")
        df_other = df_other.set_index("Bin")

        df_control, df_other = df_control.align(df_other, join="outer", axis=0, fill_value=0)

        common_cols = [c for c in df_control.columns if c in df_other.columns]
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
            match = re.search(r"_binned_([1-9][0-9]*)\.csv$", f)
            if match and match.group(1) in self.bins:
                suffix_map[match.group(1)] = f
        return suffix_map


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("bin widths must be positive integers")
    if number <= 0:
        raise argparse.ArgumentTypeError("bin widths must be positive integers")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare material-event PMFs for selected horizons and bin widths."
    )
    parser.add_argument("--horizons", nargs="+", type=int, choices=(1, 2, 3, 4),
                        required=True, help="Horizons to calculate, from 1 through 4.")
    parser.add_argument("--bins", nargs="+", type=positive_int, required=True,
                        help="Central bin widths encoded in PMF filenames, such as 20 30 50 100.")
    parser.add_argument("--material-dir", default=paths.MAT_DIR,
                        help="Material Events directory (default: repository Material Events).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    for horizon in dict.fromkeys(args.horizons):
        horizon_name = f"Basel III T+{horizon}"
        comparer = JSDComparer(
            survivors_dir=os.path.join(args.material_dir, "Survivors", "JS Divergence",
                                       horizon_name, "Probabilities"),
            failures_dir=os.path.join(args.material_dir, "Failures", "JS Divergence",
                                     horizon_name, "Probabilities"),
            mergers_dir=os.path.join(args.material_dir, "Mergers", "JS Divergence",
                                    horizon_name, "Probabilities"),
            output_dir=os.path.join(args.material_dir, "JSD", f"BASEL III T+{horizon}"),
            bins=args.bins,
        )
        comparer.compare_multiple_files()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
