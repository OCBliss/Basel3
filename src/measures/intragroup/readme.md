# Step 8.3.0.1 — Intragroup Column Filtering After JSD Outputs

This step proccesses the JSD outputs temporally produced in:

- `Material Events/JSD/BASEL III T+1/`
- `Material Events/JSD/BASEL III T+2/`
- `Material Events/JSD/BASEL III T+3/`
- `Material Events/JSD/BASEL III T+4/`

and applies an directional pmf mean distance style filter:

- keep onl those columns whose JSD value is above a threshold (T)
  
## Purpose

The purpose of this is to identify **high-signal variables** removing columns whose JSD values are too small (i.e., columns that provide very little divergence/information between outcomes)

This implements a hard threshold:

- Variables with **JSD < T** → removed
- Variables with **JSD ≥ T** → kept

For:

- Survivors vs. Failures  
- Survivors vs. Mergers  
- Mergers vs. Failures

## Inputs

### YAML

**argparse** injection is used `JSD_intragroup_filter3.py`

- place beneath line containing `path`
```
args: "--process_dir_t1 'Material Events/JSD/BASEL III T+1' \
        --output_dir_t1 'Material Events/IG/BASEL III T+1' \
        --process_dir_t2 'Material Events/JSD/BASEL III T+2' \
        --output_dir_t2 'Material Events/IG/BASEL III T+2' \
        --process_dir_t3 'Material Events/JSD/BASEL III T+3' \
        --output_dir_t3 'Material Events/IG/BASEL III T+3' \
        --process_dir_t4 'Material Events/JSD/BASEL III T+4' \
        --output_dir_t4 'Material Events/IG/BASEL III T+4'"
```

Use `JSD_intragroup_filter.py if argparse throws error is not necessary and comment the above.
