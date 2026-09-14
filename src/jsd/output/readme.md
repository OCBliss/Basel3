# JSD outputs and proposed matrix construction

This directory contains documentation only. There is no matrix-construction
script here and no matrix stage in the current pipeline. The matrix contract below describes a proposed extension.

## Implemented outputs

The [calculation stage](../calculation/readme.md) writes one-row comparisons under
`Material Events/JSD/BASEL III T+<horizon>/` for the selected horizons and central
bin counts. Each bin specification has Survivors–Failures, Survivors–Mergers and
Mergers–Failures files, such as `JSD_survivors_vs_failures_100.csv`. Values are
square-root Jensen–Shannon divergence using natural logarithms. The three stages
use common histogram edges within a specification, then normalize each ratio
column independently. See [the JSD workflow](../readme.md) for prerequisites and
exact commands from the repository root.

The next implemented consumer is [the column filter](../../measures/intragroup/readme.md),
which retains selected result columns meeting its threshold. It does not assemble
matrices or test predictive significance.

## Proposed matrix contract

A future matrix stage could collect a given cohort comparison, central bin count
and variable into rows such as `q0`, `q0q1`, `q0q2`, `q0q3` and columns for horizons
T+1 through T+4. It must preserve the bin specification and cohort identity,
validate missing/duplicate source results, and retain provenance rather than
silently mixing selected and stale outputs. No command or output location is
implemented for that stage. Such a matrix would organize descriptive distances;
it would not by itself establish causality, risk ordering or held-out accuracy.
