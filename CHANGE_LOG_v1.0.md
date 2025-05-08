## 🚧 Intragroup JSD (Bank-Level Differentiation) – Future Implementation

The current pipeline completes the full intergroup JSD computation across temporal windows and asset pairings as described in the paper. As of this release, the **intragroup JSD scoring** — (which measures bank-level idiosyncratic divergence relative to peer PMFs) — is **mathematically formulated** and structurally anticipated in the pipeline, but **not yet implemented in code**.

This final step involves:

- Pruning features with non-trivial intergroup JSD values,
- Computing per-bank ratio deviations from peer distributions (bins),
- Scoring these deviations using a Jensen–Shannon divergence framework adapted to individual banks.

The logic and filtration framework to support this are in place, and this component is scheduled for rollout in an upcoming version.
