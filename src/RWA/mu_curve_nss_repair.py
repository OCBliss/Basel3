from __future__ import annotations
import sys
sys.stdout.reconfigure(line_buffering=True)
import os

# Prevent each worker from spawning its own BLAS thread pool.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import sys
import importlib.util

import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
import concurrent.futures
import multiprocessing as mp


# ============================================================
# USER SETTINGS
# ============================================================

###############################################################################
#                           1) PATH SETUP & MODULE IMPORT
###############################################################################
# --- Step 1: Find the CODE Directory ---
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))  # Start from the script's directory
    while current_dir and os.path.basename(current_dir) != "src":  # Traverse up until "CODE" is found
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Reached the root directory
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir  # CODE directory is located

# --- Step 2: Locate CODE and Add to sys.path ---
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)  # Ensure CODE directory is in the import path

# --- Step 3: Import Basel3_Global_Filepath Dynamically ---
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# --- Step 4: Use the Dynamically Determined ROOT_DIR ---
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)
RWA_DIR = os.path.join(ROOT_DIR, "RWA")
EXP_DIR = os.path.join(RWA_DIR, "Experimental")

###############################################################################
#                    2) DEFINE CIR MODEL ESTIMATION FUNCTIONS
###############################################################################

INPUT_FILE = os.path.join(EXP_DIR, "MLE YIELD", "CURVE", "mu_curve.csv")
OUTPUT_FILE = os.path.join(EXP_DIR, "MLE YIELD", "NSS", "mu_curve_nss_repaired.csv")

DATE_COLUMN = "observation_date"

MU_COLUMNS = {
    "mu1y": 1.0,
    "mu2y": 2.0,
    "mu3y": 3.0,
    "mu5y": 5.0,
    "mu7y": 7.0,
    "mu10y": 10.0,
    "mu20y": 20.0,
    "mu30y": 30.0,
}

# Any mu value whose absolute magnitude exceeds this threshold
# is treated as an exploded CIR estimate.
EXPLOSION_ABS_THRESHOLD = 9

# Use all logical CPU cores by default. Set to a smaller integer if desired.
MAX_WORKERS = min(28, max(1, (os.cpu_count() or 1)))


# ============================================================
# NELSON-SIEGEL-SVENSSON
# ============================================================

def nss_curve(
    maturity: np.ndarray,
    beta0: float,
    beta1: float,
    beta2: float,
    beta3: float,
    tau1: float,
    tau2: float,
) -> np.ndarray:
    """
    Evaluate a Nelson-Siegel-Svensson term structure.
    """
    maturity = np.asarray(maturity, dtype=float)

    x1 = maturity / tau1
    x2 = maturity / tau2

    level_slope_loading = -np.expm1(-x1) / x1

    first_curvature_loading = (
        level_slope_loading
        - np.exp(-x1)
    )

    second_curvature_loading = (
        -np.expm1(-x2) / x2
        - np.exp(-x2)
    )

    return (
        beta0
        + beta1 * level_slope_loading
        + beta2 * first_curvature_loading
        + beta3 * second_curvature_loading
    )


def nss_residuals(
    parameters: np.ndarray,
    maturities: np.ndarray,
    observed_mu: np.ndarray,
) -> np.ndarray:
    return (
        nss_curve(maturities, *parameters)
        - observed_mu
    )


# ============================================================
# NELSON-SIEGEL FALLBACK
# ============================================================

def ns_curve(
    maturity: np.ndarray,
    beta0: float,
    beta1: float,
    beta2: float,
    tau1: float,
) -> np.ndarray:
    """
    Evaluate the four-parameter Nelson-Siegel term structure.

    This is used when too few valid nodes remain to identify the
    six-parameter Svensson extension.
    """
    maturity = np.asarray(maturity, dtype=float)

    x1 = maturity / tau1

    level_slope_loading = -np.expm1(-x1) / x1

    curvature_loading = (
        level_slope_loading
        - np.exp(-x1)
    )

    return (
        beta0
        + beta1 * level_slope_loading
        + beta2 * curvature_loading
    )


def ns_residuals(
    parameters: np.ndarray,
    maturities: np.ndarray,
    observed_mu: np.ndarray,
) -> np.ndarray:
    return (
        ns_curve(maturities, *parameters)
        - observed_mu
    )


# ============================================================
# ANOMALY IDENTIFICATION
# ============================================================

def identify_anomalies(
    values: np.ndarray,
) -> np.ndarray:
    """
    Return a Boolean mask identifying invalid or exploded values.
    """
    values = np.asarray(values, dtype=float)

    # Repair only finite values that actually exceed the explosion threshold.
    # Historical NaNs represent unavailable maturities and are not themselves
    # reconstruction targets. They are simply excluded from the curve fit.
    return (
        np.isfinite(values)
        & (np.abs(values) > EXPLOSION_ABS_THRESHOLD)
    )


