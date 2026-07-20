import os

# Prevent NumPy/SciPy from creating extra native threads inside each process.
# The script parallelizes by maturity, so one native thread per process is enough.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import sys
sys.stdout.reconfigure(line_buffering=True)

import importlib.util
import concurrent.futures
import numpy as np
import pandas as pd
from scipy.optimize import minimize

###############################################################################
#                           1) PATH SETUP & MODULE IMPORT
###############################################################################

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))

    while current_dir and os.path.basename(current_dir).lower() != "src":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate the 'src' directory.")
        current_dir = parent_dir

    return current_dir


CODE_DIR = find_code_dir()
if CODE_DIR not in sys.path:
    sys.path.append(CODE_DIR)

filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)

if spec is None or spec.loader is None:
    raise ImportError(f"Could not load Basel3_Global_Filepath.py from {filepath}")

paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

ROOT_DIR = paths.BASEL3_ROOT
RWA_DIR = os.path.join(ROOT_DIR, "RWA")
EXP_DIR = os.path.join(RWA_DIR, "Experimental")
OUTPUT_DIR = os.path.join(EXP_DIR, "MLE YIELD", "RAW")

###############################################################################
#                               2) USER SETTINGS
###############################################################################

WINDOW_SIZE = 2520
DT = 1 / 252

CSV_FILES = [
    "DGS1.csv",
    "DGS2.csv",
    "DGS3.csv",
    "DGS5.csv",
    "DGS7.csv",
    "DGS10.csv",
    "DGS20.csv",
    "DGS30.csv",
]

###############################################################################
#                    3) DEFINE CIR MODEL ESTIMATION FUNCTIONS
###############################################################################

def cir_log_likelihood(params, yields, dt):
    """Return the negative Gaussian Euler CIR log-likelihood."""
    theta, mu, sigma = params

    xt = yields[:-1]
    xt_next = yields[1:]

    if sigma <= 0.0 or np.any(xt <= 0.0):
        return np.inf

    mean_xt = xt + theta * (mu - xt) * dt
    variance_xt = sigma * sigma * xt * dt
    residual = xt_next - mean_xt

    return 0.5 * np.sum(
        np.log(2.0 * np.pi * variance_xt)
        + (residual * residual) / variance_xt
    )


def make_initial_guess(yields_block):
    """Create the original generic starting values for the first window."""
    sigma_guess = float(np.std(np.diff(yields_block)))

    return np.array(
        [
            1.5,
            max(float(np.mean(yields_block)), 1e-6),
            max(sigma_guess, 1e-6),
        ],
        dtype=np.float64,
    )


def estimate_theta_cir(yields_block, initial_guess):
    """Estimate theta, mu, and sigma for one rolling window."""
    bounds = ((1e-6, None), (1e-6, None), (1e-6, None))

    result = minimize(
        cir_log_likelihood,
        x0=initial_guess,
        args=(yields_block, DT),
        bounds=bounds,
        method="L-BFGS-B",
    )

    if result.success and np.all(np.isfinite(result.x)):
        return result.x

    return np.array([np.nan, np.nan, np.nan], dtype=np.float64)

###############################################################################
#                         4) PROCESS ONE MATURITY FILE
###############################################################################

def process_csv(file_name):
    """
    Process all rolling windows for one maturity sequentially.

    Sequential processing within a maturity allows each window to use the
    preceding window's fitted parameters as its optimizer starting point.
    Different maturities are processed concurrently in separate processes.
    """
    csv_path = os.path.join(RWA_DIR, "FRED", file_name)
    yield_column = os.path.splitext(file_name)[0]

    print(f"Processing {file_name}...")

    df = pd.read_csv(csv_path)

    if "observation_date" in df.columns:
        df["observation_date"] = pd.to_datetime(
            df["observation_date"],
            errors="coerce",
        )

    if yield_column not in df.columns:
        raise KeyError(f"{yield_column} column not found in {file_name}.")

    df["yield_clean"] = pd.to_numeric(
        df[yield_column],
        errors="coerce",
    ).bfill()

    if df["yield_clean"].isna().any():
        raise ValueError(
            f"{file_name} still contains missing yield values after backfilling."
        )

    yields_data = df["yield_clean"].to_numpy(dtype=np.float64, copy=True)
    row_count = yields_data.size
    total_windows = row_count - WINDOW_SIZE + 1

    if total_windows <= 0:
        raise ValueError(
            f"{file_name} contains {row_count} rows, fewer than the "
            f"required {WINDOW_SIZE}-row window."
        )

    # Preserve one-based row labels in the output CSV.
    df.index = np.arange(1, row_count + 1)

    theta_results = np.full(row_count, np.nan, dtype=np.float64)
    mu_results = np.full(row_count, np.nan, dtype=np.float64)
    sigma_results = np.full(row_count, np.nan, dtype=np.float64)

    print(
        f"Starting {total_windows} calculations for {file_name}: "
        f"output row {total_windows} down to row 1..."
    )

    previous_params = None

    # Work backward exactly as the original script intended, but use valid
    # zero-based NumPy positions and one-based DataFrame labels separately.
    for count, start_position in enumerate(
        range(total_windows - 1, -1, -1),
        start=1,
    ):
        block = yields_data[start_position:start_position + WINDOW_SIZE]

        if previous_params is None:
            initial_guess = make_initial_guess(block)
        else:
            initial_guess = previous_params

        params = estimate_theta_cir(block, initial_guess)
        theta, mu, sigma = params

        if np.all(np.isfinite(params)):
            previous_params = params
        else:
            # Do not propagate a failed fit into the next optimizer call.
            previous_params = None

        theta_results[start_position] = theta
        mu_results[start_position] = mu
        sigma_results[start_position] = sigma

        if count % 100 == 0 or count == total_windows:
            output_row = start_position + 1
            print(
                f"Processed {count}/{total_windows} windows in {file_name}. "
                f"Row {output_row}: theta={theta}, mu={mu}, sigma={sigma}"
            )

    df["theta"] = theta_results
    df["mu"] = mu_results
    df["sigma"] = sigma_results

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_csv_path = os.path.join(
        OUTPUT_DIR,
        file_name.replace(".csv", "_with_parameters.csv"),
    )

    df.to_csv(output_csv_path, index=True)
    print(f"Done processing {file_name}. Output saved to: {output_csv_path}")

    return output_csv_path

###############################################################################
#                           5) RUN ALL MATURITIES
###############################################################################

def main():
    # One process per maturity. This replaces the original nested structure of
    # eight outer threads, each creating fourteen inner worker processes.
    worker_count = min(len(CSV_FILES), os.cpu_count() or 1)

    print(
        f"Processing {len(CSV_FILES)} maturity files with "
        f"{worker_count} maturity-level worker processes..."
    )

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=worker_count
    ) as executor:
        output_paths = list(executor.map(process_csv, CSV_FILES))

    print("All files processed.")
    for output_path in output_paths:
        print(output_path)


if __name__ == "__main__":
    main()
