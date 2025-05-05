import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import numpy as np
import csv
import importlib.util
import re

# Directories
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))  # Start from script's directory
    while current_dir and os.path.basename(current_dir) != "CODE":  # Traverse up until "CODE" is found
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Stop if we reach the root directory
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir  # Now 'CODE' directory is located

# Step 2: Locate CODE and Add to sys.path
CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)  # Ensure CODE directory is in the import path

# Step 3: Import Basel3_Global_Filepath Dynamically
filepath = os.path.join(CODE_DIR, "Basel3_Global_Filepath.py")
spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
paths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paths)

# Step 4: Use the Dynamically Determined ROOT_DIR
ROOT_DIR = paths.BASEL3_ROOT  # Basel3 root directory (dynamically set)
CALL_DIR = os.path.join(ROOT_DIR, "Call Report")
MAT_DIR = os.path.join(ROOT_DIR, "Material Events")
process_directory = os.path.join(MAT_DIR, "DE NOVO/Call Reports")
failures_directory = os.path.join(MAT_DIR, "Failures/Cleaned")
financial_quarter_file = os.path.join(MAT_DIR, "quarters_failures.csv")
output_directory = os.path.join(MAT_DIR, "Failures/Call Reports")

# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)

# Load Mergers and Financial Quarters data
mergers_files = [os.path.join(failures_directory, file) for file in os.listdir(failures_directory) if file.endswith('.csv')]
if not mergers_files:
    raise FileNotFoundError("No Mergers files found in the directory.")

mergers_data = pd.concat([pd.read_csv(file) for file in mergers_files])
quarters_data = pd.read_csv(financial_quarter_file)

# Standardize CERT formatting
mergers_data['CERT'] = mergers_data['CERT'].astype(float).astype(int).astype(str)
quarters_data['Quarters'] = quarters_data['Quarters'].astype(str)

# Convert EFFDATE from ISO 8601 to YYYYMMDD (as integers for comparison)
if 'EFFDATE' in mergers_data.columns:
    mergers_data['EFFDATE'] = pd.to_datetime(mergers_data['EFFDATE'], format='%Y-%m-%dT%H:%M:%S').dt.strftime('%Y%m%d').astype(int)

# Convert START_DATE, END_DATE, and Quarters to integers
quarters_data['START_DATE'] = quarters_data['START_DATE'].astype(int)
quarters_data['END_DATE1'] = quarters_data['END_DATE1'].astype(int)
quarters_data['END_DATE2'] = quarters_data['END_DATE2'].astype(int)
quarters_data['END_DATE3'] = quarters_data['END_DATE3'].astype(int)
quarters_data['END_DATE4'] = quarters_data['END_DATE4'].astype(int)

# Process each file in the process directory
processed_files = []
csv_files = [file for file in os.listdir(process_directory) if file.endswith('.csv') and 'DE NOVO_' in file]

if not csv_files:
    print(f"No CSV files found in {process_directory}.")
else:
    for file in csv_files:
        input_file_path = os.path.join(process_directory, file)
        data = pd.read_csv(input_file_path)

        # Standardize CERT formatting in the process file
        data['CERT'] = data['CERT'].astype(float).astype(int).astype(str)
        data['RCON9999'] = data['RCON9999'].astype(int)

        # Add MERGER T+1, MERGER T+2, MERGER T+3, MERGER T+4 columns
        data['FAILURE_T1'] = 0
        data['FAILURE_T2'] = 0
        data['FAILURE_T3'] = 0
        data['FAILURE_T4'] = 0

        # Loop through rows in the process_directory file
        for index, row in data.iterrows():
            cert_value = row['CERT']
            rcon9999_value = row['RCON9999']

            # Debug CERT and RCON9999
            # print(f"Processing Row {index}: CERT={cert_value}, RCON9999={rcon9999_value}")

            # Find matching CERT in mergers data
            mergers_cert_matches = mergers_data[mergers_data['CERT'] == cert_value]
            # print(f"MERGER Matches for CERT={cert_value}:\n{mergers_cert_matches}")

            if not mergers_cert_matches.empty:
                for _, mergers_row in mergers_cert_matches.iterrows():
                    effdate = mergers_row['EFFDATE']  # Already converted to integer

                    # Debug EFFDATE
                    # print(f"EFFDATE for CERT={cert_value}: {effdate}")

                    # Find matching Quarters value in quarters_failures.csv
                    quarter_match = quarters_data[quarters_data['Quarters'].astype(int) == rcon9999_value]
                    # print(f"Quarter Matches for RCON9999={rcon9999_value}:\n{quarter_match}")

                    if not quarter_match.empty:
                        for _, quarter_row in quarter_match.iterrows():
                            start_date = quarter_row['START_DATE']
                            end_date1 = quarter_row['END_DATE1']
                            end_date2 = quarter_row['END_DATE2']
                            end_date3 = quarter_row['END_DATE3']
                            end_date4 = quarter_row['END_DATE4']

                            # Debug Date Ranges
                            # print(
                            #     f"START_DATE={start_date}, END_DATE1={end_date1}, END_DATE2={end_date2}, "
                            #     f"END_DATE3={end_date3}, END_DATE4={end_date4}"
                            # )

                            # Compare EFFDATE with START_DATE and END_DATE ranges
                            if pd.notna(effdate):
                                if start_date <= effdate <= end_date1:
                                    # print(f"EFFDATE={effdate} is within START_DATE={start_date} and END_DATE1={end_date1}")
                                    data.at[index, 'FAILURE_T1'] = 1
                                if start_date <= effdate <= end_date2:
                                    # print(f"EFFDATE={effdate} is within START_DATE={start_date} and END_DATE2={end_date2}")
                                    data.at[index, 'FAILURE_T2'] = 1
                                if start_date <= effdate <= end_date3:
                                    # print(f"EFFDATE={effdate} is within START_DATE={start_date} and END_DATE3={end_date3}")
                                    data.at[index, 'FAILURE_T3'] = 1
                                if start_date <= effdate <= end_date4:
                                    # print(f"EFFDATE={effdate} is within START_DATE={start_date} and END_DATE4={end_date4}")
                                    data.at[index, 'FAILURE_T4'] = 1

        # Save the processed file
        output_filename = re.sub(r"(?i)DE NOVO_", "Failures_", os.path.basename(file))
        output_file_path = os.path.join(output_directory, output_filename)
        data.to_csv(output_file_path, index=False)
        processed_files.append(output_file_path)
        print(f"Processed {file} and saved to {output_file_path}.")

# Print summary
print(f"Processed files: {processed_files}")