# ============================================================
# STARTING VALUES
# ============================================================

def curve_scale(
    observed_mu: np.ndarray,
) -> float:
    observed_mu = np.asarray(observed_mu, dtype=float)

    return max(
        float(np.max(np.abs(observed_mu))),
        float(np.ptp(observed_mu)),
        1.0,
    )


def nss_starting_parameters(
    maturities: np.ndarray,
    observed_mu: np.ndarray,
) -> list[np.ndarray]:
    order = np.argsort(maturities)

    maturities = maturities[order]
    observed_mu = observed_mu[order]

    short_mu = float(observed_mu[0])
    long_mu = float(observed_mu[-1])

    beta0 = long_mu
    beta1 = short_mu - long_mu

    amplitude = max(
        float(np.ptp(observed_mu)),
        abs(float(np.mean(observed_mu))) * 0.10,
        0.01,
    )

    starts = []

    tau_pairs = (
        (0.25, 2.0),
        (0.50, 3.0),
        (1.00, 5.0),
        (1.50, 10.0),
        (2.00, 15.0),
        (3.00, 20.0),
        (5.00, 30.0),
    )

    curvature_pairs = (
        (0.0, 0.0),
        (amplitude, -amplitude),
        (-amplitude, amplitude),
        (amplitude, amplitude),
        (-amplitude, -amplitude),
    )

    for tau1, tau2 in tau_pairs:
        for beta2, beta3 in curvature_pairs:
            starts.append(
                np.array(
                    [
                        beta0,
                        beta1,
                        beta2,
                        beta3,
                        tau1,
                        tau2,
                    ],
                    dtype=float,
                )
            )

    return starts


def ns_starting_parameters(
    maturities: np.ndarray,
    observed_mu: np.ndarray,
) -> list[np.ndarray]:
    order = np.argsort(maturities)

    maturities = maturities[order]
    observed_mu = observed_mu[order]

    short_mu = float(observed_mu[0])
    long_mu = float(observed_mu[-1])

    beta0 = long_mu
    beta1 = short_mu - long_mu

    amplitude = max(
        float(np.ptp(observed_mu)),
        abs(float(np.mean(observed_mu))) * 0.10,
        0.01,
    )

    starts = []

    for tau1 in (
        0.25,
        0.50,
        1.00,
        1.50,
        2.00,
        3.00,
        5.00,
        10.00,
        20.00,
    ):
        for beta2 in (
            0.0,
            amplitude,
            -amplitude,
        ):
            starts.append(
                np.array(
                    [
                        beta0,
                        beta1,
                        beta2,
                        tau1,
                    ],
                    dtype=float,
                )
            )

    return starts


# ============================================================
# CURVE FITTING
# ============================================================

def fit_nss(
    maturities: np.ndarray,
    observed_mu: np.ndarray,
) -> tuple[np.ndarray, float]:
    """
    Fit the six-parameter Nelson-Siegel-Svensson model.
    """
    maturities = np.asarray(maturities, dtype=float)
    observed_mu = np.asarray(observed_mu, dtype=float)

    if len(observed_mu) < 6:
        raise ValueError(
            "NSS requires at least six valid maturity nodes."
        )

    scale = curve_scale(observed_mu)

    lower_bounds = np.array(
        [
            -10.0 * scale,
            -20.0 * scale,
            -20.0 * scale,
            -20.0 * scale,
            0.05,
            0.05,
        ],
        dtype=float,
    )

    upper_bounds = np.array(
        [
            10.0 * scale,
            20.0 * scale,
            20.0 * scale,
            20.0 * scale,
            50.0,
            50.0,
        ],
        dtype=float,
    )

    best_parameters = None
    best_sse = np.inf

    for start in nss_starting_parameters(
        maturities,
        observed_mu,
    ):
        start = np.clip(
            start,
            lower_bounds + 1e-10,
            upper_bounds - 1e-10,
        )

        result = least_squares(
            fun=nss_residuals,
            x0=start,
            bounds=(lower_bounds, upper_bounds),
            args=(maturities, observed_mu),
            loss="soft_l1",
            f_scale=max(scale * 0.01, 1e-6),
            max_nfev=300,
            xtol=1e-10,
            ftol=1e-10,
            gtol=1e-10,
        )

        if not result.success:
            continue

        residuals = nss_residuals(
            result.x,
            maturities,
            observed_mu,
        )

        sse = float(np.dot(residuals, residuals))

        if np.isfinite(sse) and sse < best_sse:
            best_sse = sse
            best_parameters = result.x.copy()

    if best_parameters is None:
        raise RuntimeError(
            "Nelson-Siegel-Svensson optimization failed."
        )

    rmse = float(
        np.sqrt(best_sse / len(observed_mu))
    )

    return best_parameters, rmse


