#!/usr/bin/env python3
"""Run the endogenous mu/theta/sigma hierarchy on the repository's FRED inputs."""

import argparse
import csv
import io
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sys

import numpy as np
import pandas as pd

if __package__:
    from .core import integer, positive_number, stabilize_panel, transition_steps
    from .recursive import simulate_walk, walk_workload
    from .covariance_archive import CovarianceArchive
else:
    from core import integer, positive_number, stabilize_panel, transition_steps
    from recursive import simulate_walk, walk_workload
    from covariance_archive import CovarianceArchive


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
        raise ValueError("project paths must remain inside the repository: " + str(path))
    return path


def read_yield_panel(directory, maturities=TENORS, as_of=None, missing_policy="forward-fill"):
    """Join raw quote dates with explicit causal-fill or genuine-only selection.

    The original DGS column is authoritative; processed yield_clean never replaces
    missing raw observations. Counts and source hashes preserve the selection audit.
    """
    if missing_policy not in ("forward-fill", "observed"):
        raise ValueError("missing_policy must be forward-fill or observed")
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
        payload = p.read_bytes()
        if b"\x00" in payload:
            raise ValueError(str(p) + " contains an invalid NUL control character")
        try:
            records = list(csv.reader(io.StringIO(payload.decode("utf-8-sig")), strict=True))
        except (csv.Error, UnicodeDecodeError) as error:
            raise ValueError(str(p) + " contains malformed CSV: " + str(error)) from error
        header = records[0] if records else []
        rows = [row for row in records[1:] if row]
        if (not header or len(set(header)) != len(header)
                or any(len(row) != len(header) for row in rows)):
            raise ValueError(str(p) + " contains duplicate columns or malformed CSV rows")
        frame = pd.DataFrame(rows, columns=header, dtype=str)
        column = "DGS%d" % tenor
        if not {"observation_date", column}.issubset(frame.columns):
            raise ValueError(str(p) + " lacks date/yield columns")
        text_dates = frame.observation_date.astype(str)
        date_format = "%m/%d/%y" if text_dates.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}").all() else None
        dates = pd.to_datetime(frame.observation_date, errors="raise", format=date_format)
        if dates.isna().any() or dates.duplicated().any():
            raise ValueError(str(p) + " contains missing/duplicate dates")
        tokens = frame[column].astype(str).str.strip()
        missing_tokens = tokens.isin(["", "."])
        numeric = pd.to_numeric(tokens.mask(missing_tokens), errors="raise")
        if not np.isfinite(numeric[~missing_tokens]).all():
            raise ValueError(str(p) + " contains nonfinite quotes")
        values = pd.Series(numeric.to_numpy(), index=dates, name=tenor).sort_index()
        if cutoff is not None:
            values = values.loc[values.index <= cutoff]
        missing = int(values.isna().sum())
        source_rows = len(values)
        values = values.ffill() if missing_policy == "forward-fill" else values.dropna()
        if values.empty or not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError(str(p) + " requires finite positive yields with a known initial value")
        series.append(values)
        sources.append({"path": str(p.relative_to(ROOT)),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "rows_in_cutoff": source_rows, "rows_before_alignment": len(values),
                        "missing_quotes": missing, "missing_policy": missing_policy,
                        "excluded_missing_quotes": missing if missing_policy == "observed" else 0,
                        "filled_quotes": missing if missing_policy == "forward-fill" else 0})
    panel = pd.concat(series, axis=1, join="inner").sort_index()
    panel.index.name = "observation_date"
    if panel.empty:
        raise ValueError("maturity files have no common dates")
    for source in sources:
        source["rows_after_alignment"] = len(panel)
        source["excluded_alignment_rows"] = source["rows_before_alignment"] - len(panel)
    return panel, sources


