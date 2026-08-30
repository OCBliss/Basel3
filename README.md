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
- Depositor behavior deviates from standard NML assumptions (dynamic, heterogeneous)

The pipeline in this repository produces the empirical outputs supporting these findings.

---

1. Do Basel III capital and liquidity classifications
retain statistical separation between future failures
and survivors?

2. Does predictive separation deteriorate as the
forecast horizon increases?

3. Do depositor behaviors conform to homogeneous,
memoryless assumptions commonly used in regulatory
liquidity frameworks?

4. Can duration-sensitive interest-rate modeling
identify capital impairment not reflected in
regulatory risk weights?

---

## Conceptual Framework

The pipeline implements a class-conditional transformation approach:

- Failures, Mergers, and Survivors are treated as structurally distinct states, not simple partitions of a common dataset.
- Each cohort undergoes independent preprocessing to preserve class-specific characteristics.
- Distributional comparisons (JSD) are performed across cohorts using multiple horizons (T+1–T+4) to evaluate whether regulatory classifications retain predictive separation out-of-sample, mitigating endogeneity concerns such as window dressing, simultaneity, and reverse causality.

This design ensures that divergence metrics reflect underlying economic differences rather than artifacts of shared preprocessing.

### Forecast Horizons

Observations are indexed relative to the quarter in which a structural event
occurs.

If a bank experiences a material event (failure, merger, etc.) during **2023 Q1**:

| Observation Quarter | Horizon | Event Quarter |
|---------------------|---------|---------------|
| 2022 Q4 | T+1 | 2023 Q1 |
| 2022 Q3 | T+2 | 2023 Q1 |
| 2022 Q2 | T+3 | 2023 Q1 |
| 2022 Q1 | T+4 | 2023 Q1 |

The structural event remains fixed while the observation quarter moves further
back in time.

---

### Jensen-Shannon Divergence Matrices

Each matrix reports the Jensen-Shannon divergence for a single regulatory
variable (for example **RCE-HK07-Saving+**).
* Item Number HK09
* * MATURITY AND REPRICING DATA FOR TIME DEPOITS OF 250000 OR LESS, TIME DEPOSITS OF 250000 OR LESS WITH A REMAINING MATURITY OR NEXT REPRICING DATE OF THREE MONTHS OR LESS