def fit_ns(
    maturities: np.ndarray,
    observed_mu: np.ndarray,
) -> tuple[np.ndarray, float]:
    """
    Fit the four-parameter Nelson-Siegel model.
    """
    maturities = np.asarray(maturities, dtype=float)
    observed_mu = np.asarray(observed_mu, dtype=float)

    if len(observed_mu) < 4:
        raise ValueError(
            "Nelson-Siegel requires at least four valid maturity nodes."
        )

    scale = curve_scale(observed_mu)

    lower_bounds = np.array(
        [
            -10.0 * scale,
            -20.0 * scale,
            -20.0 * scale,
            0.05,
        ],
        dtype=float,
    )

    upper_bounds = np.array(
        [
            10.0 * scale,
            20.0 * scale,
            20.0 * scale,
            50.0,
        ],
        dtype=float,
    )

    best_parameters = None
    best_sse = np.inf

    for start in ns_starting_parameters(
        maturities,
        observed_mu,
    ):
        start = np.clip(
            start,
            lower_bounds + 1e-10,
            upper_bounds - 1e-10,
        )

        result = least_squares(
            fun=ns_residuals,
            x0=start,
            bounds=(lower_bounds, upper_bounds),
            args=(maturities, observed_mu),
            loss="soft_l1",
            f_scale=max(scale * 0.01, 1e-6),
            max_nfev=300,
            xtol=1e-10,
            ftol=1e-10,
            gtol=1e-10,
        )

        if not result.success:
            continue

        residuals = ns_residuals(
            result.x,
            maturities,
            observed_mu,
        )

        sse = float(np.dot(residuals, residuals))

        if np.isfinite(sse) and sse < best_sse:
            best_sse = sse
            best_parameters = result.x.copy()

    if best_parameters is None:
        raise RuntimeError(
            "Nelson-Siegel optimization failed."
        )

    rmse = float(
        np.sqrt(best_sse / len(observed_mu))
    )

    return best_parameters, rmse


# ============================================================
# ROW REPAIR
# ============================================================

def repair_mu_row(
    row: pd.Series,
) -> pd.Series:
    """
    Detect anomalies across all maturities, fit the curve to the
    valid nodes, and replace only the anomalous values.
    """
    output = row.copy()

    columns = list(MU_COLUMNS)
    maturities = np.array(
        [MU_COLUMNS[column] for column in columns],
        dtype=float,
    )

    values = pd.to_numeric(
        row[columns],
        errors="coerce",
    ).to_numpy(dtype=float)

    anomaly_mask = identify_anomalies(values)
    valid_mask = np.isfinite(values) & ~anomaly_mask

    anomalous_columns = [
        column
        for column, is_anomaly in zip(
            columns,
            anomaly_mask,
        )
        if is_anomaly
    ]

    # Audit columns
    output["curve_repair_performed"] = False
    output["curve_fit_success"] = False
    output["curve_model"] = ""
    output["curve_fit_rmse"] = np.nan
    output["anomaly_count"] = int(anomaly_mask.sum())
    output["anomalous_maturities"] = ",".join(
        anomalous_columns
    )

    for column in columns:
        output[f"{column}_original"] = values[
            columns.index(column)
        ]

        output[f"{column}_repaired"] = False

    # No explosion on this observation date.
    if not anomaly_mask.any():
        return output

    valid_maturities = maturities[valid_mask]
    valid_values = values[valid_mask]

    anomalous_maturities = maturities[anomaly_mask]

    try:
        if len(valid_values) >= 6:
            parameters, rmse = fit_nss(
                valid_maturities,
                valid_values,
            )

            reconstructed_values = nss_curve(
                anomalous_maturities,
                *parameters,
            )

            model_name = "NSS"

        elif len(valid_values) >= 4:
            parameters, rmse = fit_ns(
                valid_maturities,
                valid_values,
            )

            reconstructed_values = ns_curve(
                anomalous_maturities,
                *parameters,
            )

            model_name = "NS"

        else:
            raise ValueError(
                "Fewer than four valid maturity nodes remain. "
                "The curve cannot be identified."
            )

        anomaly_indices = np.flatnonzero(anomaly_mask)

        for index, reconstructed_value in zip(
            anomaly_indices,
            reconstructed_values,
        ):
            column = columns[index]

            if not np.isfinite(reconstructed_value):
                raise FloatingPointError(
                    f"Curve returned a nonfinite value for {column}."
                )

            output[column] = float(reconstructed_value)
            output[f"{column}_repaired"] = True

        output["curve_repair_performed"] = True
        output["curve_fit_success"] = True
        output["curve_model"] = model_name
        output["curve_fit_rmse"] = rmse

    except (
        ValueError,
        RuntimeError,
        FloatingPointError,
    ) as error:
        warnings.warn(
            f"Curve repair failed for "
            f"{row.get(DATE_COLUMN)}: {error}",
            RuntimeWarning,
        )

    return output


