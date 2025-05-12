# 📈 Constant Maturity Treasury (CMT) Data – Overview

This project utilizes **CMT data** (Constant Maturity Treasury) from **FRED** (Federal Reserve Economic Data), published daily by the **Board of Governors of the Federal Reserve System (US)** via the *H.15 Selected Interest Rates* release.

CMT series represent **yields on U.S. Treasury securities interpolated to constructed maturities** (e.g., 1, 2, 5, 10, 20, or 30 years). These are not actual bond yields, but **par rates** derived from a monotonically convex interpolation of market data.

The rates are based on indicative bid-side quotes for the most recently auctioned securities. The U.S. Treasury uses them to construct a continuous yield curve — a critical reference for:

- Interest rate analysis  
- Duration exposure  
- Interest rate risk modeling

📄 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/RWA/README_SVENSKA.md)

---

## 🔍 Purpose in This Project

CMT data is used to:

- Model **duration-adjusted risk weights** under a `PDMM-Heston` (Path-Dependent Multi-Maturity) framework
- Capture **interest rate exposure** in `HTM` (Held-to-Maturity) portfolios
- Create a **theoretical benchmark yield curve** for U.S. bank balance sheet sensitivity
- Support **stress testing** and **Basel III-aligned regulatory analysis**

---

## 📁 Yield Curve Data Directory Structure

| Directory                     | Contents                                                                 |
|------------------------------|--------------------------------------------------------------------------|
| `<root dir>/RWA/FRED/`       | Raw FRED data (`DGS1`, `DGS3`, `DGS5`, `DGS10`, `DGS20`, `DGS30`)        |
| `<root dir>/RWA/Practical/`  | Non-parallel interest rate shock models applied to risk-based capital     |
| `<root dir>/RWA/PDMM/`       | Theoretical model: `PDMM-Heston` (Path-Dependent Multi-Maturity)          |

---

## 📦 Data Source

- **Provider:** Board of Governors of the Federal Reserve System (US)  
- **Publication:** *H.15 Selected Interest Rates*  
- **Frequency:** Daily  
- **Unit:** Percent (not seasonally adjusted)  
- **Source:** [https://fred.stlouisfed.org/series/DGS30](https://fred.stlouisfed.org/series/DGS30)  
- **Last Accessed:** May 12, 2025

> 💡 **Note:** CMT series are subject to methodological updates by the U.S. Treasury, including changes in input weights and interpolation strategy. For details, refer to the *Treasury Yield Curve Methodology* section in the H.15 documentation.

