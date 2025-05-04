import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import numpy as np
import csv
import importlib.util
import re

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
process_directory = os.path.join(CALL_DIR, "CSV/Dynamic_Lag/Cleaned")
de_novo_directory = os.path.join(MAT_DIR, "DE NOVO/Cleaned")
financial_quarter_file = os.path.join(MAT_DIR, "quarters_de_novo.csv")
output_directory = os.path.join(MAT_DIR, "DE NOVO/Call Reports")

# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)

# Load DE NOVO and Financial Quarters data
de_novo_files = [os.path.join(de_novo_directory, file) for file in os.listdir(de_novo_directory) if file.endswith('.csv')]
if not de_novo_files:
    raise FileNotFoundError("No DE NOVO files found in the directory.")

de_novo_data = pd.concat([pd.read_csv(file) for file in de_novo_files])
quarters_data = pd.read_csv(financial_quarter_file)

# Ensure consistent types
quarters_data['Quarters'] = quarters_data['Quarters'].astype(str)
de_novo_data['CERT'] = de_novo_data['CERT'].astype(str)

# Convert START_DATE and END_DATE to string format YYYYMMDD
quarters_data['START_DATE'] = quarters_data['START_DATE'].astype(str)
quarters_data['END_DATE'] = quarters_data['END_DATE'].astype(str)

# Convert ESTDATE from ISO 8601 to YYYYMMDD
if 'ESTDATE' in de_novo_data.columns:
    de_novo_data['ESTDATE'] = pd.to_datetime(de_novo_data['ESTDATE'], format='%Y-%m-%dT%H:%M:%S').dt.strftime('%Y%m%d')

# Process each file in the process directory
processed_files = []
csv_files = [file for file in os.listdir(process_directory) if file.endswith('.csv')]

if not csv_files:
    print(f"No CSV files found in {process_directory}.")
else:
    for file in csv_files:
        input_file_path = os.path.join(process_directory, file)
        data = pd.read_csv(input_file_path)
        data['CERT'] = data['CERT'].astype(str)
        data['RCON9999'] = data['RCON9999'].astype(str)

        # Add the DE_NOVO_FLAG column
        data['DE_NOVO_FLAG'] = 0  # Default to 0

        # Loop through rows in the process_directory file
        for index, row in data.iterrows():
            cert_value = row['CERT']
            rcon9999_value = row['RCON9999']

            # Find matching CERT in DE NOVO data
            de_novo_cert_matches = de_novo_data[de_novo_data['CERT'] == cert_value]
            if not de_novo_cert_matches.empty:
                for _, de_novo_row in de_novo_cert_matches.iterrows():
                    estdate = de_novo_row['ESTDATE']  # Already in YYYYMMDD format

                    # Find matching Quarters value in financial_quarter_file
                    quarter_match = quarters_data[quarters_data['Quarters'] == rcon9999_value]
                    if not quarter_match.empty:
                        for _, quarter_row in quarter_match.iterrows():
                            start_date = quarter_row['START_DATE']
                            end_date = quarter_row['END_DATE']

                            # Compare ESTDATE with START_DATE and END_DATE
                            if pd.notna(estdate) and start_date <= estdate <= end_date:
                                data.at[index, 'DE_NOVO_FLAG'] = 1
                                break  # No need to check further once a match is found

        # Save the processed file
        output_filename = re.sub(r"(?i)DDRL_", "DE NOVO_", os.path.basename(file))
        output_file_path = os.path.join(output_directory, output_filename)
        data.to_csv(output_file_path, index=False)
        processed_files.append(output_file_path)
        print(f"Processed {file} and saved to {output_file_path}.")

# Print summary
print(f"Processed files: {processed_files}")
