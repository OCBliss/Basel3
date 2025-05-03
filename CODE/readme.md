# Basel III Pipeline for Central Bank Paper

This project automates the processing of call reports and material events into regulatory metrics compliant with Basel III standards, as outlined by the Bank for International Settlements (BIS). It is designed for bank research and dynamically executes workflows based on a configurable `pipeline_config.yaml`.

 
**Purpose:** yaml-driven task manager for executing the JSD analysis on call reports and RWA analysis on CMT data from FRED.

## Overview

The pipeline processes financial data through a series of modular Python scripts, supporting:
- Sequential and concurrent execution of steps
- Dependency management between tasks
- Input hashing to skip unchanged steps
- Dynamic input/output detection
- Detailed logging for debugging and auditing

The workflow is defined in `pipeline_config.yaml`, allowing flexibility for any number of processing branches or steps.

### Directory Structure
- `CODE/`: Root directory containing all scripts.
  - `pipeline.py`: Main pipeline script—executes the workflow.
  - `pipeline_config.yaml`: Config file defining steps, dependencies, and execution flow.
  - `STEP 01/`: `call_reports_mkdir_txt_csvs_global.py`
  - `STEP 02/`:
    - `STEP 02.0/`: `Call_Report_Merged_Cleaned_Global.py`
    - `STEP 02.1/`: `numeric_only6.py`
  - `STEP 03/`: `Call_Reports_retrospective_Vertical3c.py`
  - `STEP 04/`:
    - `STEP 04.0/`: `Call_Reports_Distributed_Ratios2.py`
    - `STEP 04.1/`: `Clean_Distributed_Ratios2.py``Call_Reports_Distributed_Ratios2.py`).
  - `STEP 05/`: Dynamic ratio scripts (e.g., `Call_Reports_Dynamic_Ratios2.py`).
  - `STEP 06/`: Material event processing (e.g., `Material_events_cleaned2.py`, `Material_events_de_novo_flag4.py`).
  - `STEP 07/`: Peer group filtering (e.g., `Material_events_peer_group_basel3_t1.py`).
  - `STEP 08/`: JSD computation (e.g., `RC_JSD_Basel_T1_Bin20.py`).
  - `Logs_V3/`: Auto-generated log directory for step outputs and status.
  

## Features

- **Modular Design:** Add or modify steps by updating the YAML configuration.
- **Concurrency:** Executes independent tasks in parallel using `ThreadPoolExecutor`.
  - ** concurrency_branches
    - `basel_iii` - runs all analysis for the Basel III period as specificed in paper
    - `post_gfc` -  runs all analysis for the post-GFC as specificed in paper
    - `t1` - T+1 creates a branch of each ``concurrency_branches`` for a T+1 look ahead.
    - `t2` - T+2 creates a branch of each ``concurrency_branches`` for a T+2 look ahead.
    - `t3` - T+3 creates a branch of each ``concurrency_branches`` for a T+3 look ahead.
    - `t4` - T+4 creates a branch of each ``concurrency_branches`` for a T+4 look ahead.
  - ``concurrency_group`` - is a specific concurrency that occurs only inside a ``concurrency_branches`` instance
    - `jsd` - for instance JSD analysis is only applied once per ``concurrent_branches`` instance.
      - `bins20` - binning forms the probability mass function for Jensen Shannon Divergence among peers, i.e. (20 bins,...,50 bins)
      - `bins30`
      - `bins50`
    - `peers`: `mergers`, `failures`, `survivors` and `de novo` flags are applied for JSD analysis.
    - `filters` - we then filter by `peers` and binning.
    
  - ``intermediate_steps`` - used to insert required sequential stages (e.g., binning, PMF creation) between concurrent groups.
  - ``sequential`` - some steps cannot be run without the preceding step eliminating the possibility for concurrency at that step
- **Efficiency:** Skips steps with unchanged inputs via SHA-256 hashing.
- **Logging:** Outputs detailed logs to `Logs_V3/` for each step.
  - ** This creates to ability to restart the entire analysis mid-stream if errors occurs, preventing CPU runtime waste. see ``run_task``
