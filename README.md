## Basel III Regulatory Analytics Pipeline

**Author:** Jonathan Waller  
**GitHub:** github.com/OCBLISS  
**Contact:** johnny.waller.nb@gmail.com  
**Affiliation:** Independent Researcher  

## Basel III Under Strain: Empirical Evidence from Call Report Data

This project implements a data pipeline used to test key assumptions of the Basel III regulatory framework, specifically the belief that regulatory capital adequacy and liquidity classifications (e.g., HQLA, NML stability) correspond to reduced failure risk.

Using FFIEC Call Report data, the system constructs bank cohorts (Failures, Mergers, Survivors) and evaluates their distributional behavior across multiple horizons (T+1–T+4). Jensen-Shannon Divergence (JSD) is used to measure whether regulatory-compliant institutions exhibit statistically distinct (and safer) profiles relative to failing banks.

Results suggest that:
- Regulatory classifications fail to preserve monotonic risk ordering
- Duration risk and classification arbitrage distort capital adequacy signals
- Depositor behavior deviates from standard NML assumptions (non-Markovian, heterogeneous)

The pipeline in this repository produces the empirical outputs supporting these findings.

---

- ✅ **Includes** Depositor behavior using RC-E Part I 2025-05-29
  - NSFR claims
  - NML claims
    - depository heterogeneity
    - sticky deposits failures
    - non-monotonic rate behavior
    - non-Markovian withdrawal behavior 

---


### Purpose
- Clean and convert raw Call Report data.
- Perform vertical analysis on the full dataset, then split by schedule (RC, RC-B, etc.).
- Filter peer groups by time periods (Basel III, Post-GFC, GFC).
- Compute JSD with varying time horizons (T+1, T+2, T+3, T+4) and bin sizes (20, 30, 50, 100).
- Output regulatory metrics for BIS scrutiny.

### Conceptual Framework

The pipeline implements a class-conditional transformation approach:

- Failures, Mergers, and Survivors are treated as structurally distinct states, not simple partitions of a common dataset.
- Each cohort undergoes independent preprocessing to preserve class-specific characteristics.
- Distributional comparisons (JSD) are performed across cohorts using multiple horizons (T+1–T+4) to evaluate whether regulatory classifications retain predictive separation out-of-sample, mitigating endogeneity concerns such as window dressing, simultaneity, and reverse causality.

This design ensures that divergence metrics reflect underlying economic differences rather than artifacts of shared preprocessing.

### Requirements
  - `pyyaml`
  - `pandas`
  - `numpy`


### OS Compatibility Note
- The pipeline was developed on macOS. Most scripts are platform-independent, although some file path handling and directory conventions may require minor adjustments on Windows.

### Performance Note
- The pipeline prioritizes reproducibility, modularity, and transparent workflow execution over low-level optimization. Many stages are embarrassingly parallel and can benefit from additional CPU resources when processing large historical FFIEC datasets. This pipeline was developed and tested on a high-memory multi-core workstation (28 CPU cores, 1.5 TB RAM). The pipeline is compatible with smaller systems, but execution times will increase as available CPU, memory, and storage bandwidth decrease. Large historical datasets may benefit from additional memory or processing cores.

### How It Works
1. Download FFIEC CDR data:
   - `https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx`
   - Dowload `Call Report - Single Period` for all periods in question
   - Place unzipped files `\Basel_iii\data\TXT`
   - Make sure folders are `FFIEC CDR Call Bulk All Schedules YYYYMMDD`
2. `Basel3_Global_Filepath.py`:
   - Finds the `Basel3/` root directory dynamically from its own location, then;
   - Finds the `src/`, `Call Reports/`, `Material Events/` directories and dynamically build sub-root directories.
3. Run `Task_manager_Global_yaml_driven.py`: 
   - Loads `pipeline_config_dynamic.yaml` and validates required sections (`scripts`, `dependencies`, `execution`).
   - Executes steps based on the `execution` section:
     - `sequential`: Runs steps in order, one after another.
     - `concurrent_branches`: Launches branches in parallel using threads, recursively handling nested branches or groups.
     - `concurrent_groups`: Runs multiple step lists in parallel within a `concurrent_branches` process.
     -  `intermediate_steps`: Similar to `sequential`, but functions as a synchronization chokepoint for either a `concurrent_groups` or main `concurrent_branches` process.
   - Checks `dependencies` to enforce execution order (e.g., 3.0 must complete before 3.1 starts).
   - Logs results in `Logs_V3/` for each step in the chain.

4. `pipeline_config_dynamic.yaml`:
   - `scripts`: Maps step IDs (e.g., "1.0") to Python file paths relative to `src/`.
   - `dependencies`: Defines prerequisites for each step (e.g., "3.0": ["3.1", "3.2"] means 3.0 must run before 3.1 and 3.2).
   - `execution`: Specifies the workflow with sequential and concurrent sections, controlling the order and parallelism.

### Current Workflow
Below is the full `pipeline_config.yaml` as of now—every step, dependency, and execution detail included.

### Execution Flow
1. Sequential (1.0–3.0):
   - "1.0": Cleans raw Call Report data into a usable format (e.g., creates directories, converts text to CSVs).
   - "2.0": Merges and further cleans the data into a unified dataset.
   - "2.1": Converts data to numeric-only format for analysis.
   - "3.0": Performs vertical analysis on the full Call Report dataset, preparing it for schedule-specific splits.

