## Basel III Regulatory Analytics Pipeline

**Author:** Jonathan Waller  
**GitHub:** github.com/OCBLISS  
**Contact:** johnny.waller.nb@gmail.com  
**Affiliation:** Independent Researcher  

## Basel III Under Strain: Empirical Evidence from Call Report Data

This project implements a data pipeline used to test key assumptions of the Basel III regulatory framework, specifically the belief that regulatory capital adequacy and liquidity classifications (e.g., HQLA, NML stability) correspond to reduced failure risk.

Using FFIEC Call Report data, the system constructs bank cohorts (Failures, Mergers, Survivors) and evaluates their distributional behavior across multiple horizons (T+1–T+4). Jensen-Shannon Distance (JSD) is used to measure whether regulatory-compliant institutions exhibit statistically distinct (and safer) profiles relative to failing banks.

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

This design ensures that JSD metrics reflect underlying economic differences rather than artifacts of shared preprocessing.

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

### Jensen-Shannon Distance Matrices

Each matrix reports the Jensen-Shannon distance for a single regulatory
variable (for example **RCE-HK07-Saving+**).
* Item Number HK09
* * MATURITY AND REPRICING DATA FOR TIME DEPOITS OF 250000 OR LESS, TIME DEPOSITS OF 250000 OR LESS WITH A REMAINING MATURITY OR NEXT REPRICING DATE OF THREE MONTHS OR LESS