def observation_steps(dates, dt=1 / 252, time_basis="observation"):
    """Return the explicit observation clock or chronological ACT/365F intervals.

    Calendar time counts actual elapsed days, including weekends, divided by 365
    even in leap years. This is a model clock, not a fitted business-time clock.
    """
    positive_number(dt, "dt")
    if time_basis not in ("observation", "act365f"):
        raise ValueError("time_basis must be observation or act365f")
    if (not isinstance(dates, pd.DatetimeIndex) or dates.hasnans or dates.has_duplicates
            or not dates.is_monotonic_increasing or len(dates) < 2):
        raise ValueError("clock needs at least two strictly increasing valid dates")
    if time_basis == "observation":
        return dt
    if dates.tz is not None or not dates.equals(dates.normalize()):
        raise ValueError("ACT/365F requires timezone-naive calendar dates without intraday times")
    # Use timedeltas rather than integer timestamp subtraction (which can overflow).
    durations = np.array([(right.date() - left.date()).days / 365.
                          for left, right in zip(dates[:-1], dates[1:])])
    return transition_steps(durations, len(dates) - 1)


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


def calibrate_panel(panel, window, dt=1 / 252, nll_budget=2., fallback_theta=.25,
                    time_basis="observation"):
    """Fit and jointly stabilize every date/maturity without future information."""
    panel = _validate_panel(panel, window)
    history = panel.to_numpy(dtype=float)
    durations = observation_steps(panel.index, dt, time_basis)
    prior = None
    records = []
    for end in range(window - 1, len(panel)):
        start = end - window + 1
        local_dt = durations if np.ndim(durations) == 0 else durations[start:end]
        fits, audit = stabilize_panel(history[start:end + 1], panel.columns,
                                      local_dt, nll_budget, fallback_theta, prior)
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


def calibrate_parameters(first_stage, window, dt=1 / 252, nll_budget=2., fallback_theta=.25,
                         time_basis="observation"):
    """Apply the same CIR estimation to all three estimated parameter histories.

    Never fill unavailable or failed first-stage estimates. Gaps raise an error
    with the affected parameter; warmup should be removed before this interface.
    """
    branches = []
    for parameter, panel in parameter_panels(first_stage).items():
        try:
            fitted = calibrate_panel(panel, window, dt, nll_budget, fallback_theta, time_basis)
        except ValueError as error:
            raise ValueError("cannot fit " + parameter + " history: " + str(error)) from error
        fitted.insert(2, "parameter", parameter)
        branches.append(fitted)
    return pd.concat(branches, ignore_index=True).sort_values(
        ["observation_date", "maturity", "parameter"]).reset_index(drop=True)



def walk_history(yields, first_stage, second_stage, window):
    """Align observed rates, estimated sigma and endogenous sigma-of-sigma.

    Keep `window` complete dates AFTER both estimation warmups. The first-pass
    fitted mu is a long-run mean; it is not the rate state in this array.
    """
    integer(window, 'history_window', 5)
    panels = parameter_panels(first_stage)
    sigma_rows = second_stage.loc[second_stage.parameter == 'sigma']
    if sigma_rows.duplicated(['observation_date', 'maturity']).any():
        raise ValueError('duplicate endogenous xi dates/maturities')
    xi = sigma_rows.pivot(index='observation_date', columns='maturity', values='sigma').sort_index()
    dates = xi.index
    if len(dates) < window:
        raise ValueError('insufficient calibrated history: need %d complete days of rate, sigma and xi; '
                         'pull more source history rather than shortening the required history' % window)
    dates = dates[-window:]
    maturities = yields.columns
    history = np.stack([yields.reindex(index=dates, columns=maturities).to_numpy(),
                        panels['sigma'].reindex(index=dates, columns=maturities).to_numpy(),
                        xi.reindex(index=dates, columns=maturities).to_numpy()], axis=1)
    if not np.isfinite(history).all() or (history < 0).any():
        raise ValueError('rate/sigma/xi histories contain unavailable or inadmissible values')
    return history, dates


