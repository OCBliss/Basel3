import requests
import pandas as pd
import os
import sys
sys.stdout.reconfigure(line_buffering=True)
import importlib.util
import numpy as np

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
OUTPUT_DIR = os.path.join(ROOT_DIR, "Material Events", "Mergers", "RAW")

def fetch_fdic_history(start_date, end_date, change_codes, limit=10000):
    base_url = "https://banks.data.fdic.gov/api/history"

    code_clause = " OR ".join(f"CHANGECODE:{code}" for code in change_codes)
    filter_string = f"EFFDATE:[{start_date} TO {end_date}] AND ({code_clause})"

    # All possible fields (even if sparse)
    fields = [
        "ACQ_BRANCHES", "ACQ_CERT", "ACQ_CHARTAGENT", "ACQ_CLASS", "ACQ_CLASS_TYPE_DESC", 
        "ACQ_FDICREGION", "ACQ_FDICREGION_DESC", 
        "ACQ_INSAGENT1", "ACQ_INSTNAME", "ACQ_ORG_EFF_DTE", "ACQ_REGAGENT", "CHANGECODE", 
        "CHANGECODE_DESC", "CLASS", "EFFDATE", "ESTDATE", "FDICREGION", "FDICREGION_DESC", 
        "FRM_CLASS", "FRM_INSAGENT1", "FRM_REGAGENT", "ID", "INSAGENT1", "OUT_CHARTAGENT", 
        "OUT_CLASS", "OUT_FDICREGION", "OUT_FDICREGION_DESC", "OUT_INSAGENT1", 
        "NEW_CHARTER_DENOVO_FLAG", "NEW_CHARTER_FLAG", "REGAGENT"
    ]

    params = {
        "filters": filter_string,
        "fields": ",".join(fields),
        "sort_by": "EFFDATE",
        "sort_order": "DESC",
        "limit": limit,
        "format": "json"
    }

    print("🔍 Sending filters:", params["filters"])
    response = requests.get(base_url, params=params)

    print("HTTP STATUS:", response.status_code)
    if response.status_code != 200:
        print("❌ Server error:")
        print(response.text)
        return None

    json_data = response.json()
    if 'data' not in json_data:
        print("❌ Unexpected response structure")
        return None

    # Flatten each row's data + metadata
    records = []
    for row in json_data["data"]:
        combined = {}
        if "data" in row:
            combined.update(row["data"])
        for k, v in row.items():
            if k != "data":
                combined[k] = v
        records.append(combined)

    df = pd.DataFrame(records)

    # Add missing columns with None
    for col in fields:
        if col not in df.columns:
            df[col] = None

    # Add ESTYEAR derived from ESTDATE if present
    if "ESTDATE" in df.columns:
        df["ESTYEAR"] = pd.to_datetime(df["ESTDATE"], errors='coerce').dt.year

    # Final column order
    desired_columns = fields.copy()
    if "ESTYEAR" not in desired_columns:
        desired_columns.append("ESTYEAR")

    df = df[desired_columns]

    return df

# Save to CSV
if __name__ == "__main__":
    df = fetch_fdic_history("2014-01-01", "2024-12-31", change_codes=[221, 222, 223, 224])
    if df is not None:
        output_path = os.path.join(OUTPUT_DIR, "BankFind Suite API - mergers.csv")
        df.to_csv(output_path, index=False)
        print("✅ CSV saved as 'BankFind Suite API - mergers.csv'")
        print("📋 Columns in final file:", df.columns.tolist())