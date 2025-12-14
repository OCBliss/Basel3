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

def cir_log_likelihood(params, volatilities, dt):
    """
    Compute the negative log-likelihood for the CIR model using sigma values.
    """
    theta, mu, sigma = params
    n = len(volatilities) - 1
    ll = 0.0
    epsilon = 1e-8  # Small positive threshold to prevent log(0) or division by zero
    
    for i in range(n):
        xt = volatilities[i]
        xt_next = volatilities[i + 1]
        mean_xt = xt + theta * (mu - xt) * dt
        var_xt = max(sigma**2 * xt * dt, epsilon)  # Ensure variance is positive
        
        ll += -0.5 * np.log(2 * np.pi * var_xt)
        ll += -0.5 * ((xt_next - mean_xt)**2 / var_xt)
    return -ll  # Negative log-likelihood for minimization

def estimate_theta_cir(volatility_block):
    """
    Estimate (theta_vol, mu_vol, vol_vol) for the CIR model using MLE on a block of sigma values.
    """
    dt = 1/252
    if np.all(np.isnan(volatility_block)) or len(volatility_block) == 0:
        return (np.nan, np.nan, np.nan)
    
    initial_guess = [1.5, np.nanmean(volatility_block), np.nanstd(np.diff(volatility_block))]
    bounds = [(1e-6, None), (1e-6, None), (1e-6, None)]
    
    res = minimize(cir_log_likelihood, initial_guess, args=(volatility_block, dt),
                   bounds=bounds, method='L-BFGS-B')
    
    return res.x if res.success else (np.nan, np.nan, np.nan)

###############################################################################
#              3) DEFINE THE WINDOW PROCESSING FUNCTION
###############################################################################

def process_window(i, sigma_data):
    """
    Compute CIR parameters for the window starting at row `i` using sigma data.
    """
    block = sigma_data[i : i + 2520]  # FIXED WINDOW SELECTION (2520 rows ~ 5 years)
    if len(block) < 2520 or np.isnan(block).any():
        return i, np.nan, np.nan, np.nan  # Skip incomplete windows
    
    theta_vol, mu_vol, vol_vol = estimate_theta_cir(block)
    return i, theta_vol, mu_vol, vol_vol

###############################################################################
#        4) PROCESS EACH CSV FILE USING MULTIPROCESSING
###############################################################################

def process_csv(file_name):
    """
    Process a single CSV file and compute CIR parameters using multiprocessing on sigma.
    """
    csv_path = os.path.join(EXP_DIR, "MLE YIELD", file_name)
    print(f"\nProcessing {file_name}...\n" + "-"*50)
    print("Loading data...")

    df = pd.read_csv(csv_path)

    # Convert observation date to datetime
    if 'observation_date' in df.columns:
        df['observation_date'] = pd.to_datetime(df['observation_date'], errors='coerce')

    # Ensure sigma column exists
    if 'sigma' not in df.columns:
        print(f"Error: sigma column not found in {file_name}. Skipping.")
        return

    # Fill missing values
    df['sigma_clean'] = df['sigma'].fillna(method='bfill')
    df['sigma_clean'] = df['sigma_clean'].fillna(method='ffill')

    # Reindex for preservation
    N = len(df)
    df.index = range(1, N + 1)

    # Create new columns for CIR parameters
    df['theta_vol'] = np.nan
    df['mu_vol']    = np.nan
    df['vol_vol']   = np.nan

    # Rolling window processing
    window_size = 2520
    start_top_row = N - window_size + 2

    print(f"Starting calculations for {file_name} from row {start_top_row} down to row 1...")
    print("-"*50)
    print("Initializing multiprocessing...")

    sigma_data = df['sigma_clean'].values
    indices = [i for i in range(start_top_row, 0, -1) if i + window_size <= N]
    total = len(indices)

    # Using multiprocessing to speed up processing
    with concurrent.futures.ProcessPoolExecutor(max_workers=14) as executor:
        futures = {executor.submit(process_window, i, sigma_data): i for i in indices}
        for count, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            i, theta_vol, mu_vol, vol_vol = future.result()
            df.at[i, 'theta_vol'] = theta_vol
            df.at[i, 'mu_vol'] = mu_vol
            df.at[i, 'vol_vol'] = vol_vol
            if count % 100 == 0 or count == total:
                print(f"Processed {count}/{total} windows in {file_name}. Row {i}: theta_vol={theta_vol}, mu_vol={mu_vol}, vol_vol={vol_vol}")

    print("Finalizing processing...")
    
    output_csv_path = os.path.join(EXP_DIR, "MLE VOL", file_name.replace(".csv", "_parameters.csv"))
    df.to_csv(output_csv_path, index=True)
    
    print(f"Done processing {file_name}.")
    print(f"Output saved to: {output_csv_path}")
    print("-"*50)

###############################################################################
#        5) RUN THE SCRIPT FOR MULTIPLE CSV FILES
###############################################################################

csv_files = [
    "DGS1_vol.csv",
    "DGS2_vol.csv",
    "DGS3_vol.csv",
    "DGS5_vol.csv",
    "DGS7_vol.csv",
    "DGS10_vol.csv",
    "DGS20_vol.csv",
    "DGS30_vol.csv"
]

for file in csv_files:
    process_csv(file)

print("\nAll files processed.")
print("-"*50)
