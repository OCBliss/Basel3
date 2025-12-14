### Yield-Curve MLE Engine

## Rolling Maximum-Likelihood Estimation of Factors Across Treasury Tenors

# Overview

For each Treasury yield tenor (e.g., ```DGS1.csv```, ...):

1. Loads a time series of yields from CMT data from the Federal Reserve
2. Cleans a forward-fills missing values
3. Runs a rolling 2520-day (~10-year) fixed window
4. Calculates *MLE* yield (X_t^i) factor parameters:

   -  θ – speed of mean reversion
   -  μ – long-run mean level
   -  σ – volatility coefficient
  
# Directory Structure

The module anchors itself to the repository using ```Basel3_Global_Filepath.py```

Paths used

ROOT_DIR/
- RWA/
  - FRED/                <-- Raw input yield curves
  - Experimental/
    - MLE YIELD/       <-- Output X_t parameter CSVs
    - MLE VOL/       <-- Output nu_t and Xi_t parameter CSVs