2. Time Period Split:
   - execute steps 4.0.1–6.4.1 sequentially:
     - "4.0": Computes distributed ratios for RC, RC-B, etc., data.
     - "4.1": Cleans those distributed ratios.
     - "5.0": Computes dynamic ratios.
     - "5.1": Cleans the dynamic ratios.
     - "6.1": Cleans material event data.
     - "6.2": Flags de novo events in RC data.
     - "6.3": Flags failures in RC data.
     - "6.4": Flags mergers in RC data.

4. Peer Group Filtering:
   - `peers`: Runs 7.0.0.1–7.0.0.4 in parallel, filtering peer groups for Basel III across T+1 to T+4 horizons.
   - `filters`: Runs 7.1.0.1–7.1.0.4 in parallel, applying additional filters to Basel III peer groups.

5. JSD Analysis:
   - "8.0.1": Performs binning on Basel III data (default 50 bins—configurable within the script).
   - "8.1.1": Computes JSD probabilities for Basel III.
   - `t1`: Splits into three concurrent JSD runs with bin sizes 20, 30, 50 (8.2.0.1.1–8.2.0.1.3).
   - `t2`: Runs single JSD step "8.2.0.2" for T+2 horizon.
   - `t3`: Runs single JSD step "8.2.0.3" for T+3 horizon.
   - `t4`: Runs single JSD step "8.2.0.4" for T+4 horizon.

### Notes on Placeholders
- `t1`, `t2`, `t3`, `t4` and binning (20, 30, 50, 100).

### Directory Structure
- `pipeline/`:
  - `Task_manager_Global_yaml-driven5a.py`
  - `pipeline_config_dynamic4a4.yaml`
- `data/`:
  - `CSV/`:
    - `Schedules/`:
      - `20240630/`:
        - `FFIEC CDR Call Schedule RC 06302024.csv`
    - `Cleaned/`:
      - `Cleaned_Call_Report_20240630.csv`
    - `Interleaved/`:
      - `Cleaned_Call_Report_20240630.csv`
    - `Distributed_lag/`:
      - `RAW/':
        - `Distributed_Cleaned_Call_Report_20240630.csv`
      - `Cleaned/`:
        - `Distributed_Cleaned_Call_Report_20240630.csv`
    - `Dynamic_Lag/`:
  - `TXT/`:
  - `PDF/`:
- `src/`: subroot directory containing all scripts.
  - `call reports/`:
    - `call_reports_mkdir_txt_csvs_global.py`
    - `Call_Report_Merged_Cleaned_Global.py`
    - `numeric_only6.py`
    - `Call_Reports_retrospective_Vertical5.py`
  - `ratios/`:
    - `Call_Reports_Distributed_Ratios3.py`
    - `Clean_Distributed_Ratios2.py`
    - `Call_Reports_Dynamic_Ratios3.py`
    - `Clean_dynamic_ratio2.py`
  - `material events/`:
    - `FDIC API/`:
      - `Material_events_de_novo_download_v2.py`
      - `Material_events_Failures_download_v2.py`
      - `Material_events_mergers_download_v2.py`
      - `Material_events_delete_api.py`
      - `Material_events_cleaned2.py`
    - `Material_events_de_novo_flag4.py`
    - `Material_events_failures_flag4.py`
    - `Material_events_mergers_flag2.py`
  - `peer groups/`:
    - `base/`:
      - `Material_events_peer_group_basel3_t1.py`
      - `Material_events_peer_group_basel3_t2.py`
      - `Material_events_peer_group_basel3_t3.py`
      - `Material_events_peer_group_basel3_t4.py`
    - `horizons/`:
      - `Material_events_peer_group_filter_t1.py`
      - `Material_events_peer_group_filter_t2.py`
      - `Material_events_peer_group_filter_t3.py`
      - `Material_events_peer_group_filter_t4.py`
  - `jsd/`:
    - `binning/`:
      - `Material_events_JSD_binning_basel3_20.py`
      - `Material_events_JSD_binning_basel3_30.py`
      - `Material_events_JSD_binning_basel3_50.py`
      - `Material_events_JSD_binning_basel3_100.py`
    - `pmf/`:
      - `Material_events_JSD_probabilities_basel3.py`
    - `horizons/`:
      - `Material_events_JSD_basel3_t1.py`
      - `Material_events_JSD_basel3_t2.py`
      - `Material_events_JSD_basel3_t3.py`
      - `Material_events_JSD_basel3_t4.py`
    - `intragroup/`:
      - `JSD_intragroup_filter3.py`
    - `intergroup/`:
      - `JSD_intergroup_call_reports_bins.py`

### Future Work: RWA and Expected Loss Modeling
- `Basel3/RWA/`
  - `FRED/`: FRED data for Constant Maturity Treasury.
  - `Practical`: Simplified non-parallel yield shock calculation
    - `Expected Loss/`: Expected loss estimates for RWA.
    - `Novel Risk Weights/`: Novel risk weight computations.
  - `PDMM/`: Path-Dependent (i.e., non-Markovian) Multifactor Heston.
    - `FRED MLE YIELD/`: Maximum likelihood estimate yield data. This produces `mu_i^Y(t)`, `nu_i^Y(t)`, `theta_i^Y(t)`
    - `FRED MLE VOL/`: Maximum likelihood estimate volatility data. This produces `mu_i^nu(t)`, `xi_i^nu(t)`, `\theta_i^nu(t)`
    - `FRED MLE CORR/`: Maximum likelihood estimate correlation data. This produces `rho_i^Y(t)`, `rho_i^nu(t)`
    - `FRED HESTON/`: Heston model outputs for FRED data.

  

