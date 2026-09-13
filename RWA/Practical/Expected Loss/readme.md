# Expected-loss valuation: implementation status

This directory currently contains documentation only. There is no expected-loss
calculator here and no command that produces an exposure-level expected-loss or
RWA result. The previous reference to an unspecified “Step 13” did not identify
an executable stage in the current repository.

The existing [Practical CMT workflow](../Constant%20Maturity%20Treasury/readme.md)
prepares yield-shock, drift and coupon calculations. The separate
[endogenous parameter hierarchy](../../../src/RWA/models/parameter_hierarchy/readme.md) produces
rate/parameter scenarios. Neither output alone is a portfolio expected-loss or
regulatory capital calculation.

Before this stage can be implemented, its contract needs to specify the securities
or maturity-bucket exposures, cash flows and valuation date, scenario discounting
or repricing convention, scenario weights, horizon and the precise loss measure.
Credit expected loss, market-value loss, VaR and a capital/RWA mapping must not be
silently treated as the same calculation. The
[recursive-model PDF](../../../PDF/Recursive%20IRR%20Model.pdf) is the governing
RWA research objective; valuation remains an unfinished milestone.

For runnable current capabilities, use the [RWA source guide](../../../src/RWA/readme.md).
Read the [research checkpoint](../../../.codex-engineering/CURRENT_TASK.md) and
[journal](../../../.codex-engineering/JOURNAL.md) for completed work, evidence and
the next implementation task. No valuation output is claimed for this directory.
