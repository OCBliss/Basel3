# Distributed Lag Data Processor

The `Distributed Lag` folder contains processed data derived from interleaved Call Report files, prepared to facilitate temporal lag analysis for the Basel III study. This script appends lagged data for up to three previous quarters and saves the output for further modeling and analysis.

---

## Folder Structure

### 1. **Interleaved/**
   - **Description**: Contains Call Report data that has been interleaved to enable temporal trend analysis.
   - **Contents**:
     - Files named `Cleaned_Call_Report_<Quarter>.csv` (e.g., `Cleaned_Call_Report_202301.csv`).
     - Data includes all required Call Report schedules merged into a single file for each quarter.
   - **Usage**:
     - Input for generating distributed lag data.
     - Each file provides the base quarter's data for appending subsequent quarters.

### 2. **Distributed_Lag/RAW/**
   - **Description**: Contains output files where data from three prior quarters is appended to the base quarter.
   - **Contents**:
     - Files named `Appended_Cleaned_Call_Report_<Quarter>.csv` (e.g., `Appended_Cleaned_Call_Report_202301.csv`).
     - Each file includes:
       - Data from the base quarter.
       - Columns for lagged data from three prior quarters.
   - **Usage**:
     - Provides datasets for temporal modeling, capturing lagged relationships between variables.

---

## How to Use This Folder
1. **Input Data**:
   - Place the interleaved Call Report files in the `Interleaved/` folder.
   - Ensure the files follow the naming convention `Cleaned_Call_Report_<Quarter>.csv`.
   - Include the `quarters.csv` file listing the quarters in chronological order.

2. **Script Execution**:
   - Run the script to process interleaved data and generate distributed lag datasets:
     ```bash
     python script_name.py
     ```

3. **Output Data**:
   - Processed files will be saved in the `Distributed_Lag/RAW/` folder.
   - Each output file includes the lagged data for up to three prior quarters.

---

## Additional Notes
- The `quarters.csv` file must contain a complete chronological list of quarters for accurate processing.
- Ensure that `Interleaved/` and `Distributed_Lag/RAW/` directories exist and are accessible before running the script.
- The script uses the `IDRSSD` column as the primary key for merging data between quarters.
