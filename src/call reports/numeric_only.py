import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import sys
import pandas as pd
import csv
import importlib.util

# Step 1: Locate CODE directory FIRST
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

# NOW import
import Basel3_Global_Filepath as paths

ROOT_DIR = paths.BASEL3_ROOT
CALL_DIR = paths.CALL_DIR

CSV_DIR = paths.CSV_DIR
cleaned_directory = paths.CLEANED_DIR

# Iterate through each file in the directory
for filename in os.listdir(cleaned_directory):
    # Only process files that start with 'Cleaned_Call_Report_' and end with .csv
    if filename.startswith('Cleaned_Call_Report_') and filename.endswith('.csv'):
        file_path = os.path.join(cleaned_directory, filename)
        
        # Extract the numerical date part from the filename
        date_value = int(filename.split('_')[-1].split('.')[0])
        
        # Read the file into a DataFrame with low_memory=False
        try:
            df = pd.read_csv(file_path, low_memory=False)
        except Exception as e:
            print(f"Error reading file {filename}: {e}")
            continue
        
        # Remove the column 'RCON9224' if it exists
        if 'RCON9224' in df.columns:
            df.drop(columns=['RCON9224'], inplace=True)
            print(f"'RCON9224' column removed from {filename}.")
        
        # Overwrite the RCON9999 column with the date_value
        if 'RCON9999' in df.columns:
            df['RCON9999'] = date_value
        else:
            print(f"'RCON9999' column not found in {filename}. Skipping file.")
            continue
        
        # Save the updated DataFrame back to the file
        try:
            df.to_csv(file_path, index=False)
            print(f"Processed and updated file: {filename}")
        except Exception as e:
            print(f"Error saving file {filename}: {e}")
