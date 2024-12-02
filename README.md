# Basel III Analysis Repository

This repository contains all data, scripts, and instructions for reproducing the results presented in "A Critical Examination of Basel III: Material Events, Duration Risk, and a Novel Methodology for Dynamic Stability." It is structured to ensure transparency and facilitate reproducibility for researchers and practitioners.

---

## Repository Structure

### **1. Call Report**
This folder contains financial data derived from FFIEC call reports, organized into raw, processed, and analyzed datasets.
- **PDF/**: Visual versions of the FFIEC call reports for manual inspection.  
- **TXT/**: Raw data files in native text format as provided by the FFIEC, organized by financial quarter (e.g., `20240630/`).  
- **CSV/**: Processed data files with the following subfolders:
  - **Cleaned/**: Merged datasets derived from original call report schedules using Schedule ENT as the primary key.
  - **Schedules/**: Original call report schedules formatted by the FFIEC, retaining MDRM codes as headers and appending FDIC Certificate Numbers.
  - **Interleaved/**: Vertical analyses performed on the Cleaned datasets, capturing temporal trends and peer group comparisons.

### **2. Material Events**
This folder contains data on significant structural and non-financial events affecting banking institutions. Subfolders categorize events by type and organize data by financial quarter:
- **DE NOVO/**: Data on new bank formations.
- **Business Combinations/**: Data on mergers, acquisitions, and reorganizations.
- **Failures/**: Detailed records of failed banking institutions.
- **Survivors/**: Data on banks not involved in mergers or failures, categorized as survivors.

---

## Data Sources
1. **Call Report Data:**
   - Sourced from the FFIEC Central Data Repository (CDR).
   - Raw data files can be found in the `Call Report/TXT` folder, with processed versions in `Call Report/CSV`.

2. **Material Events Data:**
   - Downloaded from the BankFind Suite at [FDIC BankFind Suite](https://banks.data.fdic.gov/bankfind-suite/oscr).
   - Includes structural event details and failure records.

---

## How to Use This Repository

### For Call Report Data:
1. Start with **TXT/** for raw files or **PDF/** for manual validation.
2. Use **Cleaned/** for horizontally merged datasets ready for analysis.
3. Refer to **Schedules/** for the original call report schedules in a standardized format.
4. Use **Interleaved/** for temporal and vertical analyses.

### For Material Events:
1. Choose a relevant subfolder (e.g., `DE NOVO`, `Failures`) for the event type of interest.
2. Cross-reference event data with financial metrics from the Call Report folder.

### Scripts:
- All data preprocessing, cleaning, merging, and analysis scripts are available in the `Scripts` folder.
- Scripts include detailed comments and are designed to reproduce all results presented in the associated research paper.

---

## Key Features
- **Comprehensive Documentation:** Each subfolder includes a `README.md` detailing its contents and use.
- **Transparent Workflow:** The repository provides raw data, intermediate stages, and final datasets for full reproducibility.
- **Temporal and Peer Group Analysis:** Data is organized to support detailed time-series and peer group comparisons.

---

## Notes
- Ensure all dependencies are installed before running scripts (see `Scripts/README.md` for details).
- If additional clarification is required, refer to the `README.md` files within each folder.
- For licensing and usage terms, consult the `LICENSE.md` file.

---

## License
This repository is distributed under [license type]. Please refer to the `LICENSE.md` file for more details.
