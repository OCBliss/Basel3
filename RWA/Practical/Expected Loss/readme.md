# Expected-loss valuation: implementation status

This directory currently contains documentation only. There is no expected-loss
calculator here and no command that produces an exposure-level expected-loss or
RWA result.

The existing [Practical CMT workflow](../Constant%20Maturity%20Treasury/readme.md)
describes historical yield preparation, selected-change summaries and parameter
estimation. The separate
[endogenous parameter hierarchy](../../../src/RWA/models/parameter_hierarchy/readme.md) produces
a recursive rate/sigma/xi trajectory. Neither output alone is a portfolio expected-loss or
regulatory capital calculation.

Before this stage can be implemented, its contract needs to specify the securities
or maturity-bucket exposures, cash flows and valuation date, scenario discounting
or repricing convention, scenario weights, horizon and the precise loss measure.
Credit expected loss, market-value loss, VaR and a capital/RWA mapping must not be
silently treated as the same calculation. The
[recursive-model PDF](../../../PDF/Recursive%20IRR%20Model.pdf) is the governing
RWA research objective; valuation remains an unfinished milestone.

For runnable current capabilities, use the [RWA source guide](../../../src/RWA/readme.md).
The [model output guide](../../Experimental/HIERARCHY/readme.md) describes the
generated trajectories and provenance that a future valuation stage would consume.
No valuation output is produced by this directory.
