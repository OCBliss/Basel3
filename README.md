## Basel III Pipeline for Central Bank Conference

**Author:** Jonathan Waller  
**GitHub:** github.com/OCBLISS  
**Contact:** johnny.waller.nb@gmail.com  
**Affiliation:** Independent Researcher  

This project automates the processing of Call Report data and material events into regulatory metrics, focusing on Jensen-Shannon Divergence (JSD) analyses for Basel III, Post-GFC, and other time periods across multiple Call Report schedules (RC, RC-B, RC-D, RC-E). It’s designed for investment bank research, built by a finance grad (you—insert your name if you want), and runs via a Python script (`pipeline.py`) driven by a dynamic YAML config (`pipeline_config.yaml`). The pipeline supports concurrent branching for independent analyses, dependency management, and input hashing to skip unchanged steps.

### Purpose
- Clean and convert raw Call Report data.
- Perform vertical analysis on the full dataset, then split by schedule (RC, RC-B, etc.).
- Filter peer groups by time periods (Basel III, Post-GFC, GFC).
- Compute JSD with varying time horizons (T+1, T+2, etc.) and bin sizes (20, 30, 50).
- Output regulatory metrics for BIS scrutiny.

### Directory Structure
- `CODE/`: Root directory containing all scripts.
  - `pipeline.py`: Main pipeline script—executes the workflow.
  - `pipeline_config.yaml`: Config file defining steps, dependencies, and execution flow.
  - `STEP 01/`: Cleaning scripts (e.g., `call_reports_mkdir_txt_csvs_global.py`).
  - `STEP 02/`: Conversion scripts (e.g., `Call_Report_Merged_Cleaned_Global.py`, `numeric_only6.py`).
  - `STEP 03/`: Vertical analysis scripts (e.g., `Call_Reports_retrospective_Vertical3c.py`, `Vertical_Analysis_RC.py`).
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
- `Basel3/Material Events/`
  - `De Novo/`
    - `Cleaned/`: Cleaned de novo event data.
    - `RAW/`: Raw de novo event data.
  - `Failures/`
    - `Cleaned/`: Cleaned failure event data.
    - `RAW/`: Raw failure event data.
  - `Mergers/`
    - `Cleaned/`: Cleaned merger event data.
    - `RAW/`: Raw merger event data.
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
- `Basel3/RWA/`
  - `Constant Maturity Treasury/`
    - `FRED/`: FRED data for Constant Maturity Treasury.
      - `FRED MLE YIELD/`: Maximum likelihood estimate yield data.
      - `FRED MLE VOL/`: Maximum likelihood estimate volatility data.
      - `FRED MLE CORR/`: Maximum likelihood estimate correlation data.
      - `FRED HESTON/`: Heston model outputs for FRED data.
  - `Expected Coupon/`: Expected coupon calculations for RWA.
  - `Expected Loss/`: Expected loss estimates for RWA.
  - `Novel Risk Weights/`: Novel risk weight computations.

  
### Requirements
- Python 3.x: With standard libraries (`os`, `sys`, `subprocess`, `hashlib`, `time`, `yaml`, `concurrent.futures`).
  - `pyyaml`
  - `pandas`
  - `numpy`
  - `re`
  - `importlib.util`

### OS Compatibility Note
- This pipeline was developed on macOS, and some scripts may not be fully optimized for Windows. Differences in path handling (e.g., spaces, backslashes vs. forward slashes) or file system behavior might require adjustments for Windows users.

### How It Works
1. `pipeline.py`:
   - Finds the `CODE/` directory dynamically from its own location.
   - Loads `pipeline_config.yaml` and validates required sections (`scripts`, `dependencies`, `execution`).
   - Executes steps based on the `execution` section:
     - `sequential`: Runs steps in order, one after another.
     - `concurrent_branches`: Launches branches in parallel using threads, recursively handling nested branches or groups.
     - `concurrent_groups`: Runs multiple step lists in parallel within a branch.
   - Checks `dependencies` to enforce execution order (e.g., 3.0 must complete before 3.1 starts).
   - Uses input hashing (`compute_hash`) to skip steps if their inputs haven’t changed, logging results in `Logs_V3/`.

2. `pipeline_config.yaml`:
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

