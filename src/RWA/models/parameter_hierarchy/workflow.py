#!/usr/bin/env python3
"""Run the endogenous mu/theta/sigma hierarchy on the repository's FRED inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

if __package__:
    from .core import (integer, positive_number, stabilize_panel,
                               innovation_correlation, step_hierarchy)
    from .recursive import simulate_recursive
else:
    from core import (integer, positive_number, stabilize_panel,
                               innovation_correlation, step_hierarchy)
    from recursive import simulate_recursive


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.RWA.data.yields.acquire import verify_snapshot

TENORS = (1, 2, 3, 5, 7, 10, 20, 30)
PARAMETERS = ("mu", "theta", "sigma")


def repository_path(value):
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        raise ValueError("project paths must remain inside Basel3_repo: " + str(path))
    return path


def read_yield_panel(directory, maturities=TENORS, as_of=None):
    """Inner-join quote dates and causally fill quotes within each original file.

    Keep FRED percentage units and one fixed dt per input-row transition, matching
    the existing calibrator. Missing quotes are counted, not silently erased.
    """
    directory = repository_path(directory)
    if not maturities or len(set(maturities)) != len(maturities):
        raise ValueError("supply distinct positive maturities")
    series, sources = [], []
    cutoff = pd.Timestamp(as_of) if as_of is not None else None
    if cutoff is not None and pd.isna(cutoff):
        raise ValueError("as_of must be a valid date")
    for tenor in maturities:
        integer(tenor, "maturity", 1)
        p = repository_path(directory / ("DGS%d.csv" % tenor))
        frame = pd.read_csv(p)
        column = "DGS%d" % tenor
        if not {"observation_date", column}.issubset(frame.columns):
            raise ValueError(str(p) + " lacks date/yield columns")
        text_dates = frame.observation_date.astype(str)
        date_format = "%m/%d/%y" if text_dates.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}").all() else None
        dates = pd.to_datetime(frame.observation_date, errors="raise", format=date_format)
        if dates.isna().any() or dates.duplicated().any():
            raise ValueError(str(p) + " contains missing/duplicate dates")
        values = pd.Series(pd.to_numeric(frame[column], errors="coerce").to_numpy(),
                           index=dates, name=tenor).sort_index()
        if cutoff is not None:
            values = values.loc[values.index <= cutoff]
        missing = int(values.isna().sum())
        values = values.ffill()
        if values.empty or not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(str(p) + " requires finite positive yields with a known initial value")
        series.append(values)
        sources.append({"path": str(p.relative_to(ROOT)),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "rows_before_alignment": len(values), "filled_quotes": missing})
    panel = pd.concat(series, axis=1, join="inner").sort_index()
    panel.index.name = "observation_date"
    if panel.empty:
        raise ValueError("maturity files have no common dates")
    return panel, sources


def _validate_panel(panel, window):
    integer(window, "window", 4)
    if not isinstance(panel.index, pd.DatetimeIndex) or panel.index.hasnans or panel.index.has_duplicates:
        raise ValueError("panel needs unique valid observation dates")
    if panel.columns.has_duplicates or len(panel.columns) < 1:
        raise ValueError("panel needs unique maturity columns")
    if len(panel) < window:
        raise ValueError("insufficient history for the requested rolling window")
    if not np.isfinite(panel.to_numpy(dtype=float)).all() or (panel.to_numpy(dtype=float) < 0).any():
        raise ValueError("panel must contain finite nonnegative observations")
    return panel.sort_index()


def calibrate_panel(panel, window, dt=1 / 252, nll_budget=2., fallback_theta=.25):
    """Fit and jointly stabilize every date/maturity without future information."""
    panel = _validate_panel(panel, window)
    history = panel.to_numpy(dtype=float)
    prior = None
    records = []
    for end in range(window - 1, len(panel)):
        fits, audit = stabilize_panel(history[end - window + 1:end + 1], panel.columns,
                                      dt, nll_budget, fallback_theta, prior)
        for j, (fit, diagnostics) in enumerate(zip(fits, audit)):
            records.append(dict(observation_date=panel.index[end], maturity=panel.columns[j],
                                theta=fit.theta, mu=fit.mu, sigma=fit.sigma, a=fit.a,
                                **diagnostics))
        # An inadmissible fit must not seed the next date's anchors.
        prior = np.array([f.theta for f in fits])
        if not np.isfinite(prior).all() or (prior <= 0).any():
            prior = None
    return pd.DataFrame.from_records(records)


def parameter_panels(first_stage):
    required = {"observation_date", "maturity", *PARAMETERS}
    if not required.issubset(first_stage.columns):
        raise ValueError("first-stage table lacks required parameter columns")
    first = first_stage.copy()
    first["observation_date"] = pd.to_datetime(first.observation_date, errors="raise")
    if first.observation_date.isna().any() or first.duplicated(["observation_date", "maturity"]).any():
        raise ValueError("first-stage dates/maturities must be present and unique")
    return {p: first.pivot(index="observation_date", columns="maturity", values=p).sort_index()
            for p in PARAMETERS}


def calibrate_parameters(first_stage, window, dt=1 / 252, nll_budget=2., fallback_theta=.25):
    """Generalize the legacy sigma-only second pass to all three parameter states.

    Never fill unavailable or failed first-stage estimates. Gaps raise an error
    with the affected parameter; warmup should be removed before this interface.
    """
    branches = []
    for parameter, panel in parameter_panels(first_stage).items():
        try:
            fitted = calibrate_panel(panel, window, dt, nll_budget, fallback_theta)
        except ValueError as error:
            raise ValueError("cannot fit " + parameter + " history: " + str(error)) from error
        fitted.insert(2, "parameter", parameter)
        branches.append(fitted)
    return pd.concat(branches, ignore_index=True).sort_values(
        ["observation_date", "maturity", "parameter"]).reset_index(drop=True)


def forecast_history(yields, first_stage, window):
    """Assemble one causal trailing state window shared by both forecast modes."""
    integer(window, "window", 5)
    panels = parameter_panels(first_stage)
    dates = panels["mu"].index
    tenors = panels["mu"].columns.to_numpy()
    if len(dates) < window:
        raise ValueError("insufficient parameter history for joint dependence")
    history = np.stack([yields.reindex(index=dates[-window:], columns=tenors).to_numpy()] +
                       [panels[p].iloc[-window:].to_numpy() for p in PARAMETERS], axis=1)
    if not np.isfinite(history).all() or (history < 0).any():
        raise ValueError("forecast history contains missing or inadmissible states")
    return history


def forecast_inputs(yields, first_stage, second_stage, window, dt, shrinkage=.05):
    """Use only the origin's trailing observed/estimated history to fit dependence."""
    integer(window, "window", 5)
    panels = parameter_panels(first_stage)
    dates = panels["mu"].index
    if len(dates) < window:
        raise ValueError("insufficient parameter history for joint dependence")
    origin = dates[-1]
    tenors = panels["mu"].columns.to_numpy()
    selected = second_stage.loc[second_stage.observation_date == origin]
    coeff = np.empty((3, 3, len(tenors)))
    for k, p in enumerate(PARAMETERS):
        rows = selected.loc[selected.parameter == p].set_index("maturity").reindex(tenors)
        if len(rows) != len(tenors) or not {"theta", "mu", "sigma"}.issubset(rows):
            raise ValueError("missing second-stage origin parameters")
        coeff[k] = rows[["theta", "mu", "sigma"]].to_numpy().T
    history = forecast_history(yields, first_stage, window)
    if not np.isfinite(history).all() or not np.isfinite(coeff).all() or (history < 0).any() or (coeff < 0).any():
        raise ValueError("forecast inputs contain missing or inadmissible states/parameters")
    earlier = history[:-1]
    drift = np.empty_like(earlier)
    diffusion = np.empty_like(earlier)
    drift[:, 0] = earlier[:, 2] * (earlier[:, 1] - earlier[:, 0])
    diffusion[:, 0] = earlier[:, 3] * np.sqrt(earlier[:, 0])
    drift[:, 1:] = coeff[:, 0] * (coeff[:, 1] - earlier[:, 1:])
    diffusion[:, 1:] = coeff[:, 2] * np.sqrt(earlier[:, 1:])
    innovations = np.diff(history, axis=0) - drift * dt
    residuals = np.divide(innovations, diffusion * np.sqrt(dt),
                          out=np.zeros_like(innovations), where=diffusion > 0)
    if np.any((diffusion == 0) & (np.abs(innovations) > 1e-10)):
        raise ValueError("nonzero innovations under a zero diffusion coefficient")
    corr, factor, diagnostics = innovation_correlation(residuals.reshape(len(residuals), -1), shrinkage)
    return history[-1], coeff, corr, factor, diagnostics


