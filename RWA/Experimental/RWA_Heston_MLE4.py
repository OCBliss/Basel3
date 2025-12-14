import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import importlib.util
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import concurrent.futures

###############################################################################
#                           1) PATH SETUP & MODULE IMPORT
###############################################################################

def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

# Locate CODE directory and add it to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# Dynamically import Basel3_Global_Filepath module
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Build directory hierarchy:
ROOT_DIR = paths.BASEL3_ROOT
RWA_DIR  = os.path.join(ROOT_DIR, "RWA")
EXP_DIR  = os.path.join(RWA_DIR, "Experimental")

###############################################################################
#                    2) DEFINE CIR MODEL ESTIMATION FUNCTIONS
###############################################################################

def cir_log_likelihood(params, yields, dt):
    """
    Compute the negative log-likelihood for the CIR model.
    """
    theta, mu, sigma = params
    n = len(yields) - 1
    ll = 0.0
    for i in range(n):
        xt = yields[i]
        xt_next = yields[i + 1]
        mean_xt = xt + theta * (mu - xt) * dt
        var_xt = sigma**2 * xt * dt
        if var_xt <= 0:
            return np.inf
        ll += -0.5 * np.log(2 * np.pi * var_xt)
        ll += -0.5 * ((xt_next - mean_xt)**2 / var_xt)
    return -ll  # Negative log-likelihood for minimization

def estimate_theta_cir(yields_block):
    """
    Estimate (theta, mu, sigma) for the CIR model using MLE on a block of yields.
    """
    dt = 1/252
    initial_guess = [1.5, np.mean(yields_block), np.std(np.diff(yields_block))]
    bounds = [(1e-6, None), (1e-6, None), (1e-6, None)]
    res = minimize(cir_log_likelihood, initial_guess, args=(yields_block, dt),
                   bounds=bounds, method='L-BFGS-B')
    if res.success:
        return res.x  # (theta, mu, sigma)
    else:
        return (np.nan, np.nan, np.nan)

###############################################################################
#              3) DEFINE THE WINDOW PROCESSING FUNCTION
###############################################################################

def process_window(i, yields_data):
    """
    Compute CIR parameters for the window starting at row `i` using the given data.
    """
    block = yields_data[i : i + 2520]  # FIXED WINDOW SELECTION (1260 rows)
    theta, mu, sigma = estimate_theta_cir(block)
    return i, theta, mu, sigma  # RETURN CORRECT ROW i FOR STORING RESULTS

###############################################################################
#        4) PROCESS EACH CSV FILE DYNAMICALLY
###############################################################################

def process_csv(file_name):
    """
    Process a single CSV file and compute CIR parameters using multiprocessing.
    """
    csv_path = os.path.join(RWA_DIR, "FRED", file_name)
    print(f"Processing {file_name}...")

    # Extract the yield column name from the filename
    yield_column = file_name.replace(".csv", "")  # Example: "DGS2.csv" → "DGS2"

    # Load the CSV
    df = pd.read_csv(csv_path)

    # If there's an 'observation_date' column, convert it to datetime:
    if 'observation_date' in df.columns:
        df['observation_date'] = pd.to_datetime(df['observation_date'], errors='coerce')

    # Ensure yield column exists
    if yield_column not in df.columns:
        print(f"Error: {yield_column} column not found in {file_name}. Skipping.")
        return

    # Fill missing values and store in 'yield_clean'
    df['yield_clean'] = df[yield_column].fillna(method='bfill')

    # Reindex so Excel row numbers are preserved:
    N = len(df)
    df.index = range(1, N + 1)

    # Create new columns for CIR parameters
    df['theta'] = np.nan
    df['mu']    = np.nan
    df['sigma'] = np.nan

    # Rolling window parameters
    window_size = 2520
    start_top_row = N - window_size + 2  # 2918 - 1260 + 2 = 1661

    print(f"Starting calculations for {file_name} from row {start_top_row} down to row 1...")

    # Extract yield data separately to avoid multiprocessing dataframe issues
    yields_data = df['yield_clean'].values

    # Create a list of top row indices (from 1661 down to 1)
    indices = list(range(start_top_row, 0, -1))
    total = len(indices)

    # Use ProcessPoolExecutor with 14 workers for parallel processing.
    with concurrent.futures.ProcessPoolExecutor(max_workers=14) as executor:
        futures = {executor.submit(process_window, i, yields_data): i for i in indices}
        for count, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            i, theta, mu, sigma = future.result()
            df.at[i, 'theta'] = theta
            df.at[i, 'mu'] = mu
            df.at[i, 'sigma'] = sigma
            if count % 100 == 0 or count == total:
                print(f"Processed {count}/{total} windows in {file_name}. Row {i}: theta={theta}, mu={mu}, sigma={sigma}")

    # Save output CSV
    # output_csv_path = os.path.join(CMT_DIR, "FRED", file_name.replace(".csv", "_with_parameters.csv"))
    output_csv_path = os.path.join(EXP_DIR, "MLE YIELD")
    df.to_csv(output_csv_path, index=True)
    print(f"Done processing {file_name}. Output saved to: {output_csv_path}")

###############################################################################
#        5) RUN THE SCRIPT FOR MULTIPLE CSV FILES
###############################################################################

csv_files = [
    "DGS1.csv",
    "DGS2.csv",
    "DGS3.csv",
    "DGS5.csv",
    "DGS7.csv",
    "DGS10.csv",
    "DGS20.csv",
    "DGS30.csv"
]

# Run processing in parallel for all CSV files
with concurrent.futures.ThreadPoolExecutor(max_workers=len(csv_files)) as executor:
    executor.map(process_csv, csv_files)

print("All files processed.")