def write_calibration_outputs(output, yields, first, second, dt, time_basis):
    """Export both calibration passes using the existing reconstruction schema."""
    output = repository_path(output)
    output.mkdir(parents=True, exist_ok=False)
    first.to_csv(output / 'yield_parameters.csv', index=False)
    second.to_csv(output / 'parameter_dynamics.csv', index=False)
    (output / 'RAW').mkdir()
    (output / 'CURVE').mkdir()
    durations = transition_steps(observation_steps(yields.index, dt, time_basis), len(yields) - 1)
    pd.DataFrame({'start_date': yields.index[:-1], 'end_date': yields.index[1:],
                  'dt_years': durations}).to_csv(output / 'transition_intervals.csv', index=False)
    for tenor in yields.columns:
        rows = first.loc[first.maturity == tenor].set_index('observation_date')
        original = pd.DataFrame({'DGS%d' % tenor: yields[tenor], 'yield_clean': yields[tenor]})
        original = original.join(rows[['theta', 'mu', 'sigma']]).reset_index()
        original.index = np.arange(1, len(original) + 1)
        original.to_csv(output / 'RAW' / ('DGS%d_with_parameters.csv' % tenor))
    for parameter, panel in parameter_panels(first).items():
        panel.columns = [parameter + str(tenor) + 'y' for tenor in panel.columns]
        panel.to_csv(output / 'CURVE' / (parameter + '_curve.csv'))


def calibration_hashes(output):
    """Seal the initial history and historical exports in the run manifest."""
    artifacts = [output / name for name in ('yield_parameters.csv', 'parameter_dynamics.csv',
                                       'transition_intervals.csv', 'initial_history.npz')]
    for directory in ('RAW', 'CURVE'):
        artifacts.extend(sorted((output / directory).iterdir()))
    return {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in artifacts}


