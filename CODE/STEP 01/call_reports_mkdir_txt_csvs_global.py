import sys
sys.stdout.reconfigure(line_buffering=True)
import os
import csv
import importlib.util

# Locate Basel3_Global_Filepath.py
def find_global_filepath():
    for root, _, files in os.walk(os.path.abspath(os.sep)):
        if "Basel3_Global_Filepath.py" in files:
            return os.path.join(root, "Basel3_Global_Filepath.py")
    raise FileNotFoundError("Could not locate 'Basel3_Global_Filepath.py' on the system.")

global_filepath_path = find_global_filepath()

# Load Basel3_Global_Filepath.py dynamically
def load_global_filepath(filepath):
    spec = importlib.util.spec_from_file_location("Basel3_Global_Filepath", filepath)
    global_filepath = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(global_filepath)
    return global_filepath

# Load the filepath module and get ROOT_DIR
global_filepath = load_global_filepath(global_filepath_path)
ROOT_DIR = global_filepath.ROOT_DIR

# Define dynamic directories
TXT_DIR = os.path.join(ROOT_DIR, "Call Report/TXT")
CSV_DIR = os.path.join(ROOT_DIR, "Call Report/CSV")

# Ensure directories exist
os.makedirs(TXT_DIR, exist_ok=True)
os.makedirs(CSV_DIR, exist_ok=True)

# Function to batch process TXT to CSV
def batch_process_txt_to_csv(delimiter='\t'):
    """
    Converts all .txt files in subdirectories of the TXT_DIR to .csv files.
    Creates a "Schedules" folder in the CSV_DIR and subdirectories within it,
    using only the date portion of the folder name. Appends FDIC Certificate Number
    from the POR file to all other CSVs using IDRSSD as the key.

    Parameters:
    - delimiter: The delimiter used in the .txt files (default is tab-delimited).
    """
    # Create the "Schedules" folder inside the CSV directory
    schedules_directory = os.path.join(CSV_DIR, "Schedules")
    os.makedirs(schedules_directory, exist_ok=True)

    for subdirectory_name in os.listdir(TXT_DIR):
        subdirectory_path = os.path.join(TXT_DIR, subdirectory_name)

        if os.path.isdir(subdirectory_path):  # Only process subdirectories
            # Extract the date portion of the folder name (assumes it is the last part)
            date_portion = subdirectory_name.split()[-1]

            # Create a corresponding directory in the "Schedules" folder using only the date portion
            destination_subdirectory = os.path.join(schedules_directory, date_portion)
            os.makedirs(destination_subdirectory, exist_ok=True)

            # Identify the POR file and build the IDRSSD -> FDIC Certificate Number mapping
            idrssd_to_fdic = {}
            por_file_path = None
            for file_name in os.listdir(subdirectory_path):
                if file_name.startswith("FFIEC CDR Call Bulk POR") and file_name.endswith('.txt'):
                    por_file_path = os.path.join(subdirectory_path, file_name)
                    break

            if por_file_path:
                try:
                    # Read the POR file and build the mapping
                    with open(por_file_path, 'r') as por_file:
                        reader = csv.reader(por_file, delimiter=delimiter)
                        header = next(reader)  # Skip header
                        for row in reader:
                            if row and len(row) >= 2:
                                idrssd = row[0].strip()  # First column: IDRSSD
                                fdic_number = row[1].strip()  # Second column: FDIC Certificate Number
                                idrssd_to_fdic[idrssd] = fdic_number
                except Exception as e:
                    print(f"Failed to read POR file {por_file_path}: {e}")

            # If no mapping was built, skip processing this subfolder
            if not idrssd_to_fdic:
                print(f"No valid IDRSSD -> FDIC mapping found in {por_file_path}, skipping subfolder {subdirectory_name}.")
                continue

            # Process other .txt files in the current subdirectory
            for file_name in os.listdir(subdirectory_path):
                if file_name.endswith('.txt') and not file_name.startswith("FFIEC CDR Call Bulk POR"):
                    txt_file_path = os.path.join(subdirectory_path, file_name)
                    csv_file_name = os.path.splitext(file_name)[0] + '.csv'
                    csv_file_path = os.path.join(destination_subdirectory, csv_file_name)

                    try:
                        # Read the .txt file, map IDRSSD to FDIC Certificate Number, and append FDIC data
                        with open(txt_file_path, 'r') as txt_file:
                            reader = csv.reader(txt_file, delimiter=delimiter)
                            rows = []
                            header = next(reader)  # Extract header
                            header.insert(1, "FDIC Certificate Number")  # Add FDIC Certificate Number column
                            rows.append(header)

                            for row in reader:
                                if row and row[0].strip():  # Ensure the row is not empty and first column is not blank
                                    idrssd = row[0].strip()
                                    fdic_number = idrssd_to_fdic.get(idrssd, "")  # Get FDIC Number or empty if not found
                                    row.insert(1, fdic_number)  # Insert FDIC Certificate Number
                                    rows.append(row)

                        # Write the modified rows to the .csv file
                        with open(csv_file_path, 'w', newline='') as csv_file:
                            writer = csv.writer(csv_file)
                            writer.writerows(rows)

                        print(f"Converted and updated: {txt_file_path} -> {csv_file_path}")
                    except Exception as e:
                        print(f"Failed to process {file_name} in subfolder {subdirectory_name}: {e}")

# Run the batch conversion using dynamically defined directories
batch_process_txt_to_csv(delimiter='\t')
