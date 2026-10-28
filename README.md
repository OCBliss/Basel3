# Basel3 — Regulatory analytics and interest-rate research

Basel3 investigates how regulatory capital and liquidity measures relate to bank
outcomes and interest-rate exposure. It contains two executable workflows:

- **Call Report analysis:** retrieve quarterly FFIEC data, calculate bank ratios,
  construct outcome cohorts and compare their distributions across horizons.
- **Interest-rate modeling:** retrieve Treasury yields, estimate and stabilize
  CIR parameters, model all parameter branches and recursively advance a
  rate/sigma/xi trajectory across maturities.

The Call Report workflow currently ends with filtered pairwise distribution
distances. The interest-rate workflow ends with calibrated parameter histories,
serial trajectories and per-increment covariance/calibration records. Exposure valuation, loss distributions
and a duration-sensitive capital mapping remain research objectives.

## Installation

Clone the repository with an authenticated GitHub connection, then install the
[requirements](requirements.txt) in a Python environment:

```bash
git clone git@github.com:OCBliss/Basel3.git
cd Basel3
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Python 3.8 or later is required; dependency versions must support the selected
interpreter. The activation command above is for POSIX shells. On Windows,
activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell.

The requirements install the local **CallReports** library as an editable
dependency. To use its FFIEC schedule definitions and local ZIP/TXT preparation
without the research pipeline, install only `python3 -m pip install .` and import
`callreports`. See the [independent library guide](src/callreports/README.md) for
CSV headers, user-defined ratios, historical dates and the `callreports` command.

All commands below run from the **repository root**, the directory containing
`requirements.txt`, `src/` and `pipeline/`. The checkout may have any directory
name: source and data paths resolve relative to the code's location.

## Run a workflow

Preview the Call Report plan without downloading data or running its stages:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py --dry-run
```

Run the complete Call Report analysis:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py
```

Run Treasury acquisition followed by the parameter hierarchy:

```bash
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml --dry-run
python3 pipeline/Task_manager_Global_yaml_driven.py \
  --config pipeline/rwa_live/config.yaml
```

The live interest-rate workflow creates a verified yield snapshot and model
outputs in the locations configured by its YAML. These output directories must
be new for each run. See the [live workflow guide](pipeline/rwa_live/readme.md)
for rerun settings and the [RWA execution guide](src/RWA/readme.md) for each
calculation and its outputs. The [offline configuration](pipeline/rwa_hierarchy/readme.md)
uses yield files already available in the repository.

The task manager executes the configured stages, checks declared inputs and
outputs, and writes per-task logs under `pipeline_logs/<run-id>/`. Selected Call
Report and JSD outputs can be replaced on rerun; the RWA snapshot and hierarchy
writers require new destinations. Full dependency and execution rules are in
the [pipeline guide](pipeline/readme.md).

## Call Report analysis

The research asks whether regulatory classifications separate institutions with
different subsequent outcomes, how that separation changes across observation
horizons, and whether interest-rate exposure adds information beyond reported
risk weights. Distributional separation alone does not establish causality,
predictive accuracy, safety or an appropriate capital requirement.

The default configuration executes 20 tasks in this order:

| Stage | Processing | Result |
| --- | --- | --- |
| Download and preparation | Retrieve and validate quarterly FFIEC single-period archives | TXT schedules, checksums and preparation manifest |
| Conversion and merge | Convert schedules, attach FDIC certificates and merge reporting fields | Bank-quarter CSVs |
| Ratios and historical changes | Calculate 76 ratios and changes relative to earlier quarters, matching banks by `CERT` | Current ratios and `q0q1`, `q0q2`, `q0q3` changes |
| Material events | Retrieve FDIC event records, clean them and apply date-window flags | De novo, failure and merger flags |
| Peer groups | Select Failures, Mergers and Survivors by horizon, then combine calendar-selected quarters | Cohort panels for T+1 through T+4 |
| Histograms and PMFs | Count observations with common bin edges and normalize each ratio column | Cohort-specific probability distributions |
| Distribution comparison | Compare Survivors–Failures, Survivors–Mergers and Mergers–Failures | Pairwise distance CSVs |
| Filtering | Retain columns meeting the configured distance threshold | Selected comparison columns |

The [source guide](src/readme.md) maps every task to its executable program.
[Ratio definitions](src/ratios/variables/readme.md) document calculations and
form-specific rules. The [material-event guide](src/material%20events/readme.md)
explains certificate and date-window semantics.

### Horizons and distribution distances

A horizon relates the observation quarter to the event window. For an event in
2023 Q1, the corresponding earlier observation quarters are 2022 Q4 at T+1,
2022 Q3 at T+2, 2022 Q2 at T+3 and 2022 Q1 at T+4. The supplied quarter tables
determine the actual inclusive event windows and the quarters admitted to the
analysis. Failure and merger selections can overlap.

Within each observation quarter, `q0` denotes the current ratio and `q0q1`,
`q0q2`, `q0q3` denote proportional changes against one, two and three prior
quarters. Their exact denominator and missing-value rules are documented in
[dynamic ratios](src/ratios/readme.md).

The code reports the **square root of Jensen–Shannon divergence**, using natural
logarithms. It compares full histogram-based distributions, including differences
in shape and overlap that low-order moments can miss. Results depend on cohort
selection, missing-value treatment and bin specification. The [calculation guide](src/jsd/calculation/readme.md)
defines alignment, normalization and zero-mass handling.

The [YAML configuration](pipeline/pipeline_config_dynamic.yaml) supplies shared
horizon and bin selections:

```yaml
parameters:
  horizons: [1, 2, 3, 4]
  bins1: [20, 30, 50, 100]
  bins2: 5
  bins3: 1
