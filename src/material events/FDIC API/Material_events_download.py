import argparse
import requests
import pandas as pd
import os
import sys
from pathlib import Path
sys.stdout.reconfigure(line_buffering=True)
import numpy as np


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

import Basel3_Global_Filepath as paths

ROOT_DIR = paths.BASEL3_ROOT
CALL_DIR = paths.CALL_DIR
MAT_DIR = paths.MAT_DIR

EVENTS = {
    "de_novo": {
        "folder": "DE NOVO",
        "filename": "BankFind Suite API - de novo.csv",
        "saved_message": "✅ CSV saved as 'BankFind Suite API - de novo.csv'",
        "change_codes": [110],
        "fields": [
            "ACQDATE", "ACQYEAR", "CERT", "CHANGECODE_DESC", "CHANGECODE_DESC_LONG", "CHARTAGENT",
            "CLASS", "CLASS_TYPE", "CLCODE", "EFFDATE", "ESTDATE", "FDICREGION", "FDICREGION_DESC",
            "FRM_CLASS", "FRM_INSAGENT1", "FRM_REGAGENT", "ID", "INSAGENT1", "INSTNAME",
            "NEW_CHARTER_DENOVO_FLAG", "NEW_CHARTER_FLAG", "ORGTYPE", "ORGTYPE_NUM",
            "REGAGENT", "REPORT_TYPE"
        ],
    },
    "failures": {
        "folder": "Failures",
        "filename": "BankFind Suite API - Failures.csv",
        "saved_message": "✅ CSV saved as 'BankFind Suite API - failures.csv'",
        "change_codes": [211],
        "fields": [
            "ACQ_BRANCHES", "ACQ_CERT", "ACQ_CHARTAGENT", "ACQ_CLASS", "ACQ_CLASS_TYPE_DESC",
            "ACQ_INSAGENT1", "ACQ_INSTNAME", "ACQ_ORG_EFF_DTE", "ACQ_REGAGENT", "CHANGECODE",
            "CHANGECODE_DESC", "CLASS", "EFFDATE", "ESTDATE", "FDICREGION", "FDICREGION_DESC",
            "FRM_CLASS", "FRM_INSAGENT1", "FRM_REGAGENT", "ID", "INSAGENT1", "OUT_CHARTAGENT",
            "OUT_CLASS", "OUT_FDICREGION", "OUT_FDICREGION_DESC", "OUT_INSAGENT1",
            "NEW_CHARTER_DENOVO_FLAG", "NEW_CHARTER_FLAG", "REGAGENT"
        ],
    },
    "mergers": {
        "folder": "Mergers",
        "filename": "BankFind Suite API - mergers.csv",
        "saved_message": "✅ CSV saved as 'BankFind Suite API - mergers.csv'",
        "change_codes": [221, 222, 223, 224],
        "fields": [
            "ACQ_BRANCHES", "ACQ_CERT", "ACQ_CHARTAGENT", "ACQ_CLASS", "ACQ_CLASS_TYPE_DESC",
            "ACQ_FDICREGION", "ACQ_FDICREGION_DESC",
            "ACQ_INSAGENT1", "ACQ_INSTNAME", "ACQ_ORG_EFF_DTE", "ACQ_REGAGENT", "CHANGECODE",
            "CHANGECODE_DESC", "CLASS", "EFFDATE", "ESTDATE", "FDICREGION", "FDICREGION_DESC",
            "FRM_CLASS", "FRM_INSAGENT1", "FRM_REGAGENT", "ID", "INSAGENT1", "OUT_CHARTAGENT",
            "OUT_CLASS", "OUT_FDICREGION", "OUT_FDICREGION_DESC", "OUT_INSAGENT1",
            "NEW_CHARTER_DENOVO_FLAG", "NEW_CHARTER_FLAG", "REGAGENT"
        ],
    },
}


def fetch_fdic_history(start_date, end_date, change_codes, fields, limit=10000):
    base_url = "https://banks.data.fdic.gov/api/history"

    code_clause = " OR ".join(f"CHANGECODE:{code}" for code in change_codes)
    filter_string = f"EFFDATE:[{start_date} TO {end_date}] AND ({code_clause})"

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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Download FDIC material-event history.")
    parser.add_argument("--events", nargs="+", choices=list(EVENTS), required=True)
    parser.add_argument("--material-dir", type=Path, default=Path(paths.MAT_DIR))
    parser.add_argument("--start-date", default="2014-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--limit", type=int, default=10000)
    return parser.parse_args(argv)


def run_downloads(args):

    for event in args.events:
        config = EVENTS[event]
        output_dir = os.path.join(args.material_dir, config["folder"], "RAW")
        os.makedirs(output_dir, exist_ok=True)
        df = fetch_fdic_history(
            args.start_date,
            args.end_date,
            change_codes=config["change_codes"],
            fields=config["fields"],
            limit=args.limit,
        )
        if df is not None:
            output_path = os.path.join(output_dir, config["filename"])
            df.to_csv(output_path, index=False)
            print(config["saved_message"])
            print("📋 Columns in final file:", df.columns.tolist())
    return 0


def main(argv=None):
    return run_downloads(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
