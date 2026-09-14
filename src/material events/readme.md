# Material-event preparation and panel flags

The material-event workflow retrieves FDIC records, prepares their certificate
and date fields, then appends flags to quarterly bank panels. These flags supply
the [peer-group stage](../peer%20groups/readme.md). Their economic interpretation
depends on the certificate selected during [API cleaning](FDIC%20API/readme.md);
failure and merger downloads currently pass the acquiring certificate onward.

## Execution order

The [main pipeline](../../pipeline/readme.md) supplies every stage's arguments:

| Tasks | Program | Input → output |
| --- | --- | --- |
| `6.0.1`–`6.0.3` | `FDIC API/Material_events_download.py` | FDIC event responses → event-specific `RAW/` CSVs |
| `6.1` | `FDIC API/Material_events_cleaned.py` | RAW records → event-specific `Cleaned/` CSVs |
| `6.1.1` | `FDIC API/Material_events_delete_api.py` | Remove matching RAW downloads after cleaning |
| `6.2` | `Material_events_flag.py --events de_novo` | Dynamic Call Reports → de novo-flagged panels |
| `6.3` | `Material_events_flag.py --events failures` | De novo panels → failure-flagged panels |
| `6.4` | `Material_events_flag.py --events mergers` | Failure panels → merger-flagged panels |

The three downloads run concurrently. Cleaning follows all downloads, and the
three flagging stages run sequentially. Paths in this guide are relative to the
repository root. These directories are created by processing, not supplied as
finished analytical results in a clone.

## Run flagging

After acquisition, cleaning and dynamic-ratio processing:

```bash
python3 "src/material events/Material_events_flag.py" \
  --events de_novo failures mergers --material-dir "Material Events"
```

`--events` is required. Selected stages execute in de novo → failures → mergers
order and read their upstream CSVs. `--input-dir`, `--output-dir` and
`--quarter-map` override paths only when exactly one event type is selected.
For example:

```bash
python3 "src/material events/Material_events_flag.py" --events failures \
  --input-dir "Material Events/DE NOVO/Call Reports" \
  --output-dir "Material Events/Failures/Call Reports" \
  --quarter-map "Material Events/quarters_failures.csv"
```

## Date-window and file contracts

| Event | Panel input | Cleaned event input | Calendar | Output and flags |
| --- | --- | --- | --- | --- |
| De novo | `data/CSV/Dynamic_Lag/Cleaned/` | `Material Events/DE NOVO/Cleaned/` | `quarters_de_novo.csv` | `Material Events/DE NOVO/Call Reports/`, `DE_NOVO_FLAG` |
| Failure | `Material Events/DE NOVO/Call Reports/` | `Material Events/Failures/Cleaned/` | `quarters_failures.csv` | `Material Events/Failures/Call Reports/`, `FAILURE_T1`–`FAILURE_T4` |
| Merger | `Material Events/Failures/Call Reports/` | `Material Events/Mergers/Cleaned/` | `quarters_failures.csv` | `Material Events/Mergers/Call Reports/`, `MERGER_T1`–`MERGER_T4` |

Calendar files reside in `Material Events/`. The program matches panel `CERT`
and `RCON9999` to event certificates and calendar `Quarters`. De novo uses
`ESTDATE`; failures and mergers use `EFFDATE`. Each flag is set independently
when an event date falls between `START_DATE` and that flag's end date, inclusive.
The de novo end column is `END_DATE`; other stages use `END_DATE1` through
`END_DATE4`. Existing quarter windows determine the ordering of these flags;
the code does not propagate one flag's value into another.

The program preserves panel columns and appends the selected flags. De novo
replaces `Dynamic_Cleaned_` in filenames with `DE NOVO_`; failure replaces
`DE NOVO_` with `Failures_`; merger replaces `Failures` with `Mergers`.
Existing selected outputs can be replaced.

Event duplicates and overlapping windows remain in the lookups. Failure and
merger flags can both be set for an observation. Merger loading drops nonfinite
certificates after reporting them; other event paths have their own numeric
conversion behavior and may fail on malformed identifiers or dates. Missing
panels can result in no output, so completion must include checking the expected
files. The [regression suite](../../tests/readme.md) verifies the implemented
comparisons and selections; it does not validate the economic identity of each
FDIC record.