* Item Number 2385 (Savings)
* * TOTAL NONTRANSACTION ACCOUNTS (INCLUDING MMDA'S)

Rows represent the information used to compute the divergence.

| Row | Meaning |
|------|---------|
| **q0** | Regulatory ratio measured at the observation quarter |
| **q0q1** | One-quarter change in the ratio (`q1 → q0`) |
| **q0q2** | Two-quarter change in the ratio (`q2 → q0`) |
| **q0q3** | Three-quarter change in the ratio (`q3 → q0`) |

Example:

|                | BASEL III T+1 | BASEL III T+2 | BASEL III T+3 | BASEL III T+4 |
|----------------|--------------:|--------------:|--------------:|--------------:|
| **q0**   | 0.42 | 0.326 | 0.311 | 0.287 |
| **q0q1** | 0.551 | 0.458 | 0.405 | 0.347 |
| **q0q2** | 0.578 | 0.470 | 0.404 | 0.349 |
| **q0q3** | 0.573 | 0.482 | 0.439 | 0.386 |

For a bank failing during **2023 Q1**, the temporal alignment is:

| q3 | q2 | q1 | q0 | Horizon | Event |
|----|----|----|----|---------|-------|
| 2022 Q1 | 2022 Q2 | 2022 Q3 | 2022 Q4 | T+1 | 2023 Q1 |
| 2021 Q4 | 2022 Q1 | 2022 Q2 | 2022 Q3 | T+2 | 2023 Q1 |
| 2021 Q3 | 2021 Q4 | 2022 Q1 | 2022 Q2 | T+3 | 2023 Q1 |
| 2021 Q2 | 2021 Q3 | 2021 Q4 | 2022 Q1 | T+4 | 2023 Q1 |

Thus, the value in **q0q1 × BASEL III T+1** measures the Jensen-Shannon
divergence computed from the one-quarter change in the regulatory ratio
(**2022 Q3 → 2022 Q4**), evaluated one quarter before the structural event.

**Conclusion**
Across all forecast horizons, the divergence associated with quarter-over-quarter changes exceeds the divergence obtained from contemporaneous observations alone. This suggests that temporal dynamics provide greater discriminatory power than static balance-sheet measurements.

### Why Multiple Horizons?

If Basel III classifications genuinely identify safer institutions, statistical
separation should persist as the forecast horizon increases.

Evaluating multiple horizons allows the framework to distinguish between:

- variables that separate only immediately before failure,
- variables that retain predictive information several quarters in advance,
- variables whose predictive content decays through time.

The evolution of divergence across T+1–T+4 therefore becomes an empirical
measure of the temporal stability of regulatory classifications.

### Dynamic Divergence

The framework evaluates not only divergence at individual horizons but also
the evolution of divergence between successive horizons.

Traditional analyses often evaluate regulatory variables independently at each reporting period. This framework instead evaluates the evolution of distributional separation across successive forecast horizons. The objective is to determine whether the trajectory of divergence contains predictive information beyond that available from any single quarterly observation.

Rather than asking only,

"How different are failures from survivors at T+2?"

the framework also asks,

"How rapidly does that difference change between T+2 and T+1?"

These temporal transitions capture changes in depositor behavior and balance
sheet adjustment immediately preceding structural events.

For example:
- T+4 → T+3
- T+3 → T+2
- T+2 → T+1

### Motivation

Traditional liquidity assumptions often model depositor behavior as relatively
stable through time.

If divergence changes abruptly between adjacent horizons, this suggests that
depositor responses may occur in rapid, heterogeneous repricing episodes
rather than as smooth, memoryless processes.

The multi-horizon framework was therefore designed to evaluate whether the
timing of distributional changes itself contains economically meaningful

## Pipeline

[Here](https://github.com/OCBliss/Basel3/tree/refactor/pipeline)

The Basel III pipeline orchestrates the complete research workflow from raw FFIEC Call Reports through peer-group construction, Jensen-Shannon divergence analysis, and duration-sensitive RWA modeling.

Rather than implementing the workflow as a single monolithic script, the pipeline decomposes the research process into independent analytical stages connected through explicit dependency graphs.

This design was chosen because:

research modules evolve independently;
statistical methodologies may be substituted without changing upstream preprocessing;
different regulatory epochs, schedules, horizons, and parameterizations can be executed independently;
computationally independent tasks can execute concurrently.

The YAML configuration therefore represents the research workflow itself rather than simply a list of Python scripts.

### Call Reports

[Here](https://github.com/OCBliss/Basel3/tree/refactor/call%20reports)

The empirical analysis in this repository is built upon FFIEC Call Reports, the
quarterly regulatory filings submitted by every insured U.S. commercial bank.
These reports provide standardized disclosures covering capital adequacy,
balance sheet composition, liquidity, credit quality, income, and regulatory
ratios.

The objective of this module is not simply to clean regulatory filings, but to
transform heterogeneous reporting schedules into a longitudinal analytical
dataset suitable for statistical inference. The pipeline standardizes reporting
formats across time, performs cross-schedule validation, engineers derived
variables, and reorganizes the data into structures optimized for temporal,
cross-sectional, and distributional analysis.

### JSD

[Here](https://github.com/OCBliss/Basel3/tree/refactor/JSD)

Basel III makes claims about classification: that regulatory categories such as capital adequacy and liquidity distinguish safer institutions from riskier ones. The objective is therefore to evaluate whether these classifications remain statistically separable over future horizons. Jensen-Shannon divergence was selected because it compares entire probability distributions rather than only summary statistics, allowing the framework to detect changes in distributional shape, overlap, and multimodality that moment-based measures may miss.

### Material Events

[Here](https://github.com/OCBliss/Basel3/tree/refactor/Material%20Events)

Basel III is ultimately concerned with the ability of regulatory metrics to
distinguish institutions that subsequently experience materially different
outcomes.

The Material Events module constructs the dependent variables used throughout
the empirical framework by identifying future structural banking events—
including failures, mergers, de novo institutions, and surviving banks—from
FDIC BankFind data.

Rather than treating all institutions as a homogeneous population, these
outcomes are preserved as distinct analytical cohorts before preprocessing.
This enables subsequent peer-group construction and distributional analysis to
evaluate whether regulatory classifications retain predictive separation across
future forecast horizons (T+1 through T+4).

## RWA Module (Active Development)

The RWA module extends the empirical Basel III analysis by investigating
duration-sensitive capital impairment arising from interest-rate risk that is
not reflected in regulatory risk weights.

### PDF

Explanation of the RWA module mathematical foundation [Here](https://github.com/OCBliss/Basel3/tree/refactor/PDF)

### Current Components

- `FRED/`
  - Constant Maturity Treasury yield data.

- `Practical/`
  - Simplified non-parallel yield-shock framework.
  - Preliminary expected-loss estimation.
  - Exploratory risk-weight methodology.

### Research Under Development

  Components include:

  - `FRED MLE YIELD/`
    - Recursive estimation of yield-process parameters
      (`μᵧ(t)`, `νᵧ(t)`, `θᵧ(t)`)

  - `FRED MLE VOL/`
    - Recursive estimation of stochastic volatility
      (`μᵥ(t)`, `ξᵥ(t)`, `θᵥ(t)`)

  - `FRED MLE CORR/`
    - Maximum-likelihood estimation of time-varying correlation matrices
      (`ΣX(t)`, `Σν(t)`, `Σξ(t)`)
      using recursive Cholesky decomposition.


---

# How to Run It

### Requirements
  - `pyyaml`
  - `pandas`
  - `numpy`


### OS Compatibility Note
- The pipeline was developed on macOS. Most scripts are platform-independent, although some file path handling and directory conventions may require minor adjustments on Windows.

### Performance Note
- The pipeline prioritizes reproducibility, modularity, and transparent workflow execution over low-level optimization. Many stages are embarrassingly parallel and can benefit from additional CPU resources when processing large historical FFIEC datasets. This pipeline was developed and tested on a high-memory multi-core workstation. The pipeline is compatible with smaller systems, but execution times will increase as available CPU, memory, and storage bandwidth decrease. Large historical datasets may benefit from additional memory or processing cores.

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
    - `numeric_only.py`
    - `Call_Report.py`
    - `Call_Report_v2_1.py`
  - `ratios/`:
    - `Call_Reports_Distributed_Ratios.py`
    - `Clean_Distributed_Ratios.py`
    - `Call_Reports_Dynamic_Ratios.py`
    - `Clean_dynamic_ratios.py`
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



  
