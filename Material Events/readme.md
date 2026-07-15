# Material Events Folder

This folder contains data on significant structural and non-financial banking events, sourced primarily from the **BankFind Suite** at the [FDIC website](https://banks.data.fdic.gov/bankfind-suite/oscr). The data reflects transactions by either the processed date or the effective date.

The empirical objective of this repository is to determine whether Basel III
regulatory classifications provide predictive information regarding future
institutional outcomes.

To evaluate this question, every observation must ultimately be associated with
a measurable structural outcome. The Material Events module constructs these
outcome variables by identifying significant institutional events—including
failures, mergers, de novo institutions, and surviving banks—from FDIC
BankFind data.

These event classifications form the dependent variables used throughout the
research. They enable regulatory metrics observed at quarter **T** to be
evaluated against structural outcomes occurring at future forecast horizons
(T+1 through T+4).

## Why Structural Events?

Basel III is fundamentally concerned with the resilience of financial
institutions.

Consequently, regulatory metrics are evaluated against observable structural
outcomes rather than contemporaneous accounting values alone.

Failures, mergers, de novo institutions, and surviving banks represent
economically distinct end states whose behavior can be compared
distributionally using the subsequent peer-group and Jensen-Shannon
frameworks.

## Event Types
The events and changes included in this folder cover the following types:
- **New Institutions:** Records of newly established banks. -> **De Novo**
- **Business Combinations:** Includes mergers, acquisitions, and reorganizations. -> **Mergers**
- **Business Combinations - Failures:** Mergers resulting from bank failures. -> **Failures**
- **Interim Mergers & Reorganizations:** Short-term transactions for structural changes.
- **Conversions:** Bank charter changes or ownership transformations.
- **Title Changes:** Updates to institution names or legal titles.
- **Main Office Relocations:** Changes in the primary office locations of institutions.
- **Liquidations:** Voluntary or involuntary closures of banking institutions.
- **Trust Powers and Branch Purchases & Assumptions:** Transactions involving trust authority or branch-level transfers.

## Why Peer Groups

Comparing all institutions as a single population obscures meaningful
differences between banks experiencing fundamentally different structural
outcomes.

The repository therefore constructs separate peer groups before statistical
analysis.

This approach reduces contamination between cohorts and preserves
class-specific characteristics that would otherwise be diluted by pooling
institutions into one aggregate distribution.

For analysis, the data has been divided into three peer groups:
1. **DE NOVO:**
2. **Survivors:** All institutions excluding those involved in mergers or failures.
3. **Mergers:** Institutions involved in mergers, acquisitions, or reorganizations.
4. **Failures:** Institutions that failed, with failure data sourced directly from the FDIC at [this link](https://banks.data.fdic.gov/bankfind-suite/failures).

## Outcome Label Construction

The Material Events module transforms FDIC event records into analytical
labels used throughout the research pipeline.

These labels define the dependent variables for subsequent statistical
analysis and are propagated into peer-group construction, forecast-horizon
alignment, and Jensen-Shannon divergence calculations.

## Filtration-adapative Ratios
The `Material Events/` folder also contains four csvs beginning with "quarters" to aid in the ``{t,t}``, ``{t,t-1}``, ``{t,t-2}`` and ``{t,t-3}`` calculation
- **quarters_basel3**
- **quarters_de_novo**
- **quarters_failures**
- **quarters**

## Folder Structure
This folder is further divided into subfolders based on event types and peer groups. Each subfolder is organized by financial quarter:
- **DE NOVO/**: Data on new institutions, organized quarterly.
  - `RAW/`: The raw data from BankFind Suite for new institutions must be placed here.
  - `CLEANED/`: The cleaned version,restructuring and removing unnecessary columns will be placed here.
  - `Call Reports/`:
- **Mergers/**: Mergers and acquisitions, organized quarterly.
  - `RAW/`: The raw data from BankFind Suite for failures must be placed here.
  - `CLEANED/`: The cleaned version,restructuring and removing unnecessary columns will be placed here.
  - `Call Reports/`:
  - `Peer Group Failures/`:
    - `BASEL III T+1/`:
    - `BASEL III T+2/`:
    - `BASEL III T+3/`:
    - `BASEL III T+4/`:
  - `JS Divergence/`:
- **Failures/**: Detailed records of bank failures, organized quarterly.
  - `RAW/`: The raw data from BankFind Suite for mergers must be placed here.
  - `CLEANED/`: The cleaned version,restructuring and removing unnecessary columns will be placed here.
  - `Call Reports/`:
  - `Peer Group Failures/`:
    - `BASEL III T+1/`:
    - `BASEL III T+2/`:
    - `BASEL III T+3/`:
    - `BASEL III T+4/`:
  - `JS Divergence/`:
- **Survivors/**: Data on institutions excluded from mergers or failures, organized quarterly.
  - `Peer Group Failures/`:
    - `BASEL III T+1/`:
    - `BASEL III T+2/`:
    - `BASEL III T+3/`:
    - `BASEL III T+4/`:
  - `JS Divergence/`:
- **JSD:**
### Future state
- **IG:**
- **JSD-INTRA:**

## How to Use This Folder
1. **Event Type Analysis:** 
   - Use the subfolder corresponding to the specific event type (e.g., `Business Combinations/` for mergers).
2. **Peer Group Analysis:** 
   - To analyze trends among survivors, mergers, or failures, refer to the relevant peer group subfolder.
3. **Cross-Referencing Data:** 
   - Combine this structural data with call report data (located in the Call Report folder) to analyze the financial impact of these events.

## Notes on Data Sources
- The data on structural banking events is sourced from the **BankFind Suite - Events & Changes** at [this link](https://banks.data.fdic.gov/bankfind-suite/oscr).
- Failure data is sourced from the **BankFind Suite - Failures** at [this link](https://banks.data.fdic.gov/bankfind-suite/failures).

## Additional Documentation
Each subfolder contains its own `README.md` with details specific to that event type or peer group.