def simulate(initial, coefficients, factor, paths=256, steps=20, dt=1 / 252, seed=1234,
             substeps=4):
    """Frozen second-level calibration baseline with stochastic X,mu,theta,sigma.

    This finite hierarchy evolves all four states; it does not yet recalibrate
    its nine second-level coefficients on each simulated path. Output records
    boundary projections, so nonnegativity is not mistaken for discretization QA.
    """
    integer(paths, "paths", 1)
    integer(steps, "steps", 1)
    integer(seed, "seed", 0)
    integer(substeps, "substeps", 1)
    positive_number(dt, "dt")
    initial = np.asarray(initial, dtype=float)
    coefficients = np.asarray(coefficients, dtype=float)
    if initial.ndim != 2 or initial.shape[0] != 4 or initial.shape[1] < 1:
        raise ValueError("initial state must have shape (4,maturity)")
    if paths * (steps + 1) * initial.size > 20_000_000:
        raise ValueError("requested paths exceed the 20-million-state memory bound")
    state = np.broadcast_to(initial, (paths,) + initial.shape).copy()
    # Validate shapes/values before allocating the potentially large path array.
    step_hierarchy(state, coefficients, np.zeros_like(state), factor, dt)
    delta = dt / substeps
    if np.max(coefficients[:, 0]) * delta > 1:
        raise ValueError("parameter mean reversion exceeds the step scale; increase substeps")
    result = np.empty((paths, steps + 1) + initial.shape)
    result[:, 0] = state
    projections = np.zeros(initial.shape, dtype=np.int64)
    rng = np.random.default_rng(seed)
    for t in range(steps):
        for _ in range(substeps):
            if np.max(state[:, 2]) * delta > 1:
                raise ValueError("yield mean reversion exceeds the step scale; increase substeps")
            state, hits = step_hierarchy(state, coefficients, rng.standard_normal(state.shape), factor, delta)
            projections += hits.sum(axis=0)
        result[:, t + 1] = state
    return result, projections


