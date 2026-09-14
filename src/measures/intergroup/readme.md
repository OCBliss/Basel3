# Combine cohort panels by horizon

`JSD_intergroup_call_reports.py` concatenates Failures, Mergers and Survivors
panels for each of T+1 through T+4. It is separate from the default pipeline and
does not calculate a new divergence or filter ratio columns.

After generating all four [cohort panels](../../peer%20groups/readme.md), run
from the repository root with the project requirements installed:

```bash
python3 src/measures/intergroup/JSD_intergroup_call_reports.py
```

## Inputs and outputs

For each group and horizon `h`, the input is:

```text
Material Events/<Group>/Horizons/Peer_Group_<Group>_Basel3_t<h>.csv
```

The combined output is:

```text
Material Events/IG/Call Reports/RAW/Call_Report_Basel3_t<h>.csv
```

The script concatenates available rows and the column union. It has no CLI
selection options and writes up to four files, replacing existing results.
Missing inputs are printed and skipped, so a written result may contain fewer
than three groups. Failure and merger cohort membership can overlap; vertical
concatenation does not resolve duplicated bank observations across those groups.

The script executes at import. Invoke it as a program only after checking its
inputs. Further institution-level distance measures or classifier training are
possible consumers, but are not implemented by this program.