* Item Number 2385 (Savings)
* * TOTAL NONTRANSACTION ACCOUNTS (INCLUDING MMDA'S)

Rows represent the information used to compute the distance.

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
distance computed from the one-quarter change in the regulatory ratio
(**2022 Q3 → 2022 Q4**), evaluated one quarter before the structural event.

**Conclusion**
Across all forecast horizons, the JSD associated with quarter-over-quarter changes exceeds the distance obtained from contemporaneous observations alone. This suggests that temporal dynamics provide greater discriminatory power than static balance-sheet measurements.

### Why Multiple Horizons?

If Basel III classifications genuinely identify safer institutions, statistical
separation should persist as the forecast horizon increases.

Evaluating multiple horizons allows the framework to distinguish between:

- variables that separate only immediately before failure,
- variables that retain predictive information several quarters in advance,
- variables whose predictive content decays through time.

The evolution of JSD across T+1–T+4 therefore becomes an empirical
measure of the temporal stability of regulatory classifications.

### Dynamic JSD

The framework evaluates not only JSD at individual horizons but also
the evolution of distance between successive horizons.

Traditional analyses often evaluate regulatory variables independently at each reporting period. This framework instead evaluates the evolution of distributional separation across successive forecast horizons. The objective is to determine whether the trajectory of distance contains predictive information beyond that available from any single quarterly observation.

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

If the JSD changes abruptly between adjacent horizons, this suggests that
depositor responses may occur in rapid, heterogeneous repricing episodes
rather than as smooth, memoryless processes.

The multi-horizon framework was therefore designed to evaluate whether the
timing of distributional changes itself contains economically meaningful

## Pipeline

[Here](https://github.com/OCBliss/Basel3/tree/refactor/pipeline)

The configured Basel III pipeline runs 20 tasks from raw FFIEC Call Reports through peer-group construction, Jensen-Shannon distance analysis, and the final column filter. Duration-sensitive RWA modeling remains a separate module under active development, described below.

Rather than implementing the workflow as a single monolithic script, the pipeline decomposes the research process into independent analytical stages connected through explicit dependency graphs.

This design was chosen because:

research modules evolve independently;
statistical methodologies may be substituted without changing upstream preprocessing;
different regulatory epochs, schedules, horizons, and parameterizations can be executed independently;
computationally independent tasks can execute concurrently.

The YAML configuration therefore represents the research workflow itself rather than simply a list of Python scripts.

### Call Reports

[Here](https://github.com/OCBliss/Basel3/tree/refactor/src/call%20reports)

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

[Binning, PMF and calculation guide](src/readme.md)

Basel III makes claims about classification: that regulatory categories such as capital adequacy and liquidity distinguish safer institutions from riskier ones. The objective is therefore to evaluate whether these classifications remain statistically separable over future horizons. Jensen-Shannon distance was selected because it compares entire probability distributions rather than only summary statistics, allowing the framework to detect changes in distributional shape, overlap, and multimodality that moment-based measures may miss.

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
  - `requests`


### OS Compatibility Note
- The pipeline was developed on macOS. Most scripts are platform-independent, although some file path handling and directory conventions may require minor adjustments on Windows.

### Performance Note
- The pipeline prioritizes reproducibility, modularity, and transparent workflow execution over low-level optimization. Many stages are embarrassingly parallel and can benefit from additional CPU resources when processing large historical FFIEC datasets. This pipeline was developed and tested on a high-memory multi-core workstation. The pipeline is compatible with smaller systems, but execution times will increase as available CPU, memory, and storage bandwidth decrease. Large historical datasets may benefit from additional memory or processing cores.

### How It Works
1. Install the dependencies from the repository root:

   ```sh
   python3 -m pip install -r requirements.txt
   ```

   The pipeline's first task downloads FFIEC **Call Reports — Single Period**, in tab-delimited format. It reads the material-event date ranges in the active YAML, includes three earlier quarters for the dynamic ratios, validates the ZIPs, and extracts them under `data/TXT/`. The current settings require 47 quarters, from 2013Q2 through 2024Q4. No bulk data needs to be copied from another checkout. See the [preparation and rerun instructions](src/readme.md).
2. `Basel3_Global_Filepath.py`:
   - Finds the `Basel3/` root directory dynamically from its own location, then;
   - Resolves `src/`, `data/` and `Material Events/` within that checkout.
3. Run the manager from the repository root:

   ```sh
   python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
   python3 pipeline/Task_manager_Global_yaml_driven.py
   ```

   The dry run shows the expanded arguments and artifact paths without running scripts or creating logs. Use `--config path/to/config.yaml` for another configuration, or `--list` to list its tasks.

4. `pipeline/pipeline_config_dynamic.yaml` defines:
   - `parameters`: Shared horizon and bin selections.
   - `scripts`: Paths relative to `src/`, argument lists, inputs, outputs and directories to create.
   - `dependencies`: Prerequisites that must complete before a task runs.
   - `execution`: An ordered list of sequential or concurrent phases. Each phase completes before the next begins.

   The manager expands parameter placeholders in both arguments and artifact paths, validates the plan, and runs each declared task once. Per-task logs are saved under `pipeline_logs/<run-id>/` by default.

### Select Horizons and Bins

Edit this block at the top of the YAML configuration:

```yaml
parameters:
  horizons: [1, 2, 3, 4]
  bins1: [20, 30, 50, 100]
  bins2: 5
  bins3: 1
```

The default runs all four horizons and all four central bin counts. For an optional subset, `horizons: [1, 3]` and `bins1: [20, 50]` select only T+1/T+3 and those two central bin counts. The same selection reaches peer-group creation, calendar concatenation, binning, PMFs, JSD comparisons and the final filter. Expected input/output paths expand to that selection as well; no separate horizon scripts or duplicated YAML branches are needed.

`bins1` supplies the counts across −1 to 1, `bins2` supplies the count across 1 to 2, and `bins3` is the single unbounded upper bin. Thus `20 + 5 + 1` produces 26 bins. `bins1` accepts positive counts, `bins2` is a positive count, and `bins3` currently accepts only `1`. Output filenames retain the central count, such as `_binned_20.csv`; changing `bins2` updates that specification's outputs.

### Current Workflow

The current configuration has **20 tasks**:

| Tasks | Processing |
| --- | --- |
| `0.0` | Download and verify all required FFIEC reporting quarters before conversion |
| `1.0`, `2.0`, `2.1` | Convert, merge and numerically clean Call Reports |
| `3.0`, `4.0` | Build current-quarter ratios and dynamic ratios using historical rows joined by `CERT` |
| `6.0.1`–`6.0.3` | Call `Material_events_download.py` concurrently for de novo, failures and mergers |
| `6.1`, `6.1.1` | Clean the downloads, then remove matching RAW download files |
| `6.2`–`6.4` | Call `Material_events_flag.py` in de novo → failures → mergers order |
| `7.0` | Call `peer groups/base/Material_events_peer_group_basel3.py` for selected horizons |
| `7.1` | Call `peer groups/horizons/Material_events_peer_group_basel3.py` to select calendar files and concatenate each group/horizon |
| `8.0` | Call `Material_events_JSD_binning_basel3.py` for selected horizons and bin specifications |
| `8.1.1` | Normalize selected histograms with `Material_events_JSD_probabilities_basel3.py` |
| `8.2` | Calculate the three comparisons with `Material_events_JSD_basel3.py` |
| `8.3.0.1` | Apply `JSD_intragroup_filter.py` to selected results; the configured threshold is `0.3` |

The eight material-event tasks use four direct scripts. Their YAML `args` lists supply event selections and paths. The six subsequent tasks use two peer-group scripts, one binning script, one PMF script, one calculation script and one filter script. Each selected group/horizon retains its own output files.

See the [pipeline configuration guide](pipeline/readme.md), [material-event CLI](src/material%20events/readme.md), [peer-group CLI](src/peer%20groups/base/readme.md), [binning CLI](src/jsd/binning/readme.md), and [JSD calculation CLI](src/jsd/calculation/readme.md).

### Directory Structure
- `pipeline/`:
  - `Task_manager_Global_yaml_driven.py`
  - `pipeline_config_dynamic.yaml`
- `data/`:
  - `CSV/`:
    - `Schedules/`:
      - `20240630/`:
        - `FFIEC CDR Call Schedule RC 06302024.csv`
    - `Cleaned/`:
      - `Cleaned_Call_Report_20240630.csv`
    - `Interleaved/`:
      - `Cleaned_Call_Report_20240630.csv`
    - `Dynamic_Lag/`:
      - `Cleaned/`:
        - `Dynamic_Cleaned_Call_Report_20240630.csv`
  - `TXT/`: downloaded quarterly schedules, stored locally.
  - `FFIEC/`: validated ZIP cache and preparation records, stored locally.
- `Material Events/`: tracked quarter tables and reference CSVs. The pipeline creates event, peer-group, JSD and filtered-output subfolders when it runs.
- `PDF/`: research models and the archived bank-report PDFs in `Call Reports/`.
- `RWA/`: source data and separate RWA research work.
- `src/`: subroot directory containing all scripts.
  - `call reports/`:
    - `prepare_call_reports.py`
    - `call_reports_mkdir_txt_csvs_global.py`
    - `Call_Report_Merged_Cleaned_Global.py`
    - `numeric_only.py`
    - `Call_Report.py`
    - `Call_Reports_v4_0.py`
  - `ratios/`:
    - `Dynamic_Ratios.py`
    - `variables.md`: ratio definitions.
  - `material events/`:
    - `FDIC API/`:
      - `Material_events_download.py`
      - `Material_events_cleaned.py`
      - `Material_events_delete_api.py`
    - `Material_events_flag.py`
  - `peer groups/`:
    - `base/`:
      - `Material_events_peer_group_basel3.py`
    - `horizons/`:
      - `Material_events_peer_group_basel3.py`
  - `jsd/`:
    - `binning/`:
      - `Material_events_JSD_binning_basel3.py`
    - `pmf/`:
      - `Material_events_JSD_probabilities_basel3.py`
    - `calculation/`:
      - `Material_events_JSD_basel3.py`
  - `measures/`:
    - `intragroup/`:
      - `JSD_intragroup_filter.py`
    - `intergroup/`:
      - `JSD_intergroup_call_reports.py`