def parameter_noise_diagnostic(yields, first, second, yield_window, parameter_window,
                               replicates=16, seed=1234, dt=1 / 252,
                               nll_budget=2., fallback_theta=.25, shrinkage=.05):
    """Model-conditional constant-parameter bootstrap of the whole estimator.

    Simulated yields have fixed first-stage parameters, but both rolling fits
    and ridge regularization are rerun. Thus nonzero second-pass volatility
    under this null is an estimator/repair artifact. Tail fractions here are
    sensitivity diagnostics, not calibrated hypothesis-test p-values.
    """
    integer(replicates, "replicates", 2)
    integer(seed, "seed", 0)
    yields = _validate_panel(yields, yield_window)
    tenors = yields.columns
    latest = first.loc[first.observation_date == yields.index[-1]].set_index("maturity").reindex(tenors)
    base = latest[["theta", "mu", "sigma"]].to_numpy().T
    if not np.isfinite(base).all() or (base < 0).any():
        raise ValueError("bootstrap requires usable origin parameters")
    raw = yields.to_numpy()
    residuals = np.diff(raw, axis=0) - base[0] * (base[1] - raw[:-1]) * dt
    denominator = base[2] * np.sqrt(raw[:-1] * dt)
    residuals = np.divide(residuals, denominator, out=np.zeros_like(residuals), where=denominator > 0)
    _, factor, _ = innovation_correlation(residuals, shrinkage)
    origin_second = second.loc[second.observation_date == yields.index[-1]].set_index(["parameter", "maturity"])
    observed = np.array([[origin_second.loc[(p, m), "sigma"] for m in tenors] for p in PARAMETERS])
    rng = np.random.default_rng(seed)
    null_estimates, failures = [], []
    for replicate in range(replicates):
        draws = rng.normal(size=(len(raw)-1, len(tenors))) @ factor.T
        synthetic = np.empty_like(raw)
        synthetic[0] = raw[0]
        hit = False
        for t in range(len(raw)-1):
            x = synthetic[t]
            future = x + base[0]*(base[1]-x)*dt + base[2]*np.sqrt(x*dt)*draws[t]
            if not np.isfinite(future).all() or (future <= 0).any():
                hit = True
                break
            synthetic[t+1] = future
        if hit:
            failures.append({"replicate": replicate, "reason": "nonpositive/nonfinite bootstrap yield"})
            continue
        try:
            panel = pd.DataFrame(synthetic, index=yields.index, columns=tenors)
            f = calibrate_panel(panel, yield_window, dt, nll_budget, fallback_theta)
            # Replay both complete rolling passes, including the previous-date
            # anchors. Fitting only the final window would change the estimator.
            b = calibrate_parameters(f, parameter_window, dt, nll_budget, fallback_theta)
            b = b.loc[b.observation_date == yields.index[-1]].set_index(["parameter", "maturity"])
            null_estimates.append([[b.loc[(p,m),"sigma"] for m in tenors] for p in PARAMETERS])
        except ValueError as error:
            failures.append({"replicate": replicate, "reason": str(error)})
    report = {"requested_replicates": replicates, "successful_replicates": len(null_estimates),
              "seed": seed, "failures": failures,
              "interpretation": "Conditional estimation-noise benchmark; tail fractions are not p-values.",
              "comparable": len(null_estimates) == replicates, "rows": []}
    if null_estimates:
        null = np.array(null_estimates)
        for k,p in enumerate(PARAMETERS):
            for j,m in enumerate(tenors):
                distribution = null[:,k,j]
                report["rows"].append({"parameter": p, "maturity": int(m),
                                       "observed_diffusion": float(observed[k,j]),
                                       "null_median": float(np.median(distribution)),
                                       "null_q95": float(np.quantile(distribution,.95)),
                                       "null_exceedance_fraction": float(np.mean(distribution >= observed[k,j]))})
    return report