- **Error Handling:** Graceful failure with exit codes and logs for debugging.

## Future Customization - Example

- **Schedules** specific can be segregated and run à la carte decreasing computational runtime by specifying each schedule as a ``concurrency_branches``
`pipeline_config.yaml`
```yaml
# pipline_config.yaml

# Be sure to have ``dependencies`` match ``execution``

execution:
  sequential: ["1.0", "2.0", "2.1"]
  concurrent_branches: # split by schedule
    rc_schedule:
      sequential: ["3.0.1", "4.0.1", "4.1.1", "5.0.1", "5.1.1"] # RC analysis
      concurrent_branches: # split by financial/regulatory epoch (GFC, post-GFC, Basel III)
        basel_iii: # Basel III regulatory epoch
          sequential: ["6.1.1", "6.2.1", "6.3.1", "6.4.1"] # performs material event flagging
          concurrent_groups: # concurrent_groups used because peer groups can be flagged concurrently
            peers: ["7.0.0.1", "7.0.0.2", "7.0.0.3", "7.0.0.4"] # peer group creation
            filters: ["7.1.0.1", "7.1.0.2", "7.1.0.3", "7.1.0.4"] # filtering by peer group
          intermediate_steps: ["8.0.1.1", "8.1.1.1"] a sequential in between ``concurrency grouops`` to bins and creates the probability mass functions
          concurrent_branches:
            t1: # this is the `BASEL T+1` folder runs Jensen-Shannon Divergence analysis for peer group flagging ``peers`` for a T+1 (1 quarter) look ahead.
              concurrent_groups: # ``concurrent_groups`` can be used here because we are simultaneously binning and generating pmfs for various bin sizes.
                jsd: # actual JSD comparison for peer groups during Basel III epoch
                  bins20: ["8.2.1.1.1"]
                  bins30: ["8.2.1.1.2"]
                  bins50: ["8.2.1.1.3"]
            t2:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.1.2.1"]
                  bins30: ["8.2.1.2.2"]
                  bins50: ["8.2.1.2.3"]
            t3:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.1.3.1"]
                  bins30: ["8.2.1.3.2"]
                  bins50: ["8.2.1.3.3"]
            t4:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.1.4.1"]
                  bins30: ["8.2.1.4.2"]
                  bins50: ["8.2.1.4.3"]
        post_gfc: # you can simply comment epochs, t1-t4, or entire schedules for faster, more efficient computation.
          sequential: ["6.1.2", "6.2.2", "6.3.2", "6.4.2"]
          concurrent_groups:
            peers: ["7.0.1.1", "7.0.1.2", "7.0.1.3", "7.0.1.4"]
            filters: ["7.1.1.1", "7.1.1.2", "7.1.1.3", "7.1.1.4"]
          intermediate_steps: ["8.0.2.1", "8.1.2.1"]
          concurrent_branches:
            t1:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.1.1"]
                  bins30: ["8.2.2.1.2"]
                  bins50: ["8.2.2.1.3"]
            t2:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.2.1"]
                  bins30: ["8.2.2.2.2"]
                  bins50: ["8.2.2.2.3"]
            t3:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.3.1"]
                  bins30: ["8.2.2.3.2"]
                  bins50: ["8.2.2.3.3"]
            t4:
              concurrent_groups:
                jsd:
                  bins20: ["8.2.2.4.1"]
                  bins30: ["8.2.2.4.2"]
                  bins50: ["8.2.2.4.3"]
    rcb_schedule:
      sequential: ["3.0.2"] # RC-B analysis
```
## Prerequisites

- Python 3.6+
- Required Python packages:
  - `pyyaml` (for YAML parsing)
  - `pandas`
  - `numpy`
  - `importlib.utils`
  - `re`
- Directory structure:
  - Project must reside within a `CODE/` directory (auto-detected).
  - `pipeline_config.yaml` must exist in the `CODE/` root.

Install dependencies:
```bash
pip install pyyaml
