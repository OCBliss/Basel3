# Component organization and integration verification

This supporting change organizes the existing RWA calibration/simulation code by
responsibility. It does not introduce a new financial model or regenerate the
historical research CSVs. Start with the [source component map](../../../src/RWA/readme.md).

## Path migration

| Previous path | Current path |
| --- | --- |
| `src/RWA/quasi-MLE-Euler.py` | `src/RWA/yield_calibration/calibrate.py` |
| `src/RWA/mu_curve_nss_repair.py` | `src/RWA/curve_repair/mu.py` |
| `src/RWA/theta_curve_nss_repair*.py` | `src/RWA/curve_repair/theta.py` |
| `src/RWA/CMT_data_parameters_rebuild.py` | `src/RWA/parameter_rebuild/rebuild.py` |
| `src/RWA/cir_hierarchy.py` | `src/RWA/parameter_hierarchy/core.py` |
| `src/RWA/parameter_hierarchy.py` | `src/RWA/parameter_hierarchy/workflow.py` |
| `src/RWA/parameter_hierarchy.md` | `src/RWA/parameter_hierarchy/readme.md` |
| `pipeline/pipeline_config_rwa_hierarchy.yaml` | `pipeline/rwa_hierarchy/config.yaml` |
| `src/ratios/variables.md` | `src/ratios/variables/readme.md` |

The hierarchy entry point and numerical core now form one package. Imports and
repository-root discovery were updated together with YAML, test paths and usage
links. The theta repair filename no longer contains a literal asterisk. The
ratio-variable catalogue has its own nested guide instead of competing with the
ratio component's README. Historical journal paths remain historical; archived
validation programs now load the current relocated modules while retaining the
old Git path where needed for their baseline comparison.

## Validation

- [Full suite](full-suite.log): **149 tests passed in 41.191 seconds**.
- [Focused RWA suite](focused-rwa-tests.log): 41 tests passed before the global run.
- [Default pipeline dry run](default-dry-run.log): all 20 stages resolve.
- [Hierarchy dry run](hierarchy-dry-run.log): the nested configuration resolves
  its workflow and artifacts from the correct repository locations.
- [Documentation checks](documentation-check.json): local links, shell example
  syntax and component README coverage. Source/output guides were also read
  against their code; existence checks alone cannot establish documentation quality.

For regression reproduction, follow the repository-local temporary-directory
setup in the [test guide](../../../tests/readme.md), then run from `Basel3_repo`:

```bash
python3 -B -m unittest discover -s tests -v
python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_hierarchy/config.yaml --dry-run
```

The integration tests run the actual manager and direct/package entry points on
isolated fixtures and pass exported parameter histories through the real rebuild
consumer. Moving files must not redirect data writes or break their contracts.

## Findings from the wider review

The Practical guides previously described bond-pricing functions and expected-loss
outputs not implemented by their scripts. They now document the actual legacy
cleaning, differencing and parameter calculations, with valuation identified as
future work. Current source names describe calibration and parameter simulation.

Yield acquisition is missing: both active loaders read and causally clean local
FRED CSVs. There is no FRED API retrieval, refresh or freshness stage in the YAML.
Seven histories end 2025-03-10 and the 20-year series ends 2025-03-12; their common
panel ends March 10. FDIC and FFIEC downloaders serve separate data sources.
No source CSV was modified during this work.

The user's engineering objectives and schedule-control requirements are stored
in [AGENTS.md](../../../AGENTS.md) and the [checkpoint](../../CURRENT_TASK.md).
Two attempts to save the explicitly requested two-hour schedule returned success
but persisted daily 02:00. Schedule correction remains unverified; no direct
scheduler-storage modifications or duplicate automation were made.


## Publication

[Publication verification](publication.json) records commit
`5ef0f8020958f8620d3028f412fdbe64f9ec0f6d`, a successful push/pull with matching
local/remote main, and independent matching GitHub blobs for 13 affected files.
