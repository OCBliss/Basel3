# Distribution comparisons

These stages compare bank-ratio distributions for Failures, Mergers and Survivors
at the selected observation horizons. Run from `Basel3_repo` after the
[peer-group stages](../peer%20groups/readme.md) have produced the selected panels.
Install the root `requirements.txt` first.

```bash
python3 src/jsd/binning/Material_events_JSD_binning_basel3.py \
  --horizons 1 2 3 4 --bins1 20 30 50 100 --bins2 5 --bins3 1 \
  --material-dir "Material Events"
python3 src/jsd/pmf/Material_events_JSD_probabilities_basel3.py \
  --horizons 1 2 3 4 --bins 20 30 50 100 --material-dir "Material Events"
python3 src/jsd/calculation/Material_events_JSD_basel3.py \
  --horizons 1 2 3 4 --bins 20 30 50 100 --material-dir "Material Events"
```

Keep horizons and bin selections consistent across the stages. The
[pipeline configuration](../../pipeline/readme.md) supplies these once for the
whole workflow. Individual commands write the selected outputs and can replace
previous results at those locations.

| Stage | Contract and details |
| --- | --- |
| [Binning](binning/readme.md) | Cohort/horizon panels to counts using common bin edges |
| [PMFs](pmf/readme.md) | Histogram columns to probability masses |
| [Calculation](calculation/readme.md) | Pairwise aligned PMFs to distribution distances |
| [Filtering](../measures/intragroup/readme.md) | Selected distance columns above a threshold |

Counts and PMFs live under each cohort's `JS Divergence` folder. Pairwise results
live under `Material Events/JSD/BASEL III T+<horizon>/`. The implemented statistic
is the **square root** of Jensen–Shannon divergence using natural logarithms;
see the calculation guide for the exact zero-mass and alignment behavior.
Distributional separation does not alone establish causality or risk ordering.
