# CallReports

CallReports provides date-aware FFIEC Call Report definitions and local bulk-file
preparation. It uses pandas and NumPy for structured data handling. Its schedule
methods expose the reporting fields and calculations; users can choose their own
ratios without running Basel3's research pipeline.

The guide includes the public API, with exact signatures for all 573 report
methods and the shared preparation and historical-data helpers:

- [Method arguments and returned values](#method-arguments-and-returned-values)
- [Historical dates](#historical-dates)
- [Shared classes and functions](#shared-classes-and-functions)
- [031 method reference](#callreport-031-reference)
- [051 method reference](#callreport-051-reference)

## Installation

Python 3.8 or later is required, with compatible pandas and NumPy releases.
Install the package from [PyPI](https://pypi.org/project/CallReports/):

```sh
pip install CallReports
```

To install the current source directly, run this from the repository root:

```sh
python3 -m pip install .
```

For development, use `python3 -m pip install -e .`. The distribution is named
`CallReports`; the Python import and installed command are named `callreports`.
The repository's `requirements.txt` installs its pinned CallReports release from PyPI along
with the additional dependencies needed by Basel3. For library development,
install those requirements first, then install the editable source. Bank data is
supplied separately and is not downloaded during installation.

## Use an existing structured CSV

The CSV must contain one row per bank and reporting quarter, with the original
FFIEC code headers. Select one bank row before constructing a report:

```python
import pandas as pd
from callreports import CallReport_051, safe_divide

table = pd.read_csv("Cleaned_Call_Report_20240331.csv", low_memory=False)
row = table.loc[table["IDRSSD"] == 101].iloc[0]
report = CallReport_051(row)
date = "P0"

assets = report.BalanceSheet.TotalAssets(date=date)
trading_share = safe_divide(
    report.BalanceSheet.TradingAssets(date=date),
    report.BalanceSheet.TotalAssets(date=date),
)
```

This example requires `IDRSSD`, `RCON9999`, `RCON2170`, `RCONJA22`,
`RCON3123` and `RCON3545`. `TotalAssets` retains the existing adjusted definition:
`RCON2170 - RCONJA22 + RCON3123` from 2018Q1 onward, and `RCON2170 + RCON3123`
earlier. For the raw reported field, use `report.Value("RCON2170", date=date)`.
Other methods require their own reporting fields. `Certificate()` additionally
requires `FDIC Certificate Number`. Pass numeric observations; pandas' CSV reader
usually infers these from FFIEC numeric columns. A dictionary or pandas Series
with the same headers can also supply a bank row. Missing current-quarter headers
raise `KeyError`; installing the library does not supply bank data.

`CallReport_051` uses domestic reporting fields. `CallReport_031` exposes its
separate consolidated form definitions, including `RCFD` fields. Choose the form
appropriate to the supplied data; this library does not automatically infer or
substitute reporting forms. FFIEC 041 is not a separate implemented class.

Methods retain the existing definitions, historical field changes, missing-value
behavior and implemented `name=True` labels. Label support varies by method, as
described below. `safe_divide` preserves missing observations and
returns zero for a known numerator divided by zero, matching the existing API.
Ordinary Python `/` uses the operands' own division behavior instead.

## Method arguments and returned values

The complete API index below lists every public report method, its exact
signature, additional argument choices and its `name` behavior. Capitalization
and spelling in method paths are significant.

### Values and descriptive names

Where implemented, `name=False` returns the reported or calculated value, and
`name=True` returns the descriptive string assigned to the schedule object's
`self.name`. This is the reporting label, rather than Python's method identifier.
For example, using a 051 report whose row contains `RCON1754`:

```python
date = "P0"
value = report.Securities.Total(
    accounting="htm", valuation="ac", name=False, date=date
)
label = report.Securities.Total(
    accounting="htm", valuation="ac", name=True, date=date
)
print(label, value)
# Total Held-to-Maturity Securities at Amortized Cost <value of RCON1754>
```

The returned label also becomes `report.Securities.name`. Another method call on
that same schedule can replace this attribute; retain the returned string when
you need a particular label. A label call can still read reporting fields before
returning, so it requires a suitable bank row.

Label support is incomplete in the existing definitions. For example,
`BalanceSheet.TotalAssets(name=True)` and
`Securities.USTreasuries(accounting="htm", valuation="ac", name=True)`
return their normal values. `Securities.ABS` has label branches for `htm/ac` and
`afs/fv`, while its `htm/fv` and `afs/ac` branches return values even with
`name=True`. The index marks methods with explicit label branches and methods
that ignore `name`; branch labels can also depend on the selected arguments and
reporting date. Descriptive strings retain their existing wording and may
contain legacy terminology or typographical errors.

### Accounting classification and valuation

Securities methods with these parameters accept the following lowercase strings:

| Argument | Value | Meaning |
| --- | --- | --- |
| `accounting` | `"htm"` | Held-to-maturity |
| `accounting` | `"afs"` | Available-for-sale |
| `valuation` | `"ac"` | Amortized cost |
| `valuation` | `"fv"` | Fair value |

```python
treasuries_htm_ac = report.Securities.USTreasuries(
    accounting="htm", valuation="ac", date=date
)
treasuries_afs_fv = report.Securities.USTreasuries(
    accounting="afs", valuation="fv", date=date
)
```

For `USTreasuries`, the header choices are:

| Accounting / valuation | `CallReport_051` | `CallReport_031` |
| --- | --- | --- |
| `htm / ac` | `RCON0211` | `RCFD0211` |
| `htm / fv` | `RCON0213` | `RCFD0213` |
| `afs / ac` | `RCON1286` | `RCFD1286` |
| `afs / fv` | `RCON1287` | `RCFD1287` |

These are explicit named parameters in the relevant signatures, even though the
methods also accept `**kwargs`. Supply both parameters for securities methods
that require them; other methods have different arguments.

### Columns, ratings and option claims

Use the choices listed for the specific method in the index:

- `column="domestic"` or `"consolidated"` selects office coverage on relevant
  loan methods; it is separate from the chosen report class.
- Past-due methods use columns `"A"`, `"B"`, `"C"`, with aliases
  `"past due 30 days"`, `"past due 90 days"`, `"nonaccrual"` where listed.
- Fair-value methods use columns `"A"` through `"E"`; where listed,
  `"Level 1"`, `"Level 2"`, `"Level 3"` alias `"C"`, `"D"`, `"E"`.
- Credit-derivative maturity methods use `rating="IG"` or `"SubIG"`.
- Applicable option-derivative methods use `claim="written"` or `"purchased"`.
- `Value(column=...)` accepts an actual header from the supplied row.
- `BalanceSheet.LoansAndLeaseFinancingReceivables.Total(validate=True)` compares
  the reported total with its components, records `flags` and `messages` on that
  schedule and prints a mismatch. It returns the reported total.

For example:

```python
domestic_loans = report.LoansAndLeases.Total(column="domestic", date=date)
past_due = report.NonaccrualPastDue.LoansAndLeaseFinancingReceivables.Total(
    column="A", date=date
)
```

Some methods retain unused arguments, identified in the index. Invalid strings
are not handled uniformly: depending on the method, an unrecognized selection
can return `None` or raise an error. `*args` and `**kwargs` do not provide a
general option system; many methods accept and ignore extra arguments. Use the
documented parameters and exact choices rather than relying on ignored options.

## Historical dates

`date="P0"` means the bound row's quarter. `P1Q`, `P2Q`, `P3Q` and `P1Y`
refer to one, two, three and four calendar quarters earlier. Supply the historical
rows explicitly; the library never downloads them or searches a Basel3 checkout:

```python
from callreports import CallReport_051, QuarterCache

history = QuarterCache(frames={20231231: previous_quarter_table})
report = CallReport_051(row, history=history)
previous_assets = report.BalanceSheet.TotalAssets(date="P1Q")
```

Historical rows match by `IDRSSD`, independently of row order. A `frames` mapping
may contain several quarter DataFrames; a single DataFrame with several quarters
is also accepted. For files, use `QuarterCache(data_dir="prepared")`; it reads
`Cleaned_Call_Report_YYYYMMDD.csv`, including the quarter folders produced below.
Ambiguous files and duplicate historical bank rows raise an error.

Without a supplied map, lag dates follow calendar quarter ends. An explicit
`map_file` path or DataFrame preserves custom mappings with columns `P0`, `P1Q`,
`P2Q`, `P3Q`, `P1Y` and optional `Quarter`. Missing historical observations remain
missing rather than being taken from the current quarter. The API expects valid
calendar quarter-end dates in `RCON9999` when using calendar lags.

## Prepare a downloaded FFIEC ZIP

Use a local **Call Reports — Single Period**, tab-delimited ZIP containing one
quarter's POR and ENT files and the desired schedules:

```sh
callreports prepare "Call_Reports_20240331.zip" --output-dir prepared
```

The equivalent command is `python3 -m callreports prepare ...`. No network request
is made. The reporting date is inferred from the FFIEC filenames; `--date
20240331` can specify it explicitly and must agree with those filenames.

The result is:

```text
prepared/20240331/
├── TXT/                                      # extracted originals
├── Schedules/                                # individual schedule CSVs
└── Cleaned_Call_Report_20240331.csv           # merged bank-quarter table
```

The Python equivalent returns the merged CSV's path:

```python
from callreports import prepare_archive

csv_path = prepare_archive("Call_Reports_20240331.zip", "prepared")
table = pd.read_csv(csv_path, low_memory=False)
report = CallReport_051(table.iloc[0])
```

Preparation attaches FDIC certificates using POR, drops TXT description rows and
merges all available schedules by `IDRSSD`. Ancillary files such as `Readme.txt`
are retained in TXT but are not treated as schedules. ENT defines the bank population and
order. A repeated column retains its first value, with ENT first and remaining
schedule filenames sorted. It sets `RCON9999` to the validated reporting date and
removes the legacy `RCON9224` text field. Other fields, text values and missing
observations are preserved. This is a structural merge, not statistical cleaning.

Mixed quarters, duplicate bank identifiers, invalid archives and inconsistent
reporting dates fail explicitly. Preparation stages a complete quarter before
publishing its directory and refuses to replace an existing quarter directory.
Source ZIPs remain unchanged. Archive limits are 512 MiB compressed and 2 GiB
uncompressed; unsafe member paths, links and duplicate names are rejected.

## Use extracted TXT or schedule CSVs

Each command operates on one reporting quarter:

```sh
callreports convert "downloaded-quarter" --output-dir schedules
callreports merge schedules --output Cleaned_Call_Report_20240331.csv
```

The corresponding functions are `convert_txt_to_csv(input_dir, output_dir)` and
`merge_schedules(input_dir, output_file=None, reporting_date=None)`.
`merge_schedules` returns a DataFrame, whether or not an output file is requested.
Lower-level `merge_schedule_files(base_file, files_to_append, output_file=None)`
supports an explicit subset of schedules, skips absent optional paths and returns
the merged DataFrame without applying the reporting-date cleanup.

## Basel3 integration and limits

Basel3 imports the report definitions as a dependency. Its conversion and merge
scripts, selected schedule list, 76 research ratios, cohort definitions and
distribution comparisons remain in Basel3. Consumers import the public definitions
directly from `callreports`.

The standalone merge includes all available schedules; Basel3 intentionally
retains its historical schedule selection. Local ZIP preparation does not include
Basel3's YAML-driven FFIEC downloader. Coverage depends on the implemented 031/051
methods and available source headers; it does not establish completeness across
all reporting forms, historical revisions or regulatory interpretations.

Package and existing Call Report regressions run from the repository root after
installing the development requirements:

```sh
python3 -m unittest discover -s tests -p 'test_callreports_package.py' -v
python3 -m unittest discover -s tests -p 'test_call_report*.py' -v
python3 -m unittest discover -s tests -p 'test_dynamic_ratios.py' -v
```

This directory is the source used to build and maintain the PyPI package.
Basel3 installs a released version through `requirements.txt`; its pipeline
scripts are in the separate `src/call reports/` directory.

## Shared classes and functions

Import public entry points from `callreports`. Report constructors accept one
bank row; their nested schedule classes are constructed automatically. Use
`report.BalanceSheet`, `report.Securities`, and the other paths below instead of
constructing nested schedule classes yourself. Private names beginning with an
underscore are implementation details and are excluded from this reference.

| Class or object | Construction and purpose |
| --- | --- |
| `CallReport_031(row, history=None)` | Consolidated 031 form definitions. |
| `CallReport_051(row, history=None)` | Domestic 051 form definitions. |
| `QuarterCache(map_file=None, data_dir=None, frames=None)` | Explicit historical bank rows and quarter mapping. |
| `Global_uc(row)` | Change, averaging, annualization and percentage helpers. |
| `LagSupport` | Base class implementing report date and row lookup; use the methods inherited by report instances. |
| `DEFAULT_HISTORY` | Empty default QuarterCache; it does not contain or download bank data. |

### Preparation and arithmetic functions

| Function | Result |
| --- | --- |
| `safe_divide(numerator, denominator)` | Divide two scalars; missing inputs give NaN and a known numerator divided by zero gives zero. |
| `extract_archive(archive_path, output_dir)` | Validate and extract a local ZIP into a new directory; return the output directory Path. |
| `convert_txt_to_csv(input_dir, output_dir, delimiter='\t', encoding='utf-8-sig')` | Convert one quarter of TXT schedules and attach POR certificate identifiers; return the written CSV Paths. |
| `merge_schedule_files(base_file, files_to_append, output_file=None)` | Left-join an explicit schedule subset by IDRSSD; return a DataFrame and optionally write it. |
| `clean_report(table, reporting_date)` | Return a copy with RCON9224 removed and RCON9999 set to the validated reporting date. |
| `merge_schedules(input_dir, output_file=None, reporting_date=None)` | Merge all supplied quarter schedules, apply reporting-date cleanup and return a DataFrame; optionally write it. |
| `prepare_archive(archive_path, output_dir, reporting_date=None)` | Extract, convert and merge a local quarter ZIP; return the completed merged CSV Path. |

### Historical and percentage helper methods

`actual` and `anchor` are reporting dates such as `20240331`; `rssd` is the bank
IDRSSD. `date` uses the period codes explained above. Change, averaging and
annualization helpers need a bound report method so they can resolve its bank
and historical rows. They forward additional method arguments, including
accounting and valuation selections. Percentage helpers accept their documented
bound methods or numeric operands; a change helper given an unbound number
cannot identify a report history. Missing observations remain NaN; historical
division uses the same known-zero-denominator convention described above.

```python
from callreports import Global_uc

helper = Global_uc(row)
assets_change = helper.CHANGE1Q(report.BalanceSheet.TotalAssets, date="P0")
treasury_change = helper.CHANGE1Q(
    report.Securities.USTreasuries, accounting="htm", valuation="ac", date="P0"
)
```

| Method | Behavior |
| --- | --- |
| `QuarterCache.resolve(anchor, date='P0')` | Resolve an anchor quarter and period code to a reporting date; return `None` when unresolved. |
| `QuarterCache.previous(actual, quarters=1)` | Return the calendar reporting date a number of quarters before `actual`. |
| `QuarterCache.quarter(actual)` | Return the quarter number (1–4) for a valid quarter-end date. |
| `QuarterCache.frame(actual)` | Return the supplied historical quarter DataFrame indexed by IDRSSD, or `None`. |
| `QuarterCache.row(actual, rssd)` | Return one historical bank row for `actual` and `rssd`, or `None`. |
| `QuarterCache.columns(actual)` | Return the available headers for a historical quarter. |
| `LagSupport.actual_date(date='P0')` | Resolve the selected report period to its actual reporting date. |
| `LagSupport.get_row(date='P0')` | Return the selected bank row; unavailable history has missing observations. |
| `Global_uc.CHANGE1Q(value, *args, date='P0', **kwargs)` | Fractional change from one quarter earlier: `(current - prior) / prior`. |
| `Global_uc.CHANGE2Q(value, *args, date='P0', **kwargs)` | Fractional change from two quarters earlier. |
| `Global_uc.CHANGE3Q(value, *args, date='P0', **kwargs)` | Fractional change from three quarters earlier. |
| `Global_uc.CHANGE1Y(value, *args, date='P0', **kwargs)` | Fractional change from four quarters earlier. |
| `Global_uc.CAVG04X(value, *args, date='P0', **kwargs)` | Average the bound method across available quarter ends in the selected calendar year to date; required missing values produce NaN. |
| `Global_uc.ANN(value, *args, date='P0', **kwargs)` | Multiply the selected bound-method value by `4 / quarter_number`. |
| `Global_uc.PCTANN(numerator, denominator, *args, date='P0', **kwargs)` | Annualize the numerator and divide by the denominator; returns a fraction. |
| `Global_uc.PCTOFANN(numerator, denominator, *args, date='P0', **kwargs)` | Return `PCTANN * 100`. |
| `Global_uc.PCTOF(numerator, denominator, *args, date='P0', **kwargs)` | Return numerator / denominator multiplied by 100. |
| `Global_uc.PCT(numerator, denominator, *args, date='P0', **kwargs)` | Alias for PCTOF. |

## Complete report method index

Every method path is relative to a constructed report instance of the named
form. For example, under `CallReport_051.Securities`, call
`report.Securities.Total(...)`. Selectors and names are case-sensitive.

**Branch labels** means the implementation contains descriptive-name branches.
It does not promise a label for every date or selector combination. **Ignored**
means the accepted `name` argument does not switch that method to a label.
The header column lists direct or statically selected source fields across all
date branches; a particular date may use only a subset. Composite methods also
need the fields used by their callees. Normal missing-field and historical-data
rules still apply to methods called for their labels.

## CallReport 031 reference

Constructor: `CallReport_031(row, history=None)`. These methods also inherit
`actual_date(date="P0")` and `get_row(date="P0")` from `LagSupport`.

### `CallReport_031`

Nested schedules: `Maturities`, `RegulatoryCapital`, `BalanceSheet`, `Securities`, `LoansAndLeases`, `DepositLiabilities`, `OtherLiabilities`, `DerivativesOffBalanceSheet`, `NonaccrualPastDue`, `DepositInsurance`, `MeasuredAtFV`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `RSSDID(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `IDRSSD` |
| `ReportingDate(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON9999` |
| `Certificate(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `FDIC Certificate Number` |
| `Value(column, name=False, *args, date='P0', **kwargs)` | `column`: a header in the supplied row | Ignored | Uses other methods or a supplied header |

### `CallReport_031.Maturities`

Nested schedules: `Government`, `ResidentialMortgage`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Values(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.Maturities.Government`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA549` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA550` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA551` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA552` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA553` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA554` |
| `Values(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.Maturities.ResidentialMortgage`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA555` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA556` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA557` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA558` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA559` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA560` |
| `Values(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.RegulatoryCapital`

Nested schedules: `EquityCapital`, `CET1`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `RiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFAA223` |
| `TierOneCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFAP840` |
| `CommonEquityTierOneCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFAP859` |
| `AugmentedRiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ZeroRiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDB696`, `RCOND987` |
| `ZeroRiskWeightExposureRatio(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON1754`, `RCON1773`, `RCONB603`, `RCONB608`, `RCFD1754`, `RCFD1773`, `RCOND962`, `RCOND967` |
| `RiskWeightAdjustment(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `AdjustedZeroRiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ZeroRiskToReportedRWA(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ZeroRiskToAugmentedRWA(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `AdjustedZeroRiskToAugmentedRWA(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `RelativeZeroRiskAdjustment(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.RegulatoryCapital.EquityCapital`

Nested schedules: `AOCI`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAB530`, `RCFAP742`, `RCFAKW00` |
| `CommonStockSurplus(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP742` |
| `RetainedEarnings(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAKW00` |
| `CECLDesignation(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAJJ29` |

### `CallReport_031.RegulatoryCapital.EquityCapital.AOCI`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `BeforeAdjustments(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAKW00` |
| `OptOutElection(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP838` |
| `AFSSecuritiesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP844` |
| `CashFlowHedgesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP846` |
| `DefinedBenefits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP847` |
| `HTMSecuritiesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP848` |
| `AOCICashFlowHedgesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP849` |

### `CallReport_031.RegulatoryCapital.CET1`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `MinorityInterests(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP839` |
| `BeforeDeductions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFAP840` |

### `CallReport_031.BalanceSheet`

Nested schedules: `LoansAndLeaseFinancingReceivables`, `DepositDomesticOffices`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CashAndBalancesDue(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD0081`, `RCFD0071` |
| `TotalSecurities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDJA22`, `RCFD1754`, `RCFD1773`, `RCFDJJ34` |
| `HTMSecurities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDJJ34`, `RCFD1754` |
| `AFSSecurities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD1773` |
| `TradingAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD3545` |
| `OtherRealEstateOwned(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD2150` |
| `IntangibleAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD2143`, `RCFD3163`, `RCFD0426` |
| `TotalAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD3123`, `RCFD2170`, `RCFDJA22` |
| `FederalFundsPurchased(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONB993`, `RCFDB995` |
| `FederalFundsSold(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONB987`, `RCFDB989` |
| `TradingLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD3548` |
| `OtherLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD2930` |
| `OtherBorrowedMoney(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD3190` |
| `TotalLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD2948` |
| `TotalLiabilitiesIncludingAllowance(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ReportedTotalEquityCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDG105` |
| `TotalEquityCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDG105`, `RCFDJA22` |

### `CallReport_031.BalanceSheet.LoansAndLeaseFinancingReceivables`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(validate=False, name=False, *args, date='P0', **kwargs)` | `validate`: `False`, `True` | Ignored | `RCFDB529` |
| `LoansAndLeasesHeldForSale(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD5369` |
| `LoansAndLeasesHeldForInvestment(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDB528` |
| `AllowanceForCreditLossesOnLoansAndLeases(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFD3123` |
| `TotalIncludingHeldForSale(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.BalanceSheet.DepositDomesticOffices`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `NonInterestBearing(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON6631` |
| `InterestBearing(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON6636` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.Securities`

Nested schedules: `ResidentialPassThru`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `USTreasuries(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFD0211`, `RCFD0213`, `RCFD1286`, `RCFD1287` |
| `USGovtObligations(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDHT50`, `RCFDHT51`, `RCFDHT52`, `RCFD1289`, `RCFD1294`, `RCFDHT53`, `RCFD1290`, `RCFD1295`, `RCFD1291`, `RCFD1297`, `RCFD1293`, `RCFD1298` |
| `StateSecurities(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFD8496`, `RCFD8497`, `RCFD8498`, `RCFD8499` |
| `OtherResidentialPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | Uses other methods or a supplied header |
| `OtherResidentialGNMA(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG312`, `RCFDG313`, `RCFDG314`, `RCFDG315` |
| `OtherResidentialFNMA(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG316`, `RCFDG317`, `RCFDG318`, `RCFDG319` |
| `OtherResidentialOther(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG320`, `RCFDG321`, `RCFDG322`, `RCFDG323` |
| `CommericalPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG324`, `RCFDK142`, `RCFDK146`, `RCFDG325`, `RCFDG326`, `RCFDK143`, `RCFDK147`, `RCFDK144`, `RCFDK148`, `RCFDG327`, `RCFDK145`, `RCFDK149` |
| `OtherCommericalMBS(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG328`, `RCFDK150`, `RCFDK154`, `RCFDG329`, `RCFDG330`, `RCFDK151`, `RCFDK155`, `RCFDK152`, `RCFDK156`, `RCFDG331`, `RCFDK153`, `RCFDK157` |
| `GNMAPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG300`, `RCFDG301`, `RCFDG302`, `RCFDG303` |
| `FNMAPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG304`, `RCFDG305`, `RCFDG306`, `RCFDG307` |
| `OtherPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCFDG308`, `RCFDG309`, `RCFDG310`, `RCFDG311` |
| `MBSTotal(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | Uses other methods or a supplied header |
| `ABS(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | `RCFDC026`, `RCFDC988`, `RCFDC989`, `RCFDC027` |
| `OtherDebtSecurities(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | `RCFD1737`, `RCFD1742`, `RCFD1738`, `RCFD1743`, `RCFD1739`, `RCFD1744`, `RCFD1741`, `RCFD1746` |
| `Total(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | `RCFD1754`, `RCFD1771`, `RCFD1772`, `RCFD1773` |

### `CallReport_031.Securities.ResidentialPassThru`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | Uses other methods or a supplied header |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA555` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA556` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA557` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA558` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA559` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCFDA560` |

### `CallReport_031.LoansAndLeases`

Nested schedules: `SecuredRealEstate`, `Individuals`, `ExcludingClosedEnd`, `DepositoryInstitutions`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON2122`, `RCFD2122` |
| `ForeignGovt(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON2081`, `RCFD2081` |
| `StatesAndPolitical(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON2107`, `RCFD2107` |
| `NonDepository(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ454` |
| `NonDepositoryOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ464` |
| `UnearnedIncome(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2123` |

### `CallReport_031.LoansAndLeases.SecuredRealEstate`

Nested schedules: `SFR`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'` | Branch labels | Uses other methods or a supplied header |
| `ConstructionSFR(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONF158`, `RCFDF158` |
| `ConstructionOther(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONF159`, `RCFDF159` |
| `Farmland(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON1420`, `RCFD1420` |
| `FinanceAgricultural(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON1590`, `RCFD1590` |
| `CommercialAndIndustrial(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON1763`, `RCON1764`, `RCFD1763`, `RCFD1764` |
| `multifamily(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON1460`, `RCFD1460` |
| `SecuredNonfarmOwner(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONF160`, `RCFDF160` |
| `SecuredNonfarmOther(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONF161`, `RCFDF161` |

### `CallReport_031.LoansAndLeases.SecuredRealEstate.SFR`

Nested schedules: `ClosedEndFirstLiens`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `OpenEndRevolving(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON1797`, `RCFD1797` |

### `CallReport_031.LoansAndLeases.SecuredRealEstate.SFR.ClosedEndFirstLiens`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, column='domestic', *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON5367`, `RCFD5367` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA564` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA565` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA566` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA567` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA568` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA569` |

### `CallReport_031.LoansAndLeases.Individuals`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CreditCardLines(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONB538`, `RCFDB538` |
| `RevolvingCredit(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONB539`, `RCFDB539` |
| `AutomobileLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONK137`, `RCFDK137` |
| `ConsumerLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONK207`, `RCFDK207` |

### `CallReport_031.LoansAndLeases.ExcludingClosedEnd`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCON2165`, `RCONJ451`, `RCFDF163`, `RCON1545`, `RCFDF162`, `RCONJ454`, `RCFD1563`, `RCON2107`, `RCFD2107`, `RCON2081`, `RCFD2081`, `RCONK207`, `RCFDK207`, `RCONK137`, `RCFDK137`, `RCONB539`, `RCFDB539`, `RCONB538`, `RCFDB538`, `RCON1764`, `RCFD1764`, `RCON1763`, `RCFD1763`, `RCON1590`, `RCFD1590`, `RCONB535`, `RCFDB537`, `RCONB534`, `RCFDB536`, `RCONB531`, `RCFDB534`, `RCONF161`, `RCFDB533`, `RCONF160`, `RCFDB532`, `RCON1460`, `RCFDF161`, `RCON5368`, `RCFDF160`, `RCON1797`, `RCFD1460`, `RCON1420`, `RCFD5368`, `RCONF158`, `RCONF159`, `RCFD1797`, `RCFD1420`, `RCFDF158`, `RCFDF159` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA570` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA571` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA572` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA573` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA574` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA575` |

### `CallReport_031.LoansAndLeases.DepositoryInstitutions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | Uses other methods or a supplied header |
| `USBanksTotal(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | Uses other methods or a supplied header |
| `CommercialBanks(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONB531`, `RCFDB532`, `RCFDB533` |
| `Other(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONB534`, `RCFDB534` |
| `ForeignCountries(column, name=False, *args, date='P0', **kwargs)` | `column`: `'domestic'`, `'consolidated'` | Branch labels | `RCONB535`, `RCFDB536`, `RCFDB537` |

### `CallReport_031.DepositLiabilities`

Nested schedules: `TransactionDeposits`, `NonTransactionDeposits`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2200` |
| `DomesticDeposits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `Individuals(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `USGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `CommercialBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `ForeignBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `ForeignGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_031.DepositLiabilities.TransactionDeposits`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Individuals(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB549` |
| `USGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2202` |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2203` |
| `CommercialBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB551` |
| `ForeignBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2213` |
| `ForeignGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2216` |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2215` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2215` |

### `CallReport_031.DepositLiabilities.NonTransactionDeposits`

Nested schedules: `TimeDeposits`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Individuals(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB550` |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2385` |
| `USGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2520` |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2530` |
| `CommercialBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB552` |
| `ForeignBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2236` |
| `ForeignGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2377` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2385` |
| `SavingsMMDA(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON6810` |
| `SavingsOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON0352` |
| `SavingsTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_031.DepositLiabilities.NonTransactionDeposits.TimeDeposits`

Nested schedules: `LessThan250k`, `MoreThan250k`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `LessThan100k(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON6648` |
| `MoreThan100kLessThan250k(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ473`, `RCON6648` |

### `CallReport_031.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONJ473` |
| `EffectiveThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA579` |
| `EffectiveTwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA580` |
| `EffectiveThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA581` |
| `EffectiveOverThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA582` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ473` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK07` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK08` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK09` |
| `OverThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK10` |

### `CallReport_031.DepositLiabilities.NonTransactionDeposits.TimeDeposits.MoreThan250k`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONJ474` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ474` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK12` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK13` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK14` |
| `OverThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK15` |

### `CallReport_031.OtherLiabilities`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `InterestAccrued(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON3645` |
| `ExpensesAccruedOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD3646` |
| `DTLsNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD3049` |
| `CreditLosses(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDB557` |
| `AllOtherLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD2938` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD2930` |

### `CallReport_031.DerivativesOffBalanceSheet`

Nested schedules: `CreditDerivatives`, `OtherDerivatives`.

### `CallReport_031.DerivativesOffBalanceSheet.CreditDerivatives`

Nested schedules: `SoldProtection`, `PurchasedProtection`.

### `CallReport_031.DerivativesOffBalanceSheet.CreditDerivatives.SoldProtection`

Nested schedules: `Notional`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CDS(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC968` |
| `TotalReturnSwaps(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC970` |
| `CreditOptions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC972` |
| `OtherCreditDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC974` |
| `MarketRiskRule(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDG401` |

### `CallReport_031.DerivativesOffBalanceSheet.CreditDerivatives.SoldProtection.Notional`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TwelveMonths(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCFDG406`, `RCFDG409` |
| `FiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCFDG407`, `RCFDG410` |
| `OverFiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCFDG408`, `RCFDG411` |
| `InvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `SubInvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_031.DerivativesOffBalanceSheet.CreditDerivatives.PurchasedProtection`

Nested schedules: `Notional`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CDS(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC969` |
| `TotalReturnSwaps(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC971` |
| `CreditOptions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC973` |
| `OtherCreditDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDC975` |
| `MarketRiskRule(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDG402` |

### `CallReport_031.DerivativesOffBalanceSheet.CreditDerivatives.PurchasedProtection.Notional`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TwelveMonths(rating='IG', name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCFDG412`, `RCFDG415` |
| `FiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCFDG413`, `RCFDG416` |
| `OverFiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCFDG414`, `RCFDG417` |
| `InvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `SubInvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives`

Nested schedules: `HeldForTrading`, `NotHeldForTrading`, `Futures`, `Forwards`, `ETDOptions`, `OTCOptions`, `Swaps`.

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.HeldForTrading`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA126` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDA127` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8723` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8724` |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.NotHeldForTrading`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8725` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8726` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8727` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8728` |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.Futures`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8693` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8694` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8695` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8696` |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.Forwards`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8697` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8698` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8699` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8700` |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.ETDOptions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalWritten(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalPurchased(claim, name=False, *args, date='P0', **kwargs)` | `claim`: accepted but unused | Branch labels | Uses other methods or a supplied header |
| `InterestRates(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8701`, `RCFD8705` |
| `ForeignExchange(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8702`, `RCFD8706` |
| `EquityDerivatives(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8703`, `RCFD8707` |
| `CommoditiesOther(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8704`, `RCFD8708` |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.OTCOptions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalWritten(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalPurchased(claim, name=False, *args, date='P0', **kwargs)` | `claim`: accepted but unused | Branch labels | Uses other methods or a supplied header |
| `InterestRates(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8709`, `RCFD8713` |
| `ForeignExchange(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8710`, `RCFD8714` |
| `EquityDerivatives(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8711`, `RCFD8715` |
| `CommoditiesOther(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCFD8712`, `RCFD8716` |

### `CallReport_031.DerivativesOffBalanceSheet.OtherDerivatives.Swaps`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD3450` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD3826` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8719` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFD8720` |

### `CallReport_031.NonaccrualPastDue`

Nested schedules: `LoansAndLeaseFinancingReceivables`, `SecuredRealEstate`, `DepositoryInstitutions`, `Individuals`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `FinanceAgricultural(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD1594`, `RCFD1597`, `RCFD1583` |
| `CommercialAndIndustrial(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD1251`, `RCFD1252`, `RCFD1253` |
| `ForeignGovt(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD5389`, `RCFD5390`, `RCFD5391` |
| `AllOtherLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD5459`, `RCFD5460`, `RCFD5461` |
| `LeaseFinancingReceivables(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFDF166`, `RCFDF169`, `RCFDF167`, `RCFDF170`, `RCFDF168`, `RCFDF171` |

### `CallReport_031.NonaccrualPastDue.LoansAndLeaseFinancingReceivables`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD1406`, `RCFD1407`, `RCFD1403` |
| `GuaranteedByUSGovt(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFDK036`, `RCFDK037`, `RCFDK038` |
| `LoansAndLeasesHeldForSale(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFDC240`, `RCFDC241`, `RCFDC226` |

### `CallReport_031.NonaccrualPastDue.SecuredRealEstate`

Nested schedules: `SFR`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ConstructionSFR(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF172`, `RCONF174`, `RCONF176` |
| `ConstructionOther(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF173`, `RCONF175`, `RCONF177` |
| `Farmland(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON3493`, `RCON3494`, `RCON3495` |
| `SecuredMultifamily(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON3499`, `RCON3500`, `RCON3501` |
| `SecuredNonfarmOwner(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF178`, `RCONF180`, `RCONF182` |
| `SecuredNonfarmOther(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF179`, `RCONF181`, `RCONF183` |

### `CallReport_031.NonaccrualPastDue.SecuredRealEstate.SFR`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `OpenEndRevolving(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON5398`, `RCON5399`, `RCON5400` |
| `ClosedEndFirstLiens(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONC236`, `RCONC237`, `RCONC229` |
| `ClosedEndJuniorLiens(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONC238`, `RCONC239`, `RCONC230` |

### `CallReport_031.NonaccrualPastDue.DepositoryInstitutions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `USBanksTotal(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD5377`, `RCFD5378`, `RCFD5379` |
| `ForeignBanks(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFD5380`, `RCFD5381`, `RCFD5382` |

### `CallReport_031.NonaccrualPastDue.Individuals`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CreditCards(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFDB575`, `RCFDB576`, `RCFDB577` |
| `AutomobileLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFDK213`, `RCFDK214`, `RCFDK215` |
| `OtherLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCFDK216`, `RCFDK217`, `RCFDK218` |

### `CallReport_031.DepositInsurance`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Section3IDeposits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDF236` |
| `TotalAllowableExclusions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCFDF237` |
| `TotalForeignDeposits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_031.MeasuredAtFV`

Nested schedules: `TradingAssets`, `TradingLiabilities`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `AFSSecurities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDJA36`, `RCFDG474`, `RCFDG475`, `RCFDG476`, `RCFDG477` |
| `FederalFundsSold(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG478`, `RCFDG479`, `RCFDG480`, `RCFDG481`, `RCFDG482` |
| `LoansAndLeasesHeldForSale(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG483`, `RCFDG484`, `RCFDG485`, `RCFDG486`, `RCFDG487` |
| `LoansAndLeasesHeldForInvestment(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG488`, `RCFDG489`, `RCFDG490`, `RCFDG491`, `RCFDG492` |
| `AllOtherAssets(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG391`, `RCFDG392`, `RCFDG395`, `RCFDG396`, `RCFDG804` |
| `DepositLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDF252`, `RCFDF686`, `RCFDF694`, `RCFDF253`, `RCFDF254` |
| `FederalFundsPurchased(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG507`, `RCFDG508`, `RCFDG509`, `RCFDG510`, `RCFDG511` |
| `SubordinatedNotes(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG526`, `RCFDG527`, `RCFDG528`, `RCFDG529`, `RCFDG530` |
| `OtherLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG805`, `RCFDG806`, `RCFDG807`, `RCFDG808`, `RCFDG809` |
| `TotalLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG531`, `RCFDG532`, `RCFDG533`, `RCFDG534`, `RCFDG535` |
| `MSAs(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG536`, `RCFDG537`, `RCFDG538`, `RCFDG539`, `RCFDG540` |

### `CallReport_031.MeasuredAtFV.TradingAssets`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFD3543`, `RCFDG497`, `RCFDG493`, `RCFDG498`, `RCFDG494`, `RCFDG499`, `RCFDG495`, `RCFDG500`, `RCFDG496`, `RCFDG501` |
| `Derivatives(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFD3543`, `RCFDG493`, `RCFDG494`, `RCFDG495`, `RCFDG496` |
| `OtherAssets(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG497`, `RCFDG498`, `RCFDG499`, `RCFDG500`, `RCFDG501` |

### `CallReport_031.MeasuredAtFV.TradingLiabilities`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFD3547`, `RCFDG516`, `RCFDG512`, `RCFDG517`, `RCFDG513`, `RCFDG518`, `RCFDG514`, `RCFDG519`, `RCFDG515`, `RCFDG520` |
| `Derivatives(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFD3547`, `RCFDG512`, `RCFDG513`, `RCFDG514`, `RCFDG515` |
| `OtherLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCFDG516`, `RCFDG517`, `RCFDG518`, `RCFDG519`, `RCFDG520` |

## CallReport 051 reference

Constructor: `CallReport_051(row, history=None)`. These methods also inherit
`actual_date(date="P0")` and `get_row(date="P0")` from `LagSupport`.

### `CallReport_051`

Nested schedules: `Maturities`, `RegulatoryCapital`, `BalanceSheet`, `Securities`, `LoansAndLeases`, `DepositLiabilities`, `OtherLiabilities`, `DerivativesOffBalanceSheet`, `NonaccrualPastDue`, `DepositInsurance`, `MeasuredAtFV`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `RSSDID(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `IDRSSD` |
| `ReportingDate(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON9999` |
| `Certificate(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `FDIC Certificate Number` |
| `Value(column, name=False, *args, date='P0', **kwargs)` | `column`: a header in the supplied row | Ignored | Uses other methods or a supplied header |

### `CallReport_051.Maturities`

Nested schedules: `Government`, `ResidentialMortgage`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Values(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.Maturities.Government`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA549` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA550` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA551` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA552` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA553` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA554` |
| `Values(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.Maturities.ResidentialMortgage`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA555` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA556` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA557` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA558` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA559` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA560` |
| `Values(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.RegulatoryCapital`

Nested schedules: `EquityCapital`, `CET1`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `RiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCOAA223` |
| `TierOneCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCOAP840` |
| `CommonEquityTierOneCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCOAP859` |
| `AugmentedRiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ZeroRiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONB696`, `RCOND987` |
| `ZeroRiskWeightExposureRatio(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON1754`, `RCON1773`, `RCONB603`, `RCONB608`, `RCOND962`, `RCOND967` |
| `RiskWeightAdjustment(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `AdjustedZeroRiskWeightedAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ZeroRiskToReportedRWA(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ZeroRiskToAugmentedRWA(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `AdjustedZeroRiskToAugmentedRWA(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `RelativeZeroRiskAdjustment(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.RegulatoryCapital.EquityCapital`

Nested schedules: `AOCI`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAB530`, `RCOAP742`, `RCOAKW00` |
| `CommonStockSurplus(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP742` |
| `RetainedEarnings(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAKW00` |
| `CECLDesignation(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAJJ29` |

### `CallReport_051.RegulatoryCapital.EquityCapital.AOCI`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `BeforeAdjustments(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAKW00` |
| `OptOutElection(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP838` |
| `AFSSecuritiesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP844` |
| `CashFlowHedgesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP846` |
| `DefinedBenefits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP847` |
| `HTMSecuritiesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP848` |
| `AOCICashFlowHedgesNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP849` |

### `CallReport_051.RegulatoryCapital.CET1`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `MinorityInterests(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP839` |
| `BeforeDeductions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCOAP840` |

### `CallReport_051.BalanceSheet`

Nested schedules: `LoansAndLeaseFinancingReceivables`, `DepositDomesticOffices`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CashAndBalancesDue(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON0081`, `RCON0071` |
| `TotalSecurities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONJA22`, `RCON1754`, `RCON1773`, `RCONJJ34` |
| `HTMSecurities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONJJ34`, `RCON1754` |
| `AFSSecurities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON1773` |
| `TradingAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON3545` |
| `OtherRealEstateOwned(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2150` |
| `IntangibleAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2143`, `RCON3163`, `RCON0426` |
| `TotalAssets(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON3123`, `RCON2170`, `RCONJA22` |
| `FederalFundsPurchased(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONB993`, `RCONB995` |
| `FederalFundsSold(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONB987`, `RCONB989` |
| `TradingLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON3548` |
| `OtherLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2930` |
| `OtherBorrowedMoney(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON3190` |
| `TotalLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2948` |
| `TotalLiabilitiesIncludingAllowance(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |
| `ReportedTotalEquityCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONG105` |
| `TotalEquityCapital(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONG105`, `RCONJA22` |

### `CallReport_051.BalanceSheet.LoansAndLeaseFinancingReceivables`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(validate=False, name=False, *args, date='P0', **kwargs)` | `validate`: `False`, `True` | Ignored | `RCONB529` |
| `LoansAndLeasesHeldForSale(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON5369` |
| `LoansAndLeasesHeldForInvestment(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONB528` |
| `AllowanceForCreditLossesOnLoansAndLeases(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON3123` |
| `TotalIncludingHeldForSale(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.BalanceSheet.DepositDomesticOffices`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `NonInterestBearing(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON6631` |
| `InterestBearing(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON6636` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.Securities`

Nested schedules: `ResidentialPassThru`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `USTreasuries(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCON0211`, `RCON0213`, `RCON1286`, `RCON1287` |
| `USGovtObligations(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONHT50`, `RCONHT51`, `RCONHT52`, `RCON1289`, `RCON1294`, `RCONHT53`, `RCON1290`, `RCON1295`, `RCON1291`, `RCON1297`, `RCON1293`, `RCON1298` |
| `StateSecurities(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCON8496`, `RCON8497`, `RCON8498`, `RCON8499` |
| `OtherResidentialPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | Uses other methods or a supplied header |
| `OtherResidentialGNMA(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG312`, `RCONG313`, `RCONG314`, `RCONG315` |
| `OtherResidentialFNMA(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG316`, `RCONG317`, `RCONG318`, `RCONG319` |
| `OtherResidentialOther(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG320`, `RCONG321`, `RCONG322`, `RCONG323` |
| `CommericalPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG324`, `RCONK142`, `RCONK146`, `RCONG325`, `RCONG326`, `RCONK143`, `RCONK147`, `RCONK144`, `RCONK148`, `RCONG327`, `RCONK145`, `RCONK149` |
| `OtherCommericalMBS(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG328`, `RCONK150`, `RCONK154`, `RCONG329`, `RCONG330`, `RCONK151`, `RCONK155`, `RCONK152`, `RCONK156`, `RCONG331`, `RCONK153`, `RCONK157` |
| `GNMAPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG300`, `RCONG301`, `RCONG302`, `RCONG303` |
| `FNMAPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG304`, `RCONG305`, `RCONG306`, `RCONG307` |
| `OtherPassThru(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | `RCONG308`, `RCONG309`, `RCONG310`, `RCONG311` |
| `MBSTotal(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | Uses other methods or a supplied header |
| `ABS(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | `RCONC026`, `RCONC988`, `RCONC989`, `RCONC027` |
| `OtherDebtSecurities(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | `RCON1737`, `RCON1742`, `RCON1738`, `RCON1743`, `RCON1739`, `RCON1744`, `RCON1741`, `RCON1746` |
| `Total(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Branch labels | `RCON1754`, `RCON1771`, `RCON1772`, `RCON1773` |

### `CallReport_051.Securities.ResidentialPassThru`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(accounting, valuation, name=False, *args, date='P0', **kwargs)` | `accounting`: `'htm'`, `'afs'`; `valuation`: `'ac'`, `'fv'` | Ignored | Uses other methods or a supplied header |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA555` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA556` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA557` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA558` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA559` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA560` |

### `CallReport_051.LoansAndLeases`

Nested schedules: `ExcludingClosedEnd`, `ClosedEndFirstLiens`, `SecuredRealEstate`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2122` |
| `FamilyResidentialConstruction(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF158` |
| `OtherConstruction(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF159` |
| `Farmland(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1420` |
| `OpenEndSecuredFamily(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1797` |
| `ClosedEndJuniorLiens(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON5368` |
| `SecuredMultifamily(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1460` |
| `SecuredNonfarmOwner(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF160` |
| `SecuredNonfarmOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF161` |
| `DepositoryInstitutions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1288` |
| `FinanceAgricultural(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1590` |
| `CommercialAndIndustrial(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1766` |
| `CreditCards(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB538` |
| `RevolvingCredit(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB539` |
| `AutomobileLoans(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONK137` |
| `ConsumerLoans(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONK207` |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2107` |
| `NonDepository(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ454` |
| `NonDepositoryOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ464` |
| `UnearnedIncome(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2123` |

### `CallReport_051.LoansAndLeases.ExcludingClosedEnd`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA570` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA571` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA572` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA573` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA574` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA575` |

### `CallReport_051.LoansAndLeases.ClosedEndFirstLiens`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON5367` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA564` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA565` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA566` |
| `FiveYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA567` |
| `FifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA568` |
| `OverFifteenYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA569` |

### `CallReport_051.LoansAndLeases.SecuredRealEstate`

Nested schedules: `SFR`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ConstructionSFR(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF158` |
| `ConstructionOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF159` |
| `Farmland(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1420` |

### `CallReport_051.LoansAndLeases.SecuredRealEstate.SFR`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `OpenEndRevolving(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON1797` |

### `CallReport_051.DepositLiabilities`

Nested schedules: `TransactionDeposits`, `NonTransactionDeposits`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2200` |
| `DomesticDeposits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `Individuals(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `USGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `CommercialBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `ForeignBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `ForeignGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_051.DepositLiabilities.TransactionDeposits`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Individuals(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB549` |
| `USGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2202` |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2203` |
| `CommercialBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB551` |
| `ForeignBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2213` |
| `ForeignGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2216` |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2215` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2215` |

### `CallReport_051.DepositLiabilities.NonTransactionDeposits`

Nested schedules: `TimeDeposits`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Individuals(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB550` |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCON2385` |
| `USGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2520` |
| `StatesAndPolitical(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2530` |
| `CommercialBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB552` |
| `ForeignBanks(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2236` |
| `ForeignGovt(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2377` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2385` |
| `SavingsMMDA(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON6810` |
| `SavingsOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON0352` |
| `SavingsTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | Uses other methods or a supplied header |

### `CallReport_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits`

Nested schedules: `LessThan250k`, `MoreThan250k`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `LessThan100k(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON6648` |
| `MoreThan100kLessThan250k(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ473`, `RCON6648` |

### `CallReport_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.LessThan250k`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONJ473` |
| `EffectiveThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA579` |
| `EffectiveTwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA580` |
| `EffectiveThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA581` |
| `EffectiveOverThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONA582` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ473` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK07` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK08` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK09` |
| `OverThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK10` |

### `CallReport_051.DepositLiabilities.NonTransactionDeposits.TimeDeposits.MoreThan250k`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ReportedTotal(name=False, *args, date='P0', **kwargs)` | No additional selector | Ignored | `RCONJ474` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONJ474` |
| `ThreeMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK12` |
| `TwelveMonths(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK13` |
| `ThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK14` |
| `OverThreeYears(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONHK15` |

### `CallReport_051.OtherLiabilities`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `InterestAccrued(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON3645` |
| `ExpensesAccruedOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON3646` |
| `DTLsNet(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON3049` |
| `CreditLosses(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONB557` |
| `AllOtherLiabilities(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2938` |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON2930` |

### `CallReport_051.DerivativesOffBalanceSheet`

Nested schedules: `CreditDerivatives`, `OtherDerivatives`.

### `CallReport_051.DerivativesOffBalanceSheet.CreditDerivatives`

Nested schedules: `SoldProtection`, `PurchasedProtection`.

### `CallReport_051.DerivativesOffBalanceSheet.CreditDerivatives.SoldProtection`

Nested schedules: `Notional`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CDS(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC968` |
| `TotalReturnSwaps(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC970` |
| `CreditOptions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC972` |
| `OtherCreditDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC974` |
| `MarketRiskRule(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONG401` |

### `CallReport_051.DerivativesOffBalanceSheet.CreditDerivatives.SoldProtection.Notional`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TwelveMonths(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCONG406`, `RCONG409` |
| `FiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCONG407`, `RCONG410` |
| `OverFiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCONG408`, `RCONG411` |
| `InvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `SubInvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_051.DerivativesOffBalanceSheet.CreditDerivatives.PurchasedProtection`

Nested schedules: `Notional`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CDS(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC969` |
| `TotalReturnSwaps(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC971` |
| `CreditOptions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC973` |
| `OtherCreditDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONC975` |
| `MarketRiskRule(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONG402` |

### `CallReport_051.DerivativesOffBalanceSheet.CreditDerivatives.PurchasedProtection.Notional`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TwelveMonths(rating='IG', name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCONG412`, `RCONG415` |
| `FiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCONG413`, `RCONG416` |
| `OverFiveYears(rating, name=False, *args, date='P0', **kwargs)` | `rating`: `'IG'`, `'SubIG'` | Branch labels | `RCONG414`, `RCONG417` |
| `InvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `SubInvestmentGrade(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives`

Nested schedules: `HeldForTrading`, `NotHeldForTrading`, `Futures`, `Forwards`, `ETDOptions`, `OTCOptions`, `Swaps`.

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.HeldForTrading`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA126` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONA127` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8723` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8724` |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.NotHeldForTrading`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8725` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8726` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8727` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8728` |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.Futures`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8693` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8694` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8695` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8696` |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.Forwards`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8697` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8698` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8699` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8700` |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.ETDOptions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalWritten(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalPurchased(claim, name=False, *args, date='P0', **kwargs)` | `claim`: accepted but unused | Branch labels | Uses other methods or a supplied header |
| `InterestRates(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8701`, `RCON8705` |
| `ForeignExchange(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8702`, `RCON8706` |
| `EquityDerivatives(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8703`, `RCON8707` |
| `CommoditiesOther(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8704`, `RCON8708` |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.OTCOptions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalWritten(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `TotalPurchased(claim, name=False, *args, date='P0', **kwargs)` | `claim`: accepted but unused | Branch labels | Uses other methods or a supplied header |
| `InterestRates(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8709`, `RCON8713` |
| `ForeignExchange(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8710`, `RCON8714` |
| `EquityDerivatives(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8711`, `RCON8715` |
| `CommoditiesOther(claim, name=False, *args, date='P0', **kwargs)` | `claim`: `'written'`, `'purchased'` | Branch labels | `RCON8712`, `RCON8716` |

### `CallReport_051.DerivativesOffBalanceSheet.OtherDerivatives.Swaps`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |
| `InterestRates(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON3450` |
| `ForeignExchange(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON3826` |
| `EquityDerivatives(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8719` |
| `CommoditiesOther(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCON8720` |

### `CallReport_051.NonaccrualPastDue`

Nested schedules: `LoansAndLeaseFinancingReceivables`, `SecuredRealEstate`, `DepositoryInstitutions`, `Individuals`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `FinanceAgricultural(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON1594`, `RCON1597`, `RCON1583` |
| `CommercialAndIndustrial(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON1254`, `RCON1255`, `RCON1256` |
| `ForeignGovt(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | Uses other methods or a supplied header |
| `AllOtherLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON5459`, `RCON5460`, `RCON5461` |
| `LeaseFinancingReceivables(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF166`, `RCONF167`, `RCONF168` |

### `CallReport_051.NonaccrualPastDue.LoansAndLeaseFinancingReceivables`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON1406`, `RCON1407`, `RCON1403` |
| `GuaranteedByUSGovt(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONK036`, `RCONK037`, `RCONK038` |
| `LoansAndLeasesHeldForSale(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONC240`, `RCONC241`, `RCONC226` |

### `CallReport_051.NonaccrualPastDue.SecuredRealEstate`

Nested schedules: `SFR`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `ConstructionSFR(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF172`, `RCONF174`, `RCONF176` |
| `ConstructionOther(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF173`, `RCONF175`, `RCONF177` |
| `Farmland(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON3493`, `RCON3494`, `RCON3495` |
| `SecuredMultifamily(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON3499`, `RCON3500`, `RCON3501` |
| `SecuredNonfarmOwner(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF178`, `RCONF180`, `RCONF182` |
| `SecuredNonfarmOther(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONF179`, `RCONF181`, `RCONF183` |

### `CallReport_051.NonaccrualPastDue.SecuredRealEstate.SFR`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `OpenEndRevolving(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON5398`, `RCON5399`, `RCON5400` |
| `ClosedEndFirstLiens(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONC236`, `RCONC237`, `RCONC229` |
| `ClosedEndJuniorLiens(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONC238`, `RCONC239`, `RCONC230` |

### `CallReport_051.NonaccrualPastDue.DepositoryInstitutions`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `USBanksTotal(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONB834`, `RCONB835`, `RCONB836` |
| `ForeignBanks(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCON5380`, `RCON5381`, `RCON5382` |

### `CallReport_051.NonaccrualPastDue.Individuals`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `CreditCards(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONB575`, `RCONB576`, `RCONB577` |
| `AutomobileLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONK213`, `RCONK214`, `RCONK215` |
| `OtherLoans(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'past due 30 days'`, `'B'`, `'past due 90 days'`, `'C'`, `'nonaccrual'` | Branch labels | `RCONK216`, `RCONK217`, `RCONK218` |

### `CallReport_051.DepositInsurance`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Section3IDeposits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF236` |
| `TotalAllowableExclusions(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | `RCONF237` |
| `TotalForeignDeposits(name=False, *args, date='P0', **kwargs)` | No additional selector | Branch labels | Uses other methods or a supplied header |

### `CallReport_051.MeasuredAtFV`

Nested schedules: `TradingAssets`, `TradingLiabilities`.

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `AFSSecurities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONJA36`, `RCONG474`, `RCONG475`, `RCONG476`, `RCONG477` |
| `FederalFundsSold(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | Uses other methods or a supplied header |
| `LoansAndLeasesHeldForSale(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG483`, `RCONG484`, `RCONG485`, `RCONG486`, `RCONG487` |
| `LoansAndLeasesHeldForInvestment(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG488`, `RCONG489`, `RCONG490`, `RCONG491`, `RCONG492` |
| `AllOtherAssets(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG391`, `RCONG392`, `RCONG395`, `RCONG396`, `RCONG804` |
| `DepositLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONF252`, `RCONF686`, `RCONF694`, `RCONF253`, `RCONF254` |
| `FederalFundsPurchased(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | Uses other methods or a supplied header |
| `SubordinatedNotes(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | Uses other methods or a supplied header |
| `OtherLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG805`, `RCONG806`, `RCONG807`, `RCONG808`, `RCONG809` |
| `TotalLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG531`, `RCONG532`, `RCONG533`, `RCONG534`, `RCONG535` |
| `MSAs(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG536`, `RCONG537`, `RCONG538`, `RCONG539`, `RCONG540` |

### `CallReport_051.MeasuredAtFV.TradingAssets`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCON3543`, `RCONG497`, `RCONG493`, `RCONG498`, `RCONG494`, `RCONG499`, `RCONG495`, `RCONG500`, `RCONG496`, `RCONG501` |
| `Derivatives(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCON3543`, `RCONG493`, `RCONG494`, `RCONG495`, `RCONG496` |
| `OtherAssets(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG497`, `RCONG498`, `RCONG499`, `RCONG500`, `RCONG501` |

### `CallReport_051.MeasuredAtFV.TradingLiabilities`

| Method signature | Additional arguments | `name=True` | Source headers |
| --- | --- | --- | --- |
| `Total(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCON3547`, `RCONG516`, `RCONG512`, `RCONG517`, `RCONG513`, `RCONG518`, `RCONG514`, `RCONG519`, `RCONG515`, `RCONG520` |
| `Derivatives(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCON3547`, `RCONG512`, `RCONG513`, `RCONG514`, `RCONG515` |
| `OtherLiabilities(column, name=False, *args, date='P0', **kwargs)` | `column`: `'A'`, `'B'`, `'C'`, `'Level 1'`, `'D'`, `'Level 2'`, `'E'`, `'Level 3'` | Branch labels | `RCONG516`, `RCONG517`, `RCONG518`, `RCONG519`, `RCONG520` |
