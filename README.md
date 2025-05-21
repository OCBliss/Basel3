## Basel III Pipeline for Central Bank Conference

**Author:** Jonathan Waller  
**GitHub:** github.com/OCBLISS  
**Contact:** johnny.waller.nb@gmail.com  
**Affiliation:** Independent Researcher  

This project automates the processing of Call Report data and material events into regulatory metrics, focusing on Jensen-Shannon Divergence (JSD) analyses for Basel III, Post-GFC, and other time periods across multiple Call Report schedules. It’s designed for investment/central bank research, and runs via a Python script [Task_manager_Global_yaml_driven5a.py](https://github.com/OCBliss/Basel3/blob/main/CODE/) driven by a dynamic YAML config (`pipeline_config_dynamic4a.yaml`). Clone directory with pre-loaded data or ensure `Basel_Global_Filepath.py` is placed in a root directory explicitly named `Basel3/`. The root folder can be wherever you wish and the sub-directories will be dynamically resolved. The pipeline supports concurrent branching for independent analyses, dependency management, and input hashing to skip unchanged steps.


---
⚠️ NOTE TO REVIEWERS: This repository supports the empirical component of the **Sveriges Riksbank** 2025 conference submission titled "***Basel III Under Strain: Interest Rate Exposure, Misclassification Arbitrage, and the Illusion of Compliance***". All code and output structures referenced in the methodology section of the paper are located here. The pipeline is under active development, with new version folders forthcoming to isolate future-state regulatory scenarios. **Uploads still ongoing**.

📄 README på Svenska → [README_SVENSKA.md](https://github.com/OCBliss/Basel3/blob/main/README_SVENSKA.md)

---

**[Finished]**
- STEP 08 folder structure is finished 2025-05-05
- STEP 08 should run successfully to 8.0.4.
- `Task_manager_Global_yaml_driven2a.py` changed --> `Task_manager_Global_yaml_driven5a.py`
- `pipeline_config.yaml` updated --> `pipeline_config_dynamic4a.yaml`
- STEP 03.0 vertical and retrospective analysis
  - Casting errors solved for CET1, CCYB
  - Bank heterogeneity concerns for CET1 adjusted 2025-05-20
- STEP 03.1 cleans the vertical analysis
  - removes `RCRI-CET1-THRES` column (RCFAH311)
- `RWA/` subroot STEP 09-13
  - Practical method finished 2025-05-18

**[In Progress]**
- STEP 08 future state (ETA TBD)
  - Finish `readme`s and upload script with `argparse` injection and separate manual run
  - Finish 8.3.x to 8.5.x
- TXT subdirectories being populated iteratively need to be moved to Zenodo

---

### 📄 Licensing

> ⚠️ 
- 💼 **Commercial use—including regulatory, banking, or consulting implementations—requires a license**  
  See [`Commercial_License.md`](./LICENSE.md) for full terms.

To obtain a commercial license, contact:  
📧 [johnny.waller.nb@gmail.com](mailto:johnny.waller.nb@gmail.com)


### Purpose
- Clean and convert raw Call Report data.
- Perform vertical analysis on the full dataset, then split by schedule (RC, RC-B, etc.).
- Filter peer groups by time periods (Basel III, Post-GFC, GFC).
- Compute JSD with varying time horizons (T+1, T+2, T+3, T+4) and bin sizes (20, 30, 50, 100).
- Output regulatory metrics for BIS scrutiny.

### Directory Structure
- `CODE/`: Root directory containing all scripts.
  - `pipeline.py`: Main pipeline script—executes the workflow.
  - `pipeline_config.yaml`: Config file defining steps, dependencies, and execution flow.
  - `STEP 01/`: Cleaning scripts (e.g., `call_reports_mkdir_txt_csvs_global.py`).
  - `STEP 02/`: Conversion scripts (e.g., `Call_Report_Merged_Cleaned_Global.py`, `numeric_only6.py`).
  - `STEP 03/`: Vertical analysis scripts (e.g., `Call_Reports_retrospective_Vertical3c.py`).
  - `STEP 04/`: Ratio distribution scripts (e.g., `Call_Reports_Distributed_Ratios2.py`).
  - `STEP 05/`: Dynamic ratio scripts (e.g., `Call_Reports_Dynamic_Ratios2.py`).
  - `STEP 06/`: Material event processing (e.g., `Material_events_cleaned2.py`, `Material_events_de_novo_flag4.py`).
  - `STEP 07/`: Peer group filtering (e.g., `Material_events_peer_group_basel3_t1.py`).
  - `STEP 08/`: JSD computation (e.g., `RC_JSD_Basel_T1_Bin20.py`).
  - `Logs_V3/`: Auto-generated log directory for step outputs and status.

### Basel3 Directory Structure
- `Basel3/Call Reports/`
  - `CSV/`
    - `Cleaned/`: Cleaned CSV outputs from Call Report processing.
    - `Interleaved/`: Interleaved CSV data from multiple schedules.
    - `Schedules/`: CSV data split by Call Report schedules (e.g., RC, RC-B).
    - `Distributed Lag/`
      - `Cleaned/`: Cleaned distributed lag ratio outputs.
      - `RAW/`: Raw distributed lag ratio data.
    - `Dynamic Lag/`
      - `Cleaned/`: Cleaned dynamic lag ratio outputs.
      - `RAW/`: Raw dynamic lag ratio data.
  - `PDF/`: Original Call Report PDFs.
  - `TXT/`: Text files extracted from Call Report PDFs.
    - `FFIEC CDR Call Bulk All Schedules 20240630/`
    - `FFIEC CDR Call Bulk All Schedules 20240330/`
    - etc.
- `Basel3/Material Events/`
  - `De Novo/`
    - `Cleaned/`: Cleaned de novo event data structured for labeling.
    - `RAW/`: Raw de novo event data.
    - `Call Reports`: Call Reports labeled with De Novo flags.
  - `Failures/`
    - `Cleaned/`: Cleaned failure event data.
    - `RAW/`: Raw failure event data.
    - `Call Reports`: Call Reports labeled with De Novo + Failure flags.
  - `Mergers/`
    - `Cleaned/`: Cleaned merger event data.
    - `RAW/`: Raw merger event data.
    - `Call Reports`: Call Reports labeled with De Novo + Failure + Merger flags.
  - `JSD/`
    - `Basel III/`
      - `Mergers T+1/`: JSD outputs for Basel III mergers, T+1 horizon.
      - `Mergers T+2/`: JSD outputs for Basel III mergers, T+2 horizon.
      - `Mergers T+3/`: JSD outputs for Basel III mergers, T+3 horizon.
      - `Mergers T+4/`: JSD outputs for Basel III mergers, T+4 horizon.
      - `Failures T+1/`: JSD outputs for Basel III failures, T+1 horizon.
      - `Failures T+2/`: JSD outputs for Basel III failures, T+2 horizon.
      - `Failures T+3/`: JSD outputs for Basel III failures, T+3 horizon.
      - `Failures T+4/`: JSD outputs for Basel III failures, T+4 horizon.
    - `Post-GFC/`
      - `Mergers T+1/`: JSD outputs for Post-GFC mergers, T+1 horizon.
      - `Mergers T+2/`: JSD outputs for Post-GFC mergers, T+2 horizon.
      - `Mergers T+3/`: JSD outputs for Post-GFC mergers, T+3 horizon.
      - `Mergers T+4/`: JSD outputs for Post-GFC mergers, T+4 horizon.
      - `Failures T+1/`: JSD outputs for Post-GFC failures, T+1 horizon.
      - `Failures T+2/`: JSD outputs for Post-GFC failures, T+2 horizon.
      - `Failures T+3/`: JSD outputs for Post-GFC failures, T+3 horizon.
      - `Failures T+4/`: JSD outputs for Post-GFC failures, T+4 horizon.

### RWA: Completed Practical 2025-05-18
- `Basel3/RWA/`
  - `FRED/`: FRED data for Constant Maturity Treasury.
  - `Practical`: Simplified non-parallel yield shock calculation
    - `Constant Maturity Treasury/`
      - `Cleaned/`
      - `Differenced/`: Calculates only the positive yield shocks over a rolling time horizon. Any values below a threshold are filtered out to model only the downside deviation (risk of loss).
      - `EXP_DRIFT/`: Calculates the independent rate rates for each maturity.
      - `Expected Coupon/`: Expected coupon calculations for RWA.

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

  
### Requirements
- Python 3.6: With standard libraries (`os`, `sys`, `subprocess`, `hashlib`, `time`, `yaml`, `concurrent.futures`).
  - `pyyaml`
  - `pandas`
  - `numpy`

 Type or copy and paste into terminal window
```python
[ -f 
```
Drag the `requirements.txt` file into the terminal window (this auto-fills the path). Make you have a space after the `-f`, before the `[` and after the `-r` as well.
```python
 ] && pip install -r
```
Drag the `requirements.txt` file into the terminal window again. Press `return`.

### OS Compatibility Note
- This pipeline was developed on macOS, and some scripts may not be fully optimized for Windows. Differences in path handling (e.g., spaces, backslashes vs. forward slashes) or file system behavior might require adjustments for Windows users.

### How It Works
1. `Basel3_Global_Filepath.py`:
   - Finds the `Basel3/` root directory dynamically from its own location, then;
   - Finds the `CODE/`, `Call Reports/`, `Material Events/` directories and dynamically build sub-root directories.
2. `Task_manager_Global_yaml_driven5a.py`: 
   - Loads `pipeline_config_dynamic4a.yaml` and validates required sections (`scripts`, `dependencies`, `execution`).
   - Executes steps based on the `execution` section:
     - `sequential`: Runs steps in order, one after another.
     - `concurrent_branches`: Launches branches in parallel using threads, recursively handling nested branches or groups.
     - `concurrent_groups`: Runs multiple step lists in parallel within a branch.
   - Checks `dependencies` to enforce execution order (e.g., 3.0 must complete before 3.1 starts).
   - Logs results in `Logs_V3/` for each step in the chain.

2. `pipeline_config_dynamic4a.yaml`:
   - `scripts`: Maps step IDs (e.g., "1.0") to Python file paths relative to `CODE/`.
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

### Running the Pipeline
1. Setup:
   - Place all scripts in their respective `STEP XX/` subdirectories under `CODE/`.
   - Ensure `pipeline_config.yaml` is in `CODE/`.
2. Command:
   - Run from the command line: `python CODE/pipeline.py`
3. Output:
   - Logs are generated in `CODE/Logs_V3/` (e.g., `1.0_log.txt`, `8.2.0.1.1_log.txt`).
   - Each log includes timestamps, step start/completion, and input hashes (SHA-256) if hashing is enabled.

### Dynamic Features
- Concurrency: Uses Python’s `ThreadPoolExecutor`—automatically scales to the number of branches or groups (e.g., 4 schedules, 2 periods, 3 bins in t1).
- Flexibility: Add new schedules, time periods, or bin sizes by editing `pipeline_config.yaml`—no changes to `pipeline.py` required.

### Usage Tips
- Extend a Branch: Add a new schedule (e.g., `rc_f_schedule`) under `concurrent_branches` with its own steps, dependencies, and execution flow.
- Debugging: Check `Logs_V3/`—each step logs `STARTED`, `COMPLETED`, or `ERROR` with timestamps and details.
- Skip Steps: If a step’s inputs haven’t changed (via hash), it skips execution and logs `✅ Step X input unchanged`.

