# Basel III Pipeline for Central Bank Paper

This project automates the processing of call reports and material events into regulatory metrics compliant with Basel III standards, as outlined by the Bank for International Settlements (BIS). It is designed for bank research and dynamically executes workflows based on a configurable `pipeline_config_dynamic4a4.yaml`.

**NOTE**: Please use --> `Task_manager_Global_yaml_driven5d.py`. working on input_dirs injection for self-healing subroot directories. Folders could be renamed or removed in the script at will.
 
**Purpose:** yaml-driven task manager for executing the JSD analysis on call reports and RWA analysis on CMT data from FRED.

## Overview

The pipeline processes financial data through a series of modular Python scripts, supporting:
- Sequential and concurrent execution of steps
- Dependency management between tasks
- Input hashing to skip unchanged steps
- Dynamic input/output detection
- Detailed logging for debugging and auditing

The workflow is defined in `pipeline_config_dynamic4a4.yaml`, allowing flexibility for any number of processing branches or steps.

### Directory Structure
- `pipeline/`:
  - `Task_manager_Global_yaml-driven5a.py`
  - `pipeline_config_dynamic4a4.yaml`
 
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
      concurrent_groups:
        api: ["6.0.1", "6.0.2", "6.0.3"] # FDIC BankFind Suite API
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