# ============================================================
# FILE PROCESSING
# ============================================================

def repair_mu_file(
    input_file: Path | str,
    output_file: Path | str,
) -> pd.DataFrame:
    input_file = Path(input_file)
    output_file = Path(output_file)

    dataframe = pd.read_csv(
        input_file,
        dtype={DATE_COLUMN: str},
    )

    required_columns = [
        DATE_COLUMN,
        *MU_COLUMNS.keys(),
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise KeyError(
            "Input file is missing required columns: "
            + ", ".join(missing_columns)
        )

    for column in MU_COLUMNS:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    columns = list(MU_COLUMNS)
    mu_values = dataframe[columns].to_numpy(dtype=float)
    # Submit only rows containing finite exploded values. Missing historical
    # maturities are excluded from fitting but are not treated as repair targets.
    anomaly_matrix = (
        np.isfinite(mu_values)
        & (np.abs(mu_values) > EXPLOSION_ABS_THRESHOLD)
    )
    anomalous_positions = np.flatnonzero(anomaly_matrix.any(axis=1))
    anomalous_position_set = set(anomalous_positions.tolist())
    total_rows = len(dataframe)
    anomaly_total = len(anomalous_positions)

    print(
        f"Scanned {total_rows:,} observation dates; "
        f"found {anomaly_total:,} anomalous dates.",
        flush=True,
    )

    # Normal rows require no nonlinear optimization and are handled locally.
    repaired_rows = [None] * total_rows
    for position in range(total_rows):
        if position not in anomalous_position_set:
            repaired_rows[position] = repair_mu_row(dataframe.iloc[position].copy())

    if anomaly_total:
        worker_count = min(MAX_WORKERS, anomaly_total)
        print(
            f"Repairing {anomaly_total:,} anomalous dates "
            f"using {worker_count} workers...",
            flush=True,
        )

        context = mp.get_context("spawn")

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=context,
        ) as executor:
            future_to_position = {
                executor.submit(
                    repair_mu_row,
                    dataframe.iloc[position].copy(),
                ): int(position)
                for position in anomalous_positions
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_position):
                position = future_to_position[future]
                repaired_rows[position] = future.result()
                completed += 1

                if (
                    completed == 1
                    or completed % 25 == 0
                    or completed == anomaly_total
                ):
                    print(
                        f"Completed {completed:,}/{anomaly_total:,} "
                        "anomalous dates",
                        flush=True,
                    )

    repaired_dataframe = pd.DataFrame(repaired_rows)
    repaired_dataframe = repaired_dataframe.reindex(
        columns=repaired_rows[0].index
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    repaired_dataframe.to_csv(
        output_file,
        index=False,
    )

    return repaired_dataframe


def main() -> None:
    repaired = repair_mu_file(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE,
    )

    anomaly_rows = repaired[
        repaired["anomaly_count"] > 0
    ]

    successful_rows = anomaly_rows[
        anomaly_rows["curve_fit_success"]
    ]

    failed_rows = anomaly_rows[
        ~anomaly_rows["curve_fit_success"]
    ]

    total_repaired_nodes = sum(
        int(repaired[f"{column}_repaired"].sum())
        for column in MU_COLUMNS
    )

    # print(f"Input:  {INPUT_FILE.resolve()}")
    # print(f"Output: {OUTPUT_FILE.resolve()}")
    print(f"Observation dates: {len(repaired):,}")
    print(f"Dates containing anomalies: {len(anomaly_rows):,}")
    print(f"Successfully repaired dates: {len(successful_rows):,}")
    print(f"Failed repair dates: {len(failed_rows):,}")
    print(f"Individual mu nodes repaired: {total_repaired_nodes:,}")

    if len(anomaly_rows) > 0:
        print("\nModels used:")
        print(
            successful_rows["curve_model"]
            .value_counts()
            .to_string()
        )

    if len(failed_rows) > 0:
        print("\nFailed dates:")
        print(
            failed_rows[
                [
                    DATE_COLUMN,
                    "anomaly_count",
                    "anomalous_maturities",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()