```

`bins1` gives counts across −1 to 1, `bins2` across 1 to 2 and `bins3` the single
unbounded upper interval. These defaults produce 26, 36, 56 and 106 total bins.
Selections propagate through peer groups, histograms, PMFs, comparisons and
filtering. A future matrix-construction stage and formal evaluation of changes
in distance across horizons are described in the [output guide](src/jsd/output/readme.md);
those stages are not implemented.

## Interest-rate modeling

The [RWA execution guide](src/RWA/readme.md) explains the complete implemented
sequence and distinguishes the integrated model from the legacy calibration
scripts. It covers acquisition, quote selection, both parameter-estimation
passes, ridge treatment, separate family dependence, serial recursion and
per-increment audit records.

The model applies calibration to yield histories and then separately to the
estimated `mu`, `theta` and `sigma` histories across maturities. The resulting
histories initialize rate, sigma and xi. Default initialization retains 2,520
complete estimate dates after both rolling warmups, requiring at least 5,290 common
source observations. Every actual Euler increment refreshes three separate family
dependence structures and recalibrates all three state processes before xi,
sigma using new xi, and rate using new sigma advance in that order.

Forecast years continue serially from the previous year's history, random stream
and ridge anchors. Historical intervals can use an observation clock or actual
calendar year fractions; future intervals are configured explicitly. Yearly
trajectories have no ensemble axis, and every increment retains its applied
matrices, coefficients, shocks and before/after states.

These are research estimates. Calibration noise and overlapping windows can
produce apparent parameter dynamics. Positive scenarios and passing regression
tests do not establish economic identification, out-of-sample superiority or an
arbitrage-free term structure. The [model guide](src/RWA/models/parameter_hierarchy/readme.md)
details mathematical assumptions and failure handling. The [model PDF](PDF/Recursive%20IRR%20Model.pdf)
describes the broader research objective.

## Repository map

| Directory | Contents |
| --- | --- |
| [src/](src/readme.md) | Executable analytical components and their usage guides |
| [pipeline/](pipeline/readme.md) | Task manager and workflow configurations |
| [data/](data/readme.md) | Call Report reference tables and locations for generated datasets |
| [Material Events/](Material%20Events/readme.md) | Event definitions, analysis calendars and generated outcome data |
| [RWA/](RWA/README.md) | Treasury input data, archived experimental tables and model-output contracts |
| [PDF/](PDF/readme.md) | Research model and saved bank-report reference PDFs |
| [tests/](tests/readme.md) | Regression and integration tests |

Downloaded archives, caches, run logs and generated model trajectories remain
local. Their producing workflows create manifests and audit records so each
result can be traced to its inputs and settings. Shipped historical tables are
identified in their directory guides; new outputs are not assumed to exist in
a fresh clone.

## Validation

Install the project requirements and follow the [test guide](tests/readme.md)
for the complete suite or focused component checks. Tests use isolated fixtures
and cover analytical contracts, independent likelihood comparisons, chronology,
parameter branches, recursive histories, input verification and pipeline wiring.
Scientific validation also requires suitable held-out data, sensitivity analysis
and comparison with alternative model assumptions.

## Author

Jonathan Waller — Independent Researcher
[GitHub](https://github.com/OCBliss) · [Contact](mailto:johnny.waller.nb@gmail.com)
