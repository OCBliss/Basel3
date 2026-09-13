# Reconstructed inputs for parameter-process calibration

These files combine the original yield observations with repaired mu/theta and
the corresponding sigma curve. Reconstruction aligns by date; it does not fit a
second stochastic process or estimate xi.

## Rebuild

From `Basel3_repo`, with the root requirements installed:

```bash
python3 src/RWA/parameter_rebuild/rebuild.py
```

The [rebuild source](../../../../src/RWA/parameter_rebuild/rebuild.py) has fixed
repository-relative defaults and no CLI options. It requires all eight maturities
and reads:

- `RWA/Experimental/MLE YIELD/RAW/DGS<n>_with_parameters.csv` for dates, quoted
  yields and `yield_clean`.
- `RWA/Experimental/MLE YIELD/NSS/mu_curve_nss_repaired.csv` and
  `theta_curve_nss_repaired.csv` for repaired mu/theta.
- `RWA/Experimental/MLE YIELD/CURVE/sigma_curve.csv` for sigma.

Review the [NSS audits](../../MLE%20YIELD/NSS/readme.md) first. The rebuild requires
unique date keys in each table and each RAW input; missing files or required
columns are errors. It left-joins each parameter onto the original yield dates,
preserves the original row order, and prints missing-parameter counts. Missing
matches remain missing; the script does not fill them or reject all incomplete
rows automatically.

## Exact output contract

Current code writes **`DGS<n>_with_parameters.csv`** in this folder for maturities
1, 2, 3, 5, 7, 10, 20 and 30. The six columns are:

```text
observation_date,DGS<n>,yield_clean,theta,mu,sigma
```

No extra CSV index is written. The original RAW theta/mu/sigma columns are
replaced by the joined values. NS/NSS diagnostic columns are omitted, so keep
the repaired curve files as provenance. Existing same-named outputs are replaced.

The checked-in historical files instead include names such as
`DGS1_vol_with_parameters.csv` and `DGS2 vol_with_parameters.csv` (with a space).
Those are legacy artifacts, not the filenames produced by the current rebuild.
Running the current command does not delete or rename them. Select inputs by
known schema and provenance rather than assuming every CSV here is a fresh run.

## Continue to parameter dynamics

The active [endogenous hierarchy](../../../../src/RWA/parameter_hierarchy/readme.md)
fits processes to **mu, theta and sigma**, including volatility of each parameter.
Its CLI starts from FRED yields and produces its own consistent calibration run;
it does not automatically scan this folder. Its documented Python interface can
accept a long first-stage table assembled from existing parameter histories.
See the [MLE VOL guide](../readme.md) for the legacy experiment and active commands.
