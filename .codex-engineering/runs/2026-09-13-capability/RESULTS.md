# RWA endogenous parameter hierarchy — implemented milestone

Implemented rolling second-pass CIR calibration for mu, theta and sigma at every maturity, coupled ridge regularization, joint yield/parameter scenarios, and an estimation-noise benchmark. This extends the existing sigma-only experimental design. Full pathwise recursion and RWA valuation remain separate unfinished milestones.

## Executable result

- [Implementation](../../../src/RWA/parameter_hierarchy/workflow.py)
- [Mathematical specification and usage](../../../src/RWA/parameter_hierarchy/readme.md)
- [Pipeline configuration](../../../pipeline/rwa_hierarchy/config.yaml)
- [Refined real-data scenario summary](real-eight-tenor-refined/scenario_summary.csv)
- [Real-data parameter dynamics](real-eight-tenor-refined/parameter_dynamics.csv)
- [Noise benchmark and original run manifest](real-eight-tenor/manifest.json)

## What the implementation discovered

The second pass can learn fluctuations created by the first pass and its repairs. On the actual eight-tenor snapshot through 2025-03-10, the fitted volatility-of-volatility coefficient for 7, 10, 20 and 30 years was below every one of 16 constant-parameter benchmark realizations. This small model-conditional benchmark does not establish genuine stochastic volatility-of-volatility at those tenors. It also does not prove that such dynamics are absent.

The benchmark fixes the first-stage generating parameters and reruns both complete rolling estimators and the same regularization. Its tail fractions are sensitivity diagnostics, not calibrated p-values. All 16 replicates succeeded. Some repaired theta histories are identical across maturities because they share an anchor; their dependence cannot automatically be interpreted as market dependence.

| Tenor | Observed xi | Fixed-parameter benchmark median | Fraction of benchmark values at least as large |
|---|---:|---:|---:|
| 1 years | 0.005124 | 0.004364 | 0.0000 |
| 2 years | 0.006390 | 0.004834 | 0.0000 |
| 3 years | 0.005716 | 0.004908 | 0.0000 |
| 5 years | 0.004816 | 0.004859 | 0.5000 |
| 7 years | 0.004263 | 0.004800 | 1.0000 |
| 10 years | 0.003797 | 0.004806 | 1.0000 |
| 20 years | 0.003624 | 0.004416 | 1.0000 |
| 30 years | 0.003601 | 0.004315 | 1.0000 |

## Actual-data implementation evidence

- Used 2,792 aligned observations from 2014-06-27 through 2025-03-10, with a 2,520-observation first window and 252-observation second window.
- Generated 2,184 first-stage rows and 528 second-stage rows: 24 parameter processes across eight maturities over 22 second-stage dates.
- Flagged and regularized 1,462 weak first-stage fits and 181 weak second-stage fits. Every profile negative-log-likelihood cost stayed within 2.0; weak flags remain present after regularization.
- Generated 1,024 joint paths over 20 future observation steps, with X/mu/theta/sigma at eight maturities. Both the original one-increment run and refined four-increment run had zero boundary projections in this sample.
- The 32-dimensional correlation had minimum eigenvalue 0.05 after explicit 5% identity shrinkage. The largest correlation adjustment was 0.05.
- Refined and original first/second-stage CSVs are byte-identical, so the original noise benchmark applies to the same calibration used for the refined forecast. All eight original FRED hashes are unchanged.

## Independent controls

Eight paired synthetic experiments used identical rate shocks under fixed versus periodically varying known sigma, with fixed true mu and theta. These are stress controls, not parameter-recovery proofs for a CIR volatility SDE. Each experiment used 384 observations at two maturities and 64-observation windows at both stages.

| Generating parameters | Mean fitted volatility of mu | Mean fitted volatility of theta | Mean fitted volatility of sigma |
|---|---:|---:|---:|
| constant | 0.153264 | 13.538247 | 0.173424 |
| varying | 0.145880 | 13.207907 | 0.231757 |

Varying sigma increased its fitted second-pass diffusion in all eight pairs, by factors ranging from 1.13 to 1.53. The fixed-parameter controls still produced substantial apparent mu/theta volatility, demonstrating why direct higher-order fits need an estimation-noise assessment.

## Held-out comparison

Three historical origins (2024-12-16, 2025-01-13 and 2025-02-10), eight maturities each, 20-step horizons and 2,048 simulated paths per model. The stochastic-parameter hierarchy was compared with the same starting yield parameters held fixed. The current model uses a fixed second-level calibration, not pathwise recalibration.

| Forecast model | RMSE, percentage points | 90% interval coverage | Mean 90% interval score (lower is better) |
|---|---:|---:|---:|
| fixed parameters | 0.277103 | 100.0% | 1.085677 |
| stochastic parameters | 0.276832 | 100.0% | 1.087308 |

Accuracy was effectively the same in this small sample. The hierarchy had slightly wider/less efficient intervals by the interval score. There is no demonstrated forecasting superiority, and these 24 outcomes are dependent and insufficient for a coverage claim.

## Numerical checks

Independent tests verify the likelihood against a nonlinear optimizer; coupled repair budgets; unit transformations; all parameter branches and maturity positions; causality; joint conditional drift/covariance; the extra drift caused by using updated correlated volatility; singular correlation handling; zero-state behavior; and time refinement.

For a standalone CIR process with known finite-horizon moments, 20,000-path experiments gave:

| Internal increments per reported step | Simulated mean | Exact mean | Simulated variance | Exact variance |
|---|---:|---:|---:|---:|
| 1 | 3.617512 | 3.621145 | 0.031955 | 0.030842 |
| 4 | 3.621254 | 3.621145 | 0.030818 | 0.030842 |
| 16 | 3.621506 | 3.621145 | 0.030270 | 0.030842 |

Monte Carlo fluctuations remain; refinement is also checked deterministically against the known CIR drift solution. Four internal increments are the default. The simulator rejects mean-reversion speeds that exceed the internal step scale rather than silently applying a clearly unsuitable step.

A local benchmark on 24 actual 2,520-observation windows took 0.0074 seconds for the stable raw solver versus 0.5380 seconds for the existing optimizer (about 73 times faster). All existing optimizer fits converged; the new raw objective was no worse on any window. This is one small timing sample, excludes regularization/hierarchy cost, and uses slightly different boundary constraints.

## Evidence and resumption

- [Reproducible research validation script](validate_hierarchy.py)
- [Synthetic, held-out and refinement results](validation-results.json)
- [Full regression log](verified-suite.log)
- [Engineering journal](../../JOURNAL.md)

Next research must distinguish latent parameter dynamics from estimation/repair effects before interpreting the hierarchy as additional risk. Further work includes pathwise recalibration, robust boundary transition treatment, wider held-out validation, and exposure/cash-flow valuation for RWA. The existing NS/NSS scripts and the default Call Report/JSD pipeline were preserved.
