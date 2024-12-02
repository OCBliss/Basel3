# Cleaned Data Subfolder

## Description
This folder contains processed datasets derived from the raw FFIEC TXT files. Each file represents a single financial quarter and has been cleaned and structured for further analysis.

## Source
- Raw data located in the `Basel3/Call Report/TXT` subfolder.
- Original data downloaded from the FFIEC CDR system.

## File Structure
- Each file is named using the format: `YYYYMMDD_cleaned.csv`, where `YYYYMMDD` represents the quarter-end date (e.g., `20240630_cleaned.csv`).

## Cleaning Process
1. **Parsing Raw Data:** Raw TXT files were parsed and converted into structured CSV format.
2. **Data Quality Checks:** 
   - Removed incomplete or malformed entries.
   - Standardized column names for consistency across quarters.
3. **Initial Filters:** Excluded variables with no variance or those irrelevant for analysis.

## Usage
- These datasets serve as the input for merging and vertical analyses in the `Schedules` and `Interleaved` subfolders.
- Recommended as the starting point for custom analyses or validation.

## Additional Notes
- Detailed cleaning scripts and processes are available in the `Scripts` folder of the repository.
