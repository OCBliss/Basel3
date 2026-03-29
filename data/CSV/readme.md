# Schedules Subfolder

## Description
This folder contains the original call report schedules formatted by the FFIEC's Central Data Repository (CDR). The schedules have been processed to remove unnecessary rows and append essential identifiers for compatibility with other datasets.

## Source
- Raw TXT data files from the FFIEC CDR located in the repository:  
  [Basel3/Call Report/TXT](https://github.com/OCBliss/Basel3/tree/main/Call%20Report/TXT)
- FDIC Material Events data downloaded from BankFind Suite:  
  [BankFind Suite](https://banks.data.fdic.gov/bankfind-suite/oscr)  
  Also available in the repository:  
  [Basel3/Material Events](https://github.com/OCBliss/Basel3/tree/main/Material%20Events)

## Data Formatting
1. **Headers:**
   - The first row of each schedule (MDRM code descriptions) has been removed, leaving the MDRM codes as column headers.
2. **Key Identifiers:**
   - FDIC Certificate Numbers have been appended to all schedules using the IDRSSD as the key.
   - This ensures compatibility with Material Events data for cross-referencing.

## File Structure
- Files are organized by financial quarter and named in the format:  
  `YYYYMMDD_schedule.csv`  
  (e.g., `20240630_schedule.csv` for the second quarter of 2024).

## Relationship to Other Subfolders
1. **Cleaned Folder:**  
   - Contains merged versions of the original call report schedules.  
   - Uses Schedule ENT as the primary key for combining data.
2. **Interleaved Folder:**  
   - Contains vertical analyses performed on the cleaned data.  
   - These files are structured to facilitate temporal and peer group comparisons.

## Usage
- **Schedules Folder:** Provides a detailed, unaltered view of call report schedules with minimal formatting changes.  
- **Cleaned Folder:** Use for consolidated, horizontally merged datasets.  
- **Interleaved Folder:** Use for vertical analyses and temporal trend studies.

## Notes
- Scripts for appending FDIC Certificate Numbers and processing MDRM codes are available in the `Scripts` folder.
- Refer to the main `README.md` in the `Call Report` folder for an overview of all related subfolders.
