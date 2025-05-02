# Material Events Folder

This folder contains data on significant structural and non-financial banking events, sourced primarily from the **BankFind Suite** at the [FDIC website](https://banks.data.fdic.gov/bankfind-suite/oscr). The data reflects transactions by either the processed date or the effective date.

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

## Peer Groups
For analysis, the data has been divided into three peer groups:
1. **DE NOVO:**
2. **Survivors:** All institutions excluding those involved in mergers or failures.
3. **Mergers:** Institutions involved in mergers, acquisitions, or reorganizations.
4. **Failures:** Institutions that failed, with failure data sourced directly from the FDIC at [this link](https://banks.data.fdic.gov/bankfind-suite/failures).
5. **JSD:**
6. **IG:**
7. **JSD-INTRA:**

## Filtration-adapative Ratios
The `Material Events/` folder also contains four csvs beginning with "quarters" to aid in the ``{t,t}``, ``{t,t-1}``, ``{t,t-2}`` and ``{t,t-3}`` calculation
- **quarters_basel3**
- **quarters_de_novo**
- **quarters_failures**
- **quarters**

## Folder Structure
This folder is further divided into subfolders based on event types and peer groups. Each subfolder is organized by financial quarter:
- **DE NOVO/**: Data on new institutions, organized quarterly.
- **Business Combinations/**: Mergers and acquisitions, organized quarterly.
- **Failures/**: Detailed records of bank failures, organized quarterly.
- **Survivors/**: Data on institutions excluded from mergers or failures, organized quarterly.

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