def _json_file(path, payload):
    """Publish complete finite JSON atomically, without replacing an artifact."""
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + '\n').encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pending-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # An atomic exclusive link exposes only the completely written record.
        # Unlike replace(), it fails if another writer has created this name.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_years(output, history, maturities, years=1, steps_per_year=252,
              dt=1/252, substeps=1, seed=1234, history_dt=None,
              nll_budget=2., fallback_theta=.25, regularization=0.):
    """Walk complete years sequentially, carrying history, clock, RNG and anchors.

    There is one evolving trajectory and one year of reported states in memory.
    No new year restarts at a historical origin. Each actual increment retains
    its own covariance, coefficients, shocks and before/after states on disk.
    """
    integer(years, 'years', 1)
    integer(steps_per_year, 'steps_per_year', 1)
    positive_number(dt, 'dt')
    if not np.isclose(steps_per_year * dt, 1., rtol=0., atol=1e-12):
        raise ValueError('steps_per_year * dt must equal one year')
    if years > 1000:
        raise ValueError('years exceeds the explicit 1000-year local work limit')
    walk_workload(len(history), len(maturities), steps_per_year, substeps)
    output = repository_path(output)
    rng_state = None
    prior_thetas = None
    summaries = []
    for year in range(years):
        destination = output / ('year_%04d' % (year + 1))
        destination.mkdir(exist_ok=False)
        archive = CovarianceArchive(destination / 'covariance', maturities, ('rate', 'sigma', 'xi'))
        rng_state_before = rng_state
        prior_thetas_before = prior_thetas
        states, projections, diagnostics, history, history_dt = simulate_walk(
            history, maturities, steps=steps_per_year, dt=dt, substeps=substeps,
            seed=seed, history_dt=history_dt, nll_budget=nll_budget,
            fallback_theta=fallback_theta, regularization=regularization,
            archive=archive, rng_state=rng_state, prior_thetas=prior_thetas)
        archive_manifest = archive.finish()
        rng_state = diagnostics['rng_state']
        prior_thetas = diagnostics['prior_thetas']
        elapsed = year + np.arange(steps_per_year + 1) * dt
        np.savez_compressed(destination / 'trajectory.npz', states=states,
                            maturities=np.asarray(maturities), state_names=np.array(['rate', 'sigma', 'xi']),
                            elapsed_years=elapsed, boundary_projections=projections)
        with (destination / 'trajectory.csv').open('x', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['step', 'elapsed_years', 'state', 'maturity', 'value'])
            for step, state in enumerate(states):
                for family, name in enumerate(('rate', 'sigma', 'xi')):
                    for tenor, maturity in enumerate(maturities):
                        writer.writerow([step, format(elapsed[step], '.17g'), name, maturity,
                                         format(state[family, tenor], '.17g')])
        np.savez_compressed(destination / 'restart.npz', history=history, history_dt=history_dt,
                            prior_thetas=prior_thetas, maturities=np.asarray(maturities))
        files = {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                 for name in ('trajectory.npz', 'trajectory.csv', 'restart.npz', 'covariance/manifest.json')}
        report = {'schema_version': 2, 'status': 'complete', 'year': year + 1,
                  'elapsed_start_years': year, 'elapsed_end_years': year + 1,
                  'covariance_elapsed_time': 'relative to this year start',
                  'covariance_records': archive_manifest['increments'],
                  'rng_state_before': rng_state_before,
                  'prior_thetas_before': prior_thetas_before,
                  'diagnostics': diagnostics, 'files_sha256': files}
        _json_file(destination / 'manifest.json', report)
        summaries.append({'directory': destination.name, 'year': year + 1,
                          'manifest_sha256': hashlib.sha256((destination / 'manifest.json').read_bytes()).hexdigest(),
                          'covariance_records': archive_manifest['increments'],
                          'boundary_projections': int(projections.sum())})
        print(json.dumps({'completed_year': year + 1, 'years_requested': years,
                          'actual_increments': archive_manifest['increments']}), flush=True)
        # Release the annual array and its final CSV-row view before allocating
        # the following year. The rolling history and continuation state remain.
        del state, states, elapsed, projections
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description='Self-calibrate and advance rate, sigma and xi at every increment.')
    parser.add_argument('--input', default='RWA/FRED')
    parser.add_argument('--input-manifest', help='verify an acquired snapshot before reading its input series')
    parser.add_argument('--output', required=True, help='new directory inside the repository')
    parser.add_argument('--maturities', type=int, nargs='+', default=list(TENORS))
    parser.add_argument('--as-of')
    parser.add_argument('--yield-window', type=int, default=2520)
    parser.add_argument('--parameter-window', type=int, default=252)
    parser.add_argument('--history-window', type=int, default=2520,
                        help='complete calibrated daily history retained after both warmups')
    parser.add_argument('--recent-rows', type=int, default=0,
                        help='explicit raw-history truncation; zero uses every common observation')
    parser.add_argument('--dt', type=float, default=1/252, help='reported daily interval in years')
    parser.add_argument('--time-basis', choices=('observation', 'act365f'), default='observation')
    parser.add_argument('--missing-policy', choices=('forward-fill', 'observed'), default='forward-fill')
    parser.add_argument('--nll-budget', type=float, default=2.)
    parser.add_argument('--fallback-theta', type=float, default=.25)
    parser.add_argument('--correlation-regularization', type=float, default=0.,
                        help='explicit alpha in (1-alpha)*R + alpha*I; zero preserves empirical dependence')
    parser.add_argument('--years', type=int, default=1, help='consecutive full years; history continues across years')
    parser.add_argument('--steps-per-year', type=int, default=252)
    parser.add_argument('--substeps', type=int, default=1,
                        help='actual Euler increments per daily output; all recalibrate independently')
    parser.add_argument('--seed', type=int, default=1234)
    args = parser.parse_args(argv)
    try:
        output = repository_path(args.output)
        if output.exists():
            raise ValueError('output already exists; choose a new run directory')
        for value, name, minimum in ((args.recent_rows, 'recent_rows', 0),
                                     (args.yield_window, 'yield_window', 4),
                                     (args.parameter_window, 'parameter_window', 4),
                                     (args.history_window, 'history_window', 5),
                                     (args.years, 'years', 1),
                                     (args.steps_per_year, 'steps_per_year', 1),
                                     (args.substeps, 'substeps', 1), (args.seed, 'seed', 0)):
            integer(value, name, minimum)
        if args.years > 1000:
            raise ValueError('years exceeds the explicit 1000-year local work limit')
        positive_number(args.dt, 'dt')
        positive_number(args.nll_budget, 'nll_budget', allow_zero=True)
        positive_number(args.fallback_theta, 'fallback_theta')
        positive_number(args.correlation_regularization, 'correlation_regularization', allow_zero=True)
        if args.correlation_regularization > 1:
            raise ValueError('correlation_regularization must be at most one')
        if not np.isclose(args.steps_per_year * args.dt, 1., rtol=0., atol=1e-12):
            raise ValueError('steps_per_year * dt must equal one year')
        walk_workload(args.history_window, len(args.maturities), args.steps_per_year, args.substeps)
        acquisition = (verify_snapshot(args.input_manifest, args.input, args.maturities)
                       if args.input_manifest else None)
        yields, sources = read_yield_panel(args.input, args.maturities, args.as_of, args.missing_policy)
        yields = yields.reindex(sorted(yields.columns), axis=1)
        if args.recent_rows:
            yields = yields.iloc[-args.recent_rows:]
        required = args.yield_window + args.parameter_window + args.history_window - 2
        if len(yields) < required:
            raise ValueError('need at least %d common source observations to produce %d complete calibrated '
                             'history days after both warmups; only %d available' %
                             (required, args.history_window, len(yields)))
        print(json.dumps({'stage': 'historical_calibration', 'source_rows': len(yields),
                          'required_source_rows': required}), flush=True)
        first = calibrate_panel(yields, args.yield_window, args.dt,
                                args.nll_budget, args.fallback_theta, args.time_basis)
        print(json.dumps({'stage': 'parameter_calibration', 'first_stage_rows': len(first)}), flush=True)
        second = calibrate_parameters(first, args.parameter_window, args.dt,
                                      args.nll_budget, args.fallback_theta, args.time_basis)
        history, dates = walk_history(yields, first, second, args.history_window)
        durations = observation_steps(dates, args.dt, args.time_basis)
        write_calibration_outputs(output, yields, first, second, args.dt, args.time_basis)
        np.savez_compressed(output / 'initial_history.npz', history=history,
                            history_dt=transition_steps(durations, len(history)-1),
                            maturities=yields.columns.to_numpy(),
                            state_names=np.array(['rate', 'sigma', 'xi']),
                            dates=dates.strftime('%Y-%m-%d').to_numpy(dtype=str))
        years = run_years(output, history, yields.columns.to_numpy(), args.years,
                          args.steps_per_year, args.dt, args.substeps, args.seed, durations,
                          args.nll_budget, args.fallback_theta, args.correlation_regularization)
        historical_dt = transition_steps(observation_steps(yields.index, args.dt, args.time_basis), len(yields)-1)
        manifest = {'schema_version': 2, 'status': 'complete', 'settings': vars(args),
                    'source_files': sources, 'units': 'FRED percentage points for rates',
                    'files_sha256': calibration_hashes(output),
                    'yield_acquisition': acquisition,
                    'time_convention': {'basis': args.time_basis, 'forecast_dt_years': args.dt,
                                        'actual_increment_years': args.dt/args.substeps,
                                        'min_historical_dt_years': float(historical_dt.min()),
                                        'max_historical_dt_years': float(historical_dt.max()),
                                        'sum_historical_dt_years': float(historical_dt.sum()),
                                        'historical_interval_count': len(historical_dt)},
                    'history_start': str(yields.index[0].date()),
                    'walk_history_start': str(dates[0].date()),
                    'walk_history_rows': len(history),
                    'forecast_origin': str(yields.index[-1].date()),
                    'first_stage_rows': len(first), 'second_stage_rows': len(second),
                    'max_first_stage_nll_cost': float(first.nll_cost.max()),
                    'max_second_stage_nll_cost': float(second.nll_cost.max()),
                    'state_names': ['rate', 'sigma', 'xi'],
                    'update_order': ['self_calibration_and_covariance', 'xi', 'sigma', 'rate', 'append_history'],
                    'covariance_shape_per_set': [3, len(yields.columns), len(yields.columns)],
                    'covariance_sets': ['factor_covariance', 'brownian_covariance'],
                    'years': years,
                    'limitations': ['Estimated volatility histories contain calibration and ridge-estimation effects.',
                                    'Xi evolves as the CIR process described in the ordered update; it is not reset to a fitted diffusion after each step.',
                                    'Independent family Gaussian drivers; no additional cross-family rho is introduced.',
                                    'Gaussian Euler likelihood and nonnegative projection require numerical and empirical assessment.',
                                    'No exposure valuation, arbitrage-free curve construction or RWA capital mapping.']}
        _json_file(output / 'manifest.json', manifest)
        print(json.dumps({'output': str(output), 'status': 'complete', 'completed_years': len(years)}), flush=True)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, 'Hierarchy failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
