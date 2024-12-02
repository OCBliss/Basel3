# Interleaved Subfolder

## Description
This folder contains vertically analyzed datasets derived from the merged data in the **Cleaned** subfolder. These files are structured to capture temporal trends and facilitate peer group comparisons over multiple financial quarters.

## Source
- Data is sourced from the `Cleaned` folder, which merges the original call report schedules using Schedule ENT as the primary key.  
- Original call report schedules are located in the `Schedules` folder:  
  [Basel3/Call Report/Schedules](https://github.com/OCBliss/Basel3/tree/main/Call%20Report/CSV/Schedules).

## Vertical Analysis Process
1. **Dataset Structure:**
   - Combines data across multiple financial quarters to create a vertically integrated view.
   - Organizes data by quarter for consistent temporal analysis.
2. **Normalization:**
   - Key financial metrics are standardized across quarters to enable comparability.
3. **Derived Metrics:**
   - Includes quarter-over-quarter changes, cumulative trends, and other derived variables relevant for systemic risk analysis.

## File Structure
- Files are organized by financial quarter and named in the format:  
  `YYYYMMDD_interleaved.csv`  
  (e.g., `20240630_interleaved.csv` for the second quarter of 2024).

## Relationship to Other Subfolders
1. **Schedules Folder:**  
   - Provides the original call report schedules formatted by the FFIEC, with MDRM codes as headers.
   - Serves as the input for the `Cleaned` folder.
2. **Cleaned Folder:**  
   - Contains horizontally merged datasets using Schedule ENT as the key.
   - These merged files are the foundation for the interleaved analysis.

## Usage
- **Temporal Analysis:** Examine trends and changes in financial metrics over consecutive quarters.
- **Peer Group Comparisons:** Evaluate differences among survivor, merger, and failure peer groups, leveraging the Material Events data.
- **Predictive Modeling:** Use these datasets as inputs for time-series models and other statistical analyses.

## Notes
- Scripts for vertical analysis and normalization are available in the `Scripts` folder of the repository.
- For details on the cleaning and merging process, refer to the `Cleaned` folder's `README.md`.

## Additional Resources
- Material Events data: [Basel3/Material Events](https://github.com/OCBliss/Basel3/tree/main/Material%20Events)
- Original call report schedules: [Basel3/Call Report/Schedules](https://github.com/OCBliss/Basel3/tree/main/Call%20Report/CSV/Schedules)