def write_outputs(output, yields, first, second, manifest, forecast=None):
    """Write a new output directory; existing products are never overwritten."""
    output = repository_path(output)
    if output.exists():
        raise ValueError("output already exists; choose a new run directory")
    output.mkdir(parents=True)
    first.to_csv(output / "yield_parameters.csv", index=False)
    second.to_csv(output / "parameter_dynamics.csv", index=False)
    (output / "RAW").mkdir()
    (output / "CURVE").mkdir()
    for tenor in yields.columns:
        rows = first.loc[first.maturity == tenor].set_index("observation_date")
        original = pd.DataFrame({"DGS%d" % tenor: yields[tenor], "yield_clean": yields[tenor]})
        original = original.join(rows[["theta", "mu", "sigma"]]).reset_index()
        original.index = np.arange(1, len(original) + 1)
        original.to_csv(output / "RAW" / ("DGS%d_with_parameters.csv" % tenor))
    for p, panel in parameter_panels(first).items():
        panel.columns = [p + str(t) + "y" for t in panel.columns]
        panel.to_csv(output / "CURVE" / (p + "_curve.csv"))
    if forecast is not None:
        samples, projections, corr = forecast
        np.savez_compressed(output / "scenarios.npz", states=samples,
                            maturities=yields.columns.to_numpy(),
                            state_names=np.array(["X", *PARAMETERS]),
                            correlation=corr, boundary_projections=projections)
        records = []
        for k, name in enumerate(["X", *PARAMETERS]):
            for j, tenor in enumerate(yields.columns):
                for t in range(samples.shape[1]):
                    v = samples[:, t, k, j]
                    records.append(dict(step=t, maturity=tenor, state=name,
                                        mean=float(v.mean()), q05=float(np.quantile(v, .05)),
                                        q50=float(np.quantile(v, .5)), q95=float(np.quantile(v, .95))))
        pd.DataFrame(records).to_csv(output / "scenario_summary.csv", index=False)
    # Written last; absence of manifest denotes an incomplete output directory.
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="RWA/FRED")
    parser.add_argument("--input-manifest", help="verify an acquired snapshot before reading its input series")
    parser.add_argument("--output", required=True, help="new directory inside Basel3_repo")
    parser.add_argument("--maturities", type=int, nargs="+", default=list(TENORS))
    parser.add_argument("--as-of")
    parser.add_argument("--yield-window", type=int, default=2520)
    parser.add_argument("--parameter-window", type=int, default=252)
    parser.add_argument("--recent-rows", type=int, default=0,
                        help="explicit history truncation; zero uses all common rows")
    parser.add_argument("--dt", type=float, default=1 / 252)
    parser.add_argument("--nll-budget", type=float, default=2.)
    parser.add_argument("--fallback-theta", type=float, default=.25)
    parser.add_argument("--shrinkage", type=float, default=.05)
    parser.add_argument("--paths", type=int, default=256)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--substeps", type=int, default=4,
                        help="Euler increments per reported time step; check refinement sensitivity")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--noise-replicates", type=int, default=0,
                        help="zero disables the constant-parameter estimation-noise benchmark")
    parser.add_argument("--forecast-mode", choices=("frozen", "recursive"), default="frozen")
    parser.add_argument("--recalibrate-every", type=int, default=1,
                        help="recursive mode: reported-step interval for pathwise refits; zero is the frozen benchmark")
    args = parser.parse_args(argv)
    try:
        output = repository_path(args.output)
        if output.exists():
            raise ValueError("output already exists; choose a new run directory")
        integer(args.recent_rows, "recent_rows", 0)
        integer(args.noise_replicates, "noise_replicates", 0)
        if args.noise_replicates == 1:
            raise ValueError("noise_replicates must be zero or at least two")
        integer(args.parameter_window, "parameter_window", 5)
        integer(args.recalibrate_every, "recalibrate_every", 0)
        positive_number(args.dt, "dt")
        acquisition = (verify_snapshot(args.input_manifest, args.input, args.maturities)
                       if args.input_manifest else None)
        yields, sources = read_yield_panel(args.input, args.maturities, args.as_of)
        # Sort maturities consistently with parameter-panel pivot ordering.
        yields = yields.reindex(sorted(yields.columns), axis=1)
        if args.recent_rows:
            yields = yields.iloc[-args.recent_rows:]
        first = calibrate_panel(yields, args.yield_window, args.dt,
                                args.nll_budget, args.fallback_theta)
        second = calibrate_parameters(first, args.parameter_window, args.dt,
                                      args.nll_budget, args.fallback_theta)
        initial, coefficients, corr, factor, diagnostics = forecast_inputs(
            yields, first, second, args.parameter_window, args.dt, args.shrinkage)
        recursive_diagnostics = None
        if args.forecast_mode == "recursive":
            history = forecast_history(yields, first, args.parameter_window)
            samples, projections, recursive_diagnostics = simulate_recursive(
                history, coefficients, factor, yields.columns.to_numpy(), args.paths,
                args.steps, args.dt, args.seed, args.substeps, args.recalibrate_every,
                args.nll_budget, args.fallback_theta, args.shrinkage)
        else:
            samples, projections = simulate(initial, coefficients, factor, args.paths,
                                            args.steps, args.dt, args.seed, args.substeps)
        noise = None
        if args.noise_replicates:
            noise = parameter_noise_diagnostic(yields, first, second, args.yield_window,
                args.parameter_window, args.noise_replicates, args.seed, args.dt,
                args.nll_budget, args.fallback_theta, args.shrinkage)
        manifest = {"schema_version": 1, "status": "complete", "settings": vars(args),
                    "source_files": sources, "units": "FRED percentage points",
                    "yield_acquisition": acquisition,
                    "history_start": str(yields.index[0].date()),
                    "forecast_origin": str(yields.index[-1].date()),
                    "first_stage_rows": len(first), "second_stage_rows": len(second),
                    "first_stage_weak": int(first.weak.sum()),
                    "first_stage_regularized": int(first.regularized.sum()),
                    "second_stage_weak": int(second.weak.sum()),
                    "second_stage_regularized": int(second.regularized.sum()),
                    "max_first_stage_nll_cost": float(first.nll_cost.max()),
                    "max_second_stage_nll_cost": float(second.nll_cost.max()),
                    "joint_dependence": diagnostics,
                    "estimation_noise": noise,
                    "boundary_projections": projections.tolist(),
                    "forecast_mode": ("pathwise recursive parameter calibration and dependence"
                                      if args.forecast_mode == "recursive" else
                                      "stochastic parameters; frozen second-level calibration"),
                    "recursive_calibration": recursive_diagnostics,
                    "limitations": ["Estimated parameter dynamics include estimation noise.",
                                    "Regularization does not identify weak parameters.",
                                    "No exposure valuation or RWA capital mapping.",
                                    "Finite parameter hierarchy; no additional independently simulated xi level."]}
        write_outputs(output, yields, first, second, manifest, (samples, projections, corr))
        print(json.dumps({"output": str(output), "first_stage_rows": len(first),
                          "second_stage_rows": len(second),
                          "joint_dimensions": len(corr),
                          "boundary_projections": int(projections.sum())}))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, "Hierarchy failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
