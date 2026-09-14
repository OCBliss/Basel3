# Rebuild per-maturity parameter histories

[rebuild.py](rebuild.py) joins repaired mu and theta curves, together with the
unmodified sigma curve, back onto each maturity's original yield history. This
produces the six-column inputs used by the established second-pass volatility
experiments. It performs date-based reconstruction, not another calibration.

## Prepare and run

Install the [repository requirements](../../../../requirements.txt). Complete
[yield calibration](../../calibration/yields/readme.md),
[CURVE assembly](../../../../RWA/Experimental/MLE%20YIELD/CURVE/readme.md), and
[mu/theta repair](../../calibration/curves/readme.md) first. Review the repair audit fields
before carrying their values downstream. Run from the repository root:

```bash
python3 src/RWA/data/parameters/rebuild.py
```

There are no command-line settings or preview mode. Paths and the eight-tenor
`MATURITY_MAP` are constants in `rebuild.py`; root discovery uses
`src/Basel3_Global_Filepath.py`. The command creates `MLE VOL/RAW` if needed and
replaces its configured per-tenor output files.

## Required files

Paths in this table are relative to `RWA/Experimental/`.

| Input | Required columns |
| --- | --- |
| `MLE YIELD/RAW/DGS*_with_parameters.csv` | `observation_date`, the named `DGS*` market-yield column, and `yield_clean`. |
| `MLE YIELD/NSS/mu_curve_nss_repaired.csv` | `observation_date` and `mu1y`, `mu2y`, `mu3y`, `mu5y`, `mu7y`, `mu10y`, `mu20y`, `mu30y`. |
| `MLE YIELD/NSS/theta_curve_nss_repaired.csv` | The same date key and eight `theta*y` columns. |
| `MLE YIELD/CURVE/sigma_curve.csv` | The same date key and eight `sigma*y` columns. |

All eight DGS files for 1, 2, 3, 5, 7, 10, 20 and 30 years are processed.
Use parameter curves from the same input history and calibration settings as
the RAW files; the program does not verify provenance or statistical agreement.

## Join and output contract

For each DGS file, reconstruction discards its old parameter columns, retains
the three market-data columns, and performs three one-to-one left joins by
`observation_date`. It then restores the original RAW row order.

Each `MLE VOL/RAW/DGS*_with_parameters.csv` contains exactly:

```text
observation_date,DGS*,yield_clean,theta,mu,sigma
```

`DGS*` is the actual maturity name, such as `DGS10`. Dates are formatted as
`YYYY-MM-DD`; there is no extra CSV index. Missing curve matches and historical
warmup values remain missing. The console reports missing theta, mu and sigma
counts for each maturity; it does not fill them or reject the output merely
because matches are absent. Extra curve dates do not add RAW rows.

Missing files, missing required columns, unparseable dates and duplicate date
keys raise errors. The three curves are loaded before the maturity loop, but
an error in a later DGS file can leave earlier rebuilt files on disk. There is
no whole-run transaction. The rebuild does not check parameter positivity or
carry NS/NSS audit fields into its six-column exports, so preserve and review
the repaired source curves alongside the results.

## Next consumer

The [MLE VOL/RAW guide](../../../../RWA/Experimental/MLE%20VOL/RAW/readme.md)
describes the reconstructed files. The
[MLE VOL overview](../../../../RWA/Experimental/MLE%20VOL/readme.md) distinguishes
the historical sigma-only experiment from the active
[endogenous parameter hierarchy](../../models/parameter_hierarchy/readme.md). The active
hierarchy reads FRED inputs directly, calibrates mu/theta/sigma histories, and
also exports compatible first-stage RAW and CURVE tables; it does not require
this legacy reconstruction command as a preceding pipeline task. Its optional
ACT/365F/observed mode exports irregular genuine common dates with the same
RAW/CURVE columns. Date joins remain compatible, but this six-column reconstruction
does not carry timing settings or the model's interval audit. Preserve the
original hierarchy manifest and `transition_intervals.csv` and pass the same time
convention to any subsequent parameter fit; filenames alone do not encode it.

## Verification

Use the repository-local temporary-file setup in the
[test guide](../../../../tests/readme.md), then run:

```bash
python3 -B -m unittest discover -s tests -p test_rwa_calibration.py -v
python3 -B -m unittest discover -s tests -p test_rwa_hierarchy.py -v
```

The tests pass isolated calibration/repair outputs and the active hierarchy's
actual CSV exports through this rebuild consumer, checking dates, original row
order, warmup values and the six-column contract. Data compatibility does not
establish that repaired estimates measure latent parameter risk.
