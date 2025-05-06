**[Finished]**
- STEP 08 folder structure is finished 2025-05-05
- STEP 08 should run successfully to 8.3.0.1.
- `Task_manager_Global_yaml_driven2a.py` changed --> `Task_manager_Global_yaml_driven5a.py`
- `pipeline_config.yaml` updated --> `pipeline_config_dynamic4a.yaml`
  
**[In Progress]**
- STEP 08 future state (ETA TBD)
  - Finish `readme`s and upload script with `argparse` injection and separate manual run
  - Finish 8.4.x and 8.5.x
- TXT subdirectories being populated iteratively need to be moved to Zenodo
⚠️ CSV Precision Warning:
Some regulatory data fields (e.g., RCFAH311) are stored as string-encoded percentages ("XX%").
Even after stripping "%", Excel auto-formatting and pandas dtype inference may cause downstream precision or casting errors. These will be patched via raw float coercion or .csv export handling if needed.
