import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import importlib.util
import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg
from scipy.optimize import minimize
from multiprocessing import Pool, cpu_count

# Locate CODE directory
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

# Load Basel3_Global_Filepath.py
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Paths
ROOT_DIR = paths.BASEL3_ROOT
FRED_DIR = os.path.join(ROOT_DIR, "RWA", "FRED")
EXPECTED_COUPON_DIR = os.path.join(ROOT_DIR, "RWA", "Practical", "Constant Maturity Treasury", "EXP_COUPON")
os.makedirs(EXPECTED_COUPON_DIR, exist_ok=True)

# Series list
DEFAULT_SERIES = ["DGS1", "DGS3", "DGS5", "DGS10", "DGS20", "DGS30"]

# Estimation functions
def estimate_theta_ar1(yields):
    model = AutoReg(yields, lags=1).fit()
    beta = model.params[1]
    mu = model.params[0] / (1 - beta)
    sigma = np.std(model.resid)
    theta = -np.log(beta) * 252
    return theta, mu, sigma

def cir_log_likelihood(params, yields, dt):
    theta, mu, sigma = params
    ll = 0
    for i in range(len(yields) - 1):
        xt, xt_next = yields[i], yields[i+1]
        mean_xt = xt + theta * (mu - xt) * dt
        variance_xt = sigma**2 * xt * dt
        if variance_xt <= 0:
            return np.inf
        ll += -0.5 * np.log(2 * np.pi * variance_xt) - 0.5 * ((xt_next - mean_xt)**2 / variance_xt)
    return -ll

def estimate_theta_cir(yields):
    dt = 1 / 252
    initial_guess = [1.47, np.mean(yields), np.std(np.diff(yields))]
    bounds = [(1e-3, None), (1e-3, None), (1e-3, None)]
    result = minimize(cir_log_likelihood, initial_guess, args=(yields, dt), bounds=bounds, method='L-BFGS-B')
    return result.x if result.success else (None, None, None)

# Process each series
def process_series(args):
    series, model_type = args
    try:
        matching_files = [f for f in os.listdir(FRED_DIR) if f.startswith(series) and f.endswith(".csv")]
        if not matching_files:
            print(f"⚠️ Skipping {series}: no CSV found.")
            return series, None

        latest_file = max(matching_files, key=lambda f: os.path.getmtime(os.path.join(FRED_DIR, f)))
        file_path = os.path.join(FRED_DIR, latest_file)

        df = pd.read_csv(file_path, parse_dates=["observation_date"])
        df = df.dropna(subset=[series]).sort_values("observation_date").reset_index(drop=True)

        df[series] = df[series] / 100.0
        yields = df[series].values

        if model_type == "AR1":
            theta, mu, sigma = estimate_theta_ar1(yields)
        elif model_type == "CIR":
            theta, mu, sigma = estimate_theta_cir(yields)
        else:
            raise ValueError("Invalid model type.")

        print(f"✅ {series}: θ={theta:.4f}, μ={mu:.4f}, σ={sigma:.4f}")
        return series, (round(theta, 4), round(mu, 4), round(sigma, 4))

    except Exception as e:
        print(f"❌ Error processing {series}: {e}")
        return series, None

# Main
def main(series_list=None, model_type="CIR", output_csv="CIR_parameters_summary.csv"):
    if series_list is None:
        series_list = DEFAULT_SERIES

    param_names = ["Mean Reversion Speed", "Long-Term Mean", "Volatility"]
    results = {param: [] for param in param_names}
    processed_series = []

    # Parallel processing
    with Pool(processes=min(len(series_list), cpu_count())) as pool:
        args_list = [(series, model_type) for series in series_list]
        outputs = pool.map(process_series, args_list)

    for series, values in outputs:
        if values:
            theta, mu, sigma = values
            results["Mean Reversion Speed"].append(theta)
            results["Long-Term Mean"].append(mu)
            results["Volatility"].append(sigma)
            processed_series.append(series)

    # Align output
    final_data = {param: [] for param in param_names}
    for series in series_list:
        if series in processed_series:
            idx = processed_series.index(series)
            for param in param_names:
                final_data[param].append(results[param][idx])
        else:
            for param in param_names:
                final_data[param].append("")

    summary_df = pd.DataFrame(final_data, index=series_list).T
    summary_df.index.name = "Parameters"

    # ✅ Write to EXPECTED_COUPON_DIR, not FRED_DIR
    output_path = os.path.join(EXPECTED_COUPON_DIR, output_csv)
    summary_df.to_csv(output_path)

    print(f"\n📄 Drift summary saved to: {output_path}")
    print(summary_df)

# Entry point
if __name__ == "__main__":
    main(model_type="CIR", output_csv="CIR_parameters_summary.csv")
