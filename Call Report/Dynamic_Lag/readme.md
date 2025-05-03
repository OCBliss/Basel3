# Dynamic Lag Data Processing Script

## Overview
This script processes CSV files containing financial data, calculating dynamic lag features for specific variables based on quarter-over-quarter comparisons. The script reads cleaned data from a specified directory, performs computations for current and past quarters, and outputs the processed files to a new location.

## Directory Structure

### Input Directories:
- **Cleaned Files Directory**: `/Basel3/Call Report/CSV/Distributed_Lag/Cleaned`
  - Contains the input files to be processed. Files must follow the naming convention: `Appended_Cleaned_Call_Report_<Quarter>.csv`.

- **Quarters File**: `/Basel3/Call Report/CSV/quarters.csv`
  - A CSV file listing the available quarters in a column named `Quarters`.

### Output Directory:
- **Dynamic Lag Files Directory**: `/Basel3/Call Report/CSV/Dynamic_Lag`
  - Processed files will be saved here with the prefix `Processed_` added to the original filename.

## Features and Calculations
For each variable in the input files, the script calculates the following:
- **Current Quarter** (`_q0`): The value of the variable for the current quarter.
- **Lagged Changes**:
  - `_q0q1`: Percentage change from the previous quarter.
  - `_q0q2`: Percentage change from two quarters ago.
  - `_q0q3`: Percentage change from three quarters ago.

### Formula for Percentage Change:
If `prev_value` is the value from a previous quarter:

\[
change = \begin{cases} 
\frac{current\_value}{prev\_value} - 1 & \text{if } prev\_value \neq 0, \\
0 & \text{if } prev\_value = 0.
\end{cases}
\]

## How to Use

1. **Prepare the Input Files:**
   - Ensure that the `quarters.csv` file contains all quarters in the dataset in chronological order.
   - Place the cleaned data files in the `Cleaned` directory.
   - Input files must follow the naming convention: `Appended_Cleaned_Call_Report_<Quarter>.csv`, where `<Quarter>` matches an entry in the `quarters.csv` file.

2. **Run the Script:**
   - Execute the script in an environment where Python 3.x is installed, along with the required libraries (`pandas` and `numpy`).

3. **View the Output:**
   - Processed files will be saved in the `Dynamic_Lag` directory with the prefix `Processed_`.

## Key Functions

### `get_quarters(filename)`
- Extracts the current quarter from the filename.
- Identifies the previous three quarters based on the `quarters.csv` file.
- Raises an error if:
  - The current quarter is not found in the `quarters.csv` file.
  - There are not enough previous quarters for lag calculations.

### `process_file(filepath)`
- Reads the input file.
- Calculates lag features for each base variable.
- Creates a structured DataFrame with the calculated columns.
- Saves the processed file in the output directory.

### Batch Processing:
- Processes all files in the `Cleaned` directory that:
  - Start with `Appended_Cleaned_Call_Report`.
  - Have a `.csv` extension.

## Prerequisites

### Libraries:
- `pandas`
- `numpy`

### File Naming and Structure:
- Input files should have variables as columns and include a unique identifier column named `IDRSSD`.
- Variables with lagged data must follow the format `<VariableName>_<Quarter>`.

## Example Workflow

1. **Input File Example:**
   - Filename: `Appended_Cleaned_Call_Report_2023Q2.csv`
   - Content:

   | IDRSSD | Asset | Asset_2023Q1 | Asset_2023Q0 | Liability | Liability_2023Q1 |
   |--------|-------|--------------|--------------|-----------|------------------|
   | 12345  | 100   | 90           | 95           | 50        | 45               |

2. **Output File Example:**
   - Filename: `Processed_Appended_Cleaned_Call_Report_2023Q2.csv`
   - Content:

   | IDRSSD | Asset_q0 | Asset_q0q1 | Liability_q0 | Liability_q0q1 |
   |--------|----------|------------|--------------|----------------|
   | 12345  | 95       | 0.0556     | 50           | 0.1111         |

##
