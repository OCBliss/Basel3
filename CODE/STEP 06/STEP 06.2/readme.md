# Step 06.2 — Flag De Novo Banks in Panel Data

## Purpose

This step flags all **de novo banks** in the dynamic lagged panel dataset based on their **establishment date** (ESTDATE) falling within a financial reporting quarter. It integrates structural charter events into time-series panel data by assigning a `DE_NOVO_FLAG = 1` when applicable.

---

## Input

- cleaned BankFind Suite data: `/Material Events/DE NOVO/Cleaned/`
- Quarter reference file mapping quarter identifiers to date ranges: `/Material Events/quarters_de_novo.csv`
- `/Call Report/CSV/Dynamic_Lag/Cleaned/`


---

## Output

Processed files are saved in: `/Material Events/DE NOVO/Call Reports/`
with filenames prefixed as: `DE NOVO_`


---

## Operations

1. **Quarter Matching**  
   - `RCON9999` in panel data maps to `Quarters` column  
   - `Quarters` file provides `START_DATE` and `END_DATE` for each quarter

2. **DE NOVO Eligibility**
   - For each row:
     - If `CERT` appears in DE NOVO dataset
     - And its `ESTDATE` falls **within** the current quarter’s start and end dates
     - Then `DE_NOVO_FLAG = 1`

3. **Export Flagged Dataset**
   - All original panel columns retained
   - Appends a new binary column: `DE_NOVO_FLAG` = {0, 1}

---

## Example Output Row

| CERT | RCON9999 | ... | DE_NOVO_FLAG |
|------|----------|-----|---------------|
| 12345 | 20190331 | ... | 1             |
| 67890 | 20190331 | ... | 0             |

---

## Next Step

Proceed to **Step 06.3, Step 06.4**:
- Merge Failure and Merger events to assign terminal event outcomes
- Generate model-ready datasets for classification and divergence analysis