2. Schedule Split:
   - Four concurrent branches launch after 3.0:
     - `rc_schedule`: Processes RC schedule data.
     - `rc_b_schedule`: Starts RC-B analysis (currently stops at 3.2—extend as needed).
     - `rc_d_schedule`: Starts RC-D analysis (stops at 3.3).
     - `rc_e_schedule`: Starts RC-E analysis (stops at 3.4).

3. Time Period Split (RC Only):
   - Inside `rc_schedule`, two branches run in parallel:
     - `basel_iii`: Processes RC data for Basel III period.
     - `post_gfc`: Processes RC data for Post-GFC period.
   - Both execute steps 4.0.1–6.4.1 sequentially:
     - "4.0.1": Computes distributed ratios for RC data.
     - "4.1.1": Cleans those distributed ratios.
     - "5.0.1": Computes dynamic ratios for RC.
     - "5.1.1": Cleans the dynamic ratios.
     - "6.1.1": Cleans RC material event data.
     - "6.2.1": Flags de novo events in RC data.
     - "6.3.1": Flags failures in RC data.
     - "6.4.1": Flags mergers in RC data.

4. Peer Group Filtering:
   - For `basel_iii`:
     - `peers`: Runs 7.0.0.1–7.0.0.4 in parallel, filtering peer groups for Basel III across T+1 to T+4 horizons.
     - `filters`: Runs 7.1.0.1–7.1.0.4 in parallel, applying additional filters to Basel III peer groups.
   - For `post_gfc`:
     - `peers`: Runs 7.0.1.1–7.0.1.4 in parallel, filtering peer groups for Post-GFC across T+1 to T+4.
     - `filters`: Runs 7.1.1.1–7.1.1.4 in parallel, applying filters to Post-GFC peer groups.

5. JSD Analysis:
   - For `basel_iii`:
     - "8.0.1": Performs binning on Basel III data (default 50 bins—configurable within the script).
     - "8.1.1": Computes JSD probabilities for Basel III.
     - `t1`: Splits into three concurrent JSD runs with bin sizes 20, 30, 50 (8.2.0.1.1–8.2.0.1.3).
     - `t2`: Runs single JSD step "8.2.0.2" for T+2 horizon.
     - `t3`: Runs single JSD step "8.2.0.3" for T+3 horizon.
     - `t4`: Runs single JSD step "8.2.0.4" for T+4 horizon.
   - For `post_gfc`:
     - "8.0.2": Performs binning on Post-GFC data (default 50 bins).
     - "8.1.2": Computes JSD probabilities for Post-GFC.
     - `t1`: Runs single JSD step "8.2.1.1" for T+1 horizon.
     - `t2`: Runs single JSD step "8.2.1.2" for T+2 horizon.
     - `t3`: Runs single JSD step "8.2.1.3" for T+3 horizon.
     - `t4`: Runs single JSD step "8.2.1.4" for T+4 horizon.

### Notes on Placeholders
- `rc_b_schedule`, `rc_d_schedule`, `rc_e_schedule` currently stop at 3.2, 3.3, and 3.4 respectively. To extend them:
  - Add steps to `scripts` (e.g., "4.0.2": { path: "STEP 04/STEP 04.0.2/RC_B_Distributed_Ratios.py" }).
  - Update `dependencies` (e.g., "3.2": ["4.0.2"]).
  - Expand `execution` with similar `concurrent_branches` structures as `rc_schedule`.
- `t1` binning (20, 30, 50) is implemented for RC Basel III only. Other horizons (t2–t4) and Post-GFC use single steps but can be extended with binning.

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
- Input Hashing: If a script prints "Input from: /path/to/dir", `pipeline.py` hashes the directory’s files (using SHA-256) and skips the step if unchanged, logging the hash with `INPUT_HASH`.
- Concurrency: Uses Python’s `ThreadPoolExecutor`—automatically scales to the number of branches or groups (e.g., 4 schedules, 2 periods, 3 bins in t1).
- Flexibility: Add new schedules, time periods, or bin sizes by editing `pipeline_config.yaml`—no changes to `pipeline.py` required.

### Usage Tips
- Extend a Branch: Add a new schedule (e.g., `rc_f_schedule`) under `concurrent_branches` with its own steps, dependencies, and execution flow.
- Debugging: Check `Logs_V3/`—each step logs `STARTED`, `COMPLETED`, or `ERROR` with timestamps and details.
- Skip Steps: If a step’s inputs haven’t changed (via hash), it skips execution and logs `✅ Step X input unchanged`.

