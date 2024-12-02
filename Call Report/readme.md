# Call Report Folder

The Call Report folder contains all data derived from FFIEC call reports, organized to facilitate data processing and analysis for the Basel III study. This folder includes raw data, intermediate formats, and processed datasets ready for analysis.

## Folder Structure

### 1. **PDF/**
   - **Description:** Visual versions of the FFIEC call reports for manual inspection and validation.
   - **Contents:**  
     - Files in PDF format, organized by financial quarter (e.g., `20240630.pdf`).
   - **Usage:** Used for manual verification and reference.

### 2. **TXT/**
   - **Description:** Raw data files downloaded from the FFIEC CDR (Central Data Repository).
   - **Contents:**  
     - Subfolders for each financial quarter, named by the quarter’s end date (e.g., `20240630/`).
     - Files in native text format as provided by FFIEC.
   - **Usage:**  
     - Input for data preprocessing and conversion into CSV format (found in the CSV folder).
     - Provides an unaltered source for reproducibility.

### 3. **CSV/**
   - **Description:** Contains processed data in CSV format, structured for analysis.
   - **Subfolders:**
     - **Cleaned/**:  
       - Processed datasets converted from TXT files.
       - Files named by financial quarter (e.g., `20240630_cleaned.csv`).
     - **Schedules/**:  
       - Merged datasets for each financial quarter, providing a comprehensive horizontal view of all schedules.
       - Files named by financial quarter (e.g., `20240630_schedules.csv`).
     - **Interleaved/**:  
       - Vertical analysis of call report data, enabling temporal comparisons and trend identification.
       - Files named by financial quarter (e.g., `20240630_interleaved.csv`).
   - **Usage:**  
     - Cleaned data serves as the basis for merging and interleaving steps.
     - Schedules and Interleaved folders provide processed datasets for specific types of analysis.

## How to Use This Folder
1. **For Raw Data:**
   - Refer to the `TXT/` subfolder for unprocessed FFIEC call report data by quarter.
2. **For Processed Data:**
   - Use the `CSV/` subfolders for datasets ready for analysis:
     - Start with `Cleaned/` for initial data.
     - Use `Schedules/` or `Interleaved/` depending on the type of analysis required.
3. **For Validation:**
   - Refer to the `PDF/` subfolder for visual cross-checking of raw call report data.

## Additional Notes
- Each subfolder includes its own `README.md` file with more detailed instructions and metadata.
- For reproducibility instructions and code, refer to the main `README.md` in the Basel3 repository.
