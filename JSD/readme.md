# Jensen-Shannon Divergence (JSD)

The Jensen-Shannon Divergence (JSD) module measures the statistical separation between bank populations over successive forecast horizons.

The Jensen–Shannon Divergence (JSD) module measures the statistical separation between bank populations over successive forecast horizons.

Rather than fitting a theoretical probability distribution or comparing raw financial ratios through moment-based statistics, the pipeline bins the observed values for each financial variable and converts the resulting frequency counts into empirical probability mass functions (PMFs).

The Jensen–Shannon Divergence is then calculated between the empirical PMFs of two class-conditional banking cohorts at a time.

The resulting values quantify how distinguishable the observed distributions are and how that separability changes as a failure, merger, or other structural event approaches.

This approach is useful because it does not rely on moment-based descriptions of the data. Differences between populations are not reduced to changes in the mean, variance, skewness, or another limited set of summary statistics. Instead, the comparison incorporates the full discrete distribution represented by the PMF, including differences in concentration, dispersion, asymmetry, multimodality, and tail allocation.

## Purpose

This module evaluates whether financial variables exhibit increasing statistical separation prior to structural banking events.

The analysis is performed independently for each forecast horizon:

* T+1
* T+2
* T+3
* T+4

and for each comparison:

* `Survivors_vs_Failures`
* `Survivors_vs_Mergers`
* `Mergers_vs_Failures`

Because the Jensen–Shannon Divergence is symmetric and bounded, it provides an interpretable measure of distributional divergence without assuming any particular probability model.

## Pipeline

```
Raw Financial Variables
           │
           ▼
Histogram Binning
           │
           ▼
Empirical Probability Distributions
           │
           ▼
Jensen–Shannon Divergence
```

### Design Reason

Each stage is intentionally separated to permit experimentation with alternative histogram resolutions while keeping the divergence computation unchanged.

## Histogram Binning

Continuous financial variables are transformed into empirical probability distributions.

Each variable is independently discretized into histogram bins.

Typical resolutions include

20 bins
30 bins
50 bins
100 bins

The current implementation also supports a higher-resolution asymmetric binning scheme that allocates substantially more resolution near the center of the distribution while preserving tail behavior.

### Design Reason

Ratios with veritable distributional separaation should persist across binning resolutions to remove noise.

## Probability Mass Function Generation

Histogram counts are normalized into empirical probability mass functions for each temporal horizon to a particular material event. THese empirical distributions serve as the inputs to the divergence calculation.

### Design Reason

## JSD Calculation

For every financial variable, the pmf of two bank cohorts are compared using the previous flagged call reports with binary labels.

The resultive value is scaled between a range and higher values indicate greater statistical separability between the populations

### Design Reason

The Kullback-Leibler Divergence is not symmetric and essentially requires a control group forcing the designation of either `failures` or `survivors` or `mergers` as the reference class. In light of this, the JSD solves this problem being strictly symmetric.

Other divergence techniques have hyperparameters creating greater degrees of freedom, leading to greater input assumptions.

Unlike moment comparisons, Jensen-Shannon Divergence measures differences between entire probability distributions. This allows the analysis to detect changes in:
* location
* dispersion
* multimodality
* tail behavior

without assuming normality.

As structural banking events approach, variables exhibiting increasing divergence indicate growing statistical distinction between affected institutions and surviving peers.

##

## Basel III Pipeline Stub Data for JSD

# Folders

- `BASEL III T+1`
- `BASEL III T+2`
- `BASEL III T+3`
- `BASEL III T+4`
- `Matrix Outputs`

# Code

`Basel_Matrix_v2.py` would run and accept <`BASEL III T+1`>,...,<`BASEL III T+4`> subdirectories as inputs and output the results in <`Matrix Outputs`>.

The files are named according to their JSD_<peer group 1>_vs_<peer group 2>_<bin>_<variable>.csv
