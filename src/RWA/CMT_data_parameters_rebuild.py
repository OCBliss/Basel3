import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import importlib.util
import pandas as pd


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
# INPUT AND OUTPUT DIRECTORIES
###############################################################################

DGS_RAW_DIR = os.path.join(
    ROOT_DIR,
    "RWA",
    "Experimental",
    "MLE YIELD",
    "RAW"
)

MU_REPAIRED_FILE = os.path.join(
    ROOT_DIR,
    "RWA",
    "Experimental",
    "MLE YIELD",
    "NSS",
    "mu_curve_nss_repaired.csv"
)

THETA_REPAIRED_FILE = os.path.join(
    ROOT_DIR,
    "RWA",
    "Experimental",
    "MLE YIELD",
    "NSS",
    "theta_curve_nss_repaired.csv"
)

SIGMA_CURVE_FILE = os.path.join(
    ROOT_DIR,
    "RWA",
    "Experimental",
    "MLE YIELD",
    "CURVE",
    "sigma_curve.csv"
)

MLE_VOL_RAW_DIR = os.path.join(
    ROOT_DIR,
    "RWA",
    "Experimental",
    "MLE VOL",
    "RAW"
)


###############################################################################
# MATURITY MAPPING
###############################################################################

MATURITY_MAP = {
    "DGS1": {
        "mu": "mu1y",
        "theta": "theta1y",
        "sigma": "sigma1y"
    },
    "DGS2": {
        "mu": "mu2y",
        "theta": "theta2y",
        "sigma": "sigma2y"
    },
    "DGS3": {
        "mu": "mu3y",
        "theta": "theta3y",
        "sigma": "sigma3y"
    },
    "DGS5": {
        "mu": "mu5y",
        "theta": "theta5y",
        "sigma": "sigma5y"
    },
    "DGS7": {
        "mu": "mu7y",
        "theta": "theta7y",
        "sigma": "sigma7y"
    },
    "DGS10": {
        "mu": "mu10y",
        "theta": "theta10y",
        "sigma": "sigma10y"
    },
    "DGS20": {
        "mu": "mu20y",
        "theta": "theta20y",
        "sigma": "sigma20y"
    },
    "DGS30": {
        "mu": "mu30y",
        "theta": "theta30y",
        "sigma": "sigma30y"
    }
}


###############################################################################
# VALIDATION FUNCTIONS
###############################################################################

def require_file(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"Required file does not exist:\n{file_path}"
        )


def require_columns(
    df,
    required_columns,
    file_path
):
    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns in {file_path}:\n"
            f"{missing_columns}"
        )


def prepare_curve_file(
    file_path,
    parameter_columns
):
    require_file(file_path)

    df = pd.read_csv(file_path)

    require_columns(
        df,
        ["observation_date"] + parameter_columns,
        file_path
    )

    df["observation_date"] = pd.to_datetime(
        df["observation_date"],
        errors="raise"
    )

    if df["observation_date"].duplicated().any():
        duplicate_dates = df.loc[
            df["observation_date"].duplicated(
                keep=False
            ),
            "observation_date"
        ]

        raise ValueError(
            f"Duplicate observation dates found in:\n"
            f"{file_path}\n"
            f"{duplicate_dates.head(10).tolist()}"
        )

    return df[
        ["observation_date"] + parameter_columns
    ].copy()


###############################################################################
# LOAD PARAMETER CURVES
###############################################################################

def load_parameter_curves():
    mu_columns = [
        mapping["mu"]
        for mapping in MATURITY_MAP.values()
    ]

    theta_columns = [
        mapping["theta"]
        for mapping in MATURITY_MAP.values()
    ]

    sigma_columns = [
        mapping["sigma"]
        for mapping in MATURITY_MAP.values()
    ]

    print(
        f"Reading repaired mu curve:\n"
        f"{MU_REPAIRED_FILE}"
    )

    mu_curve = prepare_curve_file(
        MU_REPAIRED_FILE,
        mu_columns
    )

    print(
        f"Reading repaired theta curve:\n"
        f"{THETA_REPAIRED_FILE}"
    )

    theta_curve = prepare_curve_file(
        THETA_REPAIRED_FILE,
        theta_columns
    )

    print(
        f"Reading sigma curve:\n"
        f"{SIGMA_CURVE_FILE}"
    )

    sigma_curve = prepare_curve_file(
        SIGMA_CURVE_FILE,
        sigma_columns
    )

    return (
        mu_curve,
        theta_curve,
        sigma_curve
    )


###############################################################################
# REBUILD ONE DGS FILE
###############################################################################

