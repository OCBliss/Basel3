# Basel III Analysis Repository

This repository contains all data, scripts, and instructions for reproducing the results presented in "A Critical Examination of Basel III: Material Events, Duration Risk, and a Novel Methodology for Dynamic Stability."

## Repository Structure

### Call Report
- **CSV/**: Processed call report data in three stages:
  - **Cleaned/**: Datasets converted from raw FFIEC TXT files.
  - **Schedules/**: Merged datasets by quarter for horizontal analysis.
  - **Interleaved/**: Vertical analysis of call report data by financial quarter.
- **PDF/**: Visual FFIEC call reports for manual inspection.
- **TXT/**: Raw call report data stored by financial quarter (e.g., `20240630`).

### Material Events
- **DE NOVO/**: Data on new bank formations, organized by financial quarter.
- **Business Combinations/**: Mergers and acquisitions data, stored quarterly.
- **Failures/**: Detailed records of bank failures, organized quarterly.
- **Survivors/**: Data on banks that survived material stress events, stored quarterly.

Each folder contains a `README.md` file explaining its purpose, contents, and usage instructions.