def rebuild_dgs_file(
    dgs_name,
    parameter_mapping,
    mu_curve,
    theta_curve,
    sigma_curve
):
    input_file = os.path.join(
        DGS_RAW_DIR,
        f"{dgs_name}_with_parameters.csv"
    )

    output_file = os.path.join(
        MLE_VOL_RAW_DIR,
        f"{dgs_name}_with_parameters.csv"
    )

    require_file(input_file)

    print(
        f"\nRebuilding {dgs_name}:\n"
        f"Input:  {input_file}\n"
        f"Output: {output_file}"
    )

    dgs_df = pd.read_csv(input_file)

    require_columns(
        dgs_df,
        [
            "observation_date",
            dgs_name,
            "yield_clean"
        ],
        input_file
    )

    # Keep only the original market-data columns.
    # Old theta, mu, and sigma columns are intentionally discarded.
    dgs_df = dgs_df[
        [
            "observation_date",
            dgs_name,
            "yield_clean"
        ]
    ].copy()

    dgs_df["observation_date"] = pd.to_datetime(
        dgs_df["observation_date"],
        errors="raise"
    )

    if dgs_df["observation_date"].duplicated().any():
        duplicate_dates = dgs_df.loc[
            dgs_df["observation_date"].duplicated(
                keep=False
            ),
            "observation_date"
        ]

        raise ValueError(
            f"Duplicate observation dates found in:\n"
            f"{input_file}\n"
            f"{duplicate_dates.head(10).tolist()}"
        )

    # Preserve the input row order through the merges.
    dgs_df["_original_row_order"] = range(
        len(dgs_df)
    )

    mu_column = parameter_mapping["mu"]
    theta_column = parameter_mapping["theta"]
    sigma_column = parameter_mapping["sigma"]

    maturity_mu = mu_curve[
        [
            "observation_date",
            mu_column
        ]
    ].rename(
        columns={
            mu_column: "mu"
        }
    )

    maturity_theta = theta_curve[
        [
            "observation_date",
            theta_column
        ]
    ].rename(
        columns={
            theta_column: "theta"
        }
    )

    maturity_sigma = sigma_curve[
        [
            "observation_date",
            sigma_column
        ]
    ].rename(
        columns={
            sigma_column: "sigma"
        }
    )

    rebuilt = dgs_df.merge(
        maturity_theta,
        on="observation_date",
        how="left",
        validate="one_to_one"
    )

    rebuilt = rebuilt.merge(
        maturity_mu,
        on="observation_date",
        how="left",
        validate="one_to_one"
    )

    rebuilt = rebuilt.merge(
        maturity_sigma,
        on="observation_date",
        how="left",
        validate="one_to_one"
    )

    rebuilt = rebuilt.sort_values(
        "_original_row_order"
    ).reset_index(
        drop=True
    )

    missing_theta = int(
        rebuilt["theta"].isna().sum()
    )

    missing_mu = int(
        rebuilt["mu"].isna().sum()
    )

    missing_sigma = int(
        rebuilt["sigma"].isna().sum()
    )

    print(
        f"{dgs_name} parameter matches:\n"
        f"  theta missing: {missing_theta}\n"
        f"  mu missing:    {missing_mu}\n"
        f"  sigma missing: {missing_sigma}"
    )

    rebuilt = rebuilt[
        [
            "observation_date",
            dgs_name,
            "yield_clean",
            "theta",
            "mu",
            "sigma"
        ]
    ].copy()

    rebuilt["observation_date"] = (
        rebuilt["observation_date"]
        .dt.strftime("%Y-%m-%d")
    )

    rebuilt.to_csv(
        output_file,
        index=False
    )

    print(
        f"Saved {len(rebuilt):,} rows."
    )


###############################################################################
# MAIN
###############################################################################

def main():
    require_file(MU_REPAIRED_FILE)
    require_file(THETA_REPAIRED_FILE)
    require_file(SIGMA_CURVE_FILE)

    os.makedirs(
        MLE_VOL_RAW_DIR,
        exist_ok=True
    )

    (
        mu_curve,
        theta_curve,
        sigma_curve
    ) = load_parameter_curves()

    for dgs_name, parameter_mapping in (
        MATURITY_MAP.items()
    ):
        rebuild_dgs_file(
            dgs_name=dgs_name,
            parameter_mapping=parameter_mapping,
            mu_curve=mu_curve,
            theta_curve=theta_curve,
            sigma_curve=sigma_curve
        )

    print(
        f"\nAll rebuilt DGS parameter files "
        f"were saved to:\n{MLE_VOL_RAW_DIR}"
    )


if __name__ == "__main__":
    main()