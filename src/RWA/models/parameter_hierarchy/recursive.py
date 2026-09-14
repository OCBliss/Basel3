"""One chronological, continuously recalibrated rate/sigma/xi walk.

Every actual Euler increment estimates separate family matrices and CIR drift fits
from the available rolling LEVEL history. Fresh matrices drive xi; updated xi
drives sigma; updated sigma drives the rate. Append each increment to history.
"""

from copy import deepcopy
from time import perf_counter
import numpy as np

if __package__:
    from .core import (integer, positive_number, stabilize_panel,
                       stabilize_conditioned_panel, transition_steps)
    from .covariance import family_covariances, brownian_increments
else:
    from core import (integer, positive_number, stabilize_panel,
                      stabilize_conditioned_panel, transition_steps)
    from covariance import family_covariances, brownian_increments

FAMILIES = ("rate", "sigma", "xi")
MAX_ELEMENTS = 20_000_000
MAX_INCREMENTS = 1_000_000


def walk_workload(window, dimensions, steps, substeps):
    """Reject impossible local allocations before calibration or output creation."""
    for value, name, minimum in ((window, 'history_window', 4), (dimensions, 'maturities', 1),
                                 (steps, 'steps', 1), (substeps, 'substeps', 1)):
        integer(value, name, minimum)
    window, dimensions, steps, substeps = map(int, (window, dimensions, steps, substeps))
    count = steps * substeps
    scalar_fits = count * 3 * dimensions
    elements = (steps + 1) * 3 * dimensions + 6 * window * dimensions + 18 * dimensions**2
    if elements > MAX_ELEMENTS:
        raise ValueError('walk exceeds the 20-million-element memory bound')
    if count > MAX_INCREMENTS:
        raise ValueError('walk exceeds the one-million actual-increment bound')
    return {'increments': count, 'scalar_fits': scalar_fits,
            'work_units': scalar_fits * window, 'elements': elements}


def _numeric(values, name):
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError) as error:
        raise ValueError(name + " must contain finite real numeric values") from error
    if raw.dtype.kind not in "iuf":
        raise ValueError(name + " must contain real numbers, not strings or booleans")
    with np.errstate(over="ignore", invalid="ignore"):
        result = raw.astype(float, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(name + " must remain finite in float64 precision")
    return result


def _audit_record(item):
    """Preserve undefined identification diagnostics without nonstandard JSON."""
    result, undefined = {}, []
    for name, value in item.items():
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            undefined.append(name)
            value = None
        result[name] = value
    if undefined:
        result["undefined_numeric_fields"] = undefined
    return result


def _calibrate(history, maturities, intervals, nll_budget, fallback_theta, priors):
    dimensions = history.shape[2]
    coefficients = np.empty((3, 3, dimensions))
    audits = []
    for family, name in enumerate(FAMILIES):
        try:
            prior = None if priors is None else priors[family]
            if family < 2:
                fits, records = stabilize_conditioned_panel(
                    history[:, family], history[:, family + 1], maturities,
                    intervals, nll_budget, fallback_theta, prior_thetas=prior)
            else:
                fits, records = stabilize_panel(
                    history[:, family], maturities, intervals, nll_budget,
                    fallback_theta, prior_thetas=prior)
        except ValueError as error:
            raise ValueError("cannot calibrate " + name + ": " + str(error)) from error
        if len(fits) != dimensions or len(records) != dimensions:
            raise ValueError("incomplete " + name + " calibration")
        for tenor, (fit, record) in enumerate(zip(fits, records)):
            if (not record["usable"] or not np.isfinite([fit.theta, fit.mu, fit.nll]).all()
                    or not np.isfinite(record["nll_cost"])
                    or fit.theta <= 0 or fit.mu < 0):
                raise ValueError("unusable " + name + " fit at maturity " + str(maturities[tenor]))
            if family == 2:
                if not np.isfinite(fit.sigma) or fit.sigma < 0:
                    raise ValueError("unusable xi diffusion at maturity " + str(maturities[tenor]))
                diffusion = fit.sigma
            else:
                # This is an internal placeholder until the ordered advance
                # supplies the actual new higher state. It is not a fitted sigma.
                diffusion = history[-1, family + 1, tenor]
            coefficients[family, :, tenor] = fit.theta, fit.mu, diffusion
        source = ("updated sigma state", "updated xi state", "CIR fitted diffusion")[family]
        audits.append([dict(_audit_record(record), diffusion_source=source) for record in records])
    return coefficients, audits


def _advance(state, coefficients, increments, delta):
    """Apply the specified xi -> sigma -> rate ordering to one increment."""
    theta, mean, diffusion = (coefficients[:, index] for index in range(3))
    candidate = np.empty_like(state)
    projected = np.zeros_like(state, dtype=bool)
    with np.errstate(over="ignore", invalid="ignore"):
        raw_xi = (state[2] + theta[2] * (mean[2] - state[2]) * delta
                  + diffusion[2] * np.sqrt(state[2]) * increments[2])
        candidate[2] = np.maximum(raw_xi, 0.)
        projected[2] = raw_xi < 0.
        raw_sigma = (state[1] + theta[1] * (mean[1] - state[1]) * delta
                     + candidate[2] * np.sqrt(state[1]) * increments[1])
        candidate[1] = np.maximum(raw_sigma, 0.)
        projected[1] = raw_sigma < 0.
        raw_rate = (state[0] + theta[0] * (mean[0] - state[0]) * delta
                    + candidate[1] * np.sqrt(state[0]) * increments[0])
        candidate[0] = np.maximum(raw_rate, 0.)
        projected[0] = raw_rate < 0.
    if not all(np.isfinite(values).all() for values in (raw_xi, raw_sigma, raw_rate, candidate)):
        raise ValueError("nonfinite updated state; inspect calibration and timestep")
    return candidate, projected


def simulate_walk(history, maturities, *, steps=252, dt=1 / 252, substeps=1,
                  seed=1234, history_dt=None, nll_budget=2., fallback_theta=.25,
                  regularization=0., archive=None, normal_shocks=None,
                  rng_state=None, prior_thetas=None):
    """Return reported states, projections, diagnostics, final history and clock.

    History is (window,3,maturities), ordered rate/sigma/xi. Its supplied window
    length is preserved for all three families, including a 2,520-row history.
    There is one chronological walk and no path axis or frozen mode. Each
    reported step lasts dt years with substeps increments of delta=dt/substeps.
    Every increment, including the first, estimates matrices and all CIR fits
    before drawing; updates xi, sigma, rate; archives; and rolls in the result.

    Coefficients have axes (family, theta/long_run_mean/actual_diffusion, maturity).
    Rate/sigma drift likelihoods condition on the next higher family's observed
    right-endpoint history. Only xi fits a free scalar CIR diffusion. Archived
    rate/sigma diffusion coordinates contain the updated sigma/xi states actually
    used in that increment. Positive prior_thetas (3,maturities)
    are only causal ridge anchors. Diagnostics return final anchors and RNG
    state; pass those with final history/history_dt for exact continuation.

    normal_shocks is optionally an iterator of single (3,maturities) arrays.
    It replaces random generation and is never read ahead. Its caller maintains
    iterator position for continuation. archive.append runs per increment;
    the caller owns archive.finish and publication of the complete run.
    """
    started = perf_counter()
    for value, name, minimum in ((steps, "steps", 1), (substeps, "substeps", 1), (seed, "seed", 0)):
        integer(value, name, minimum)
    steps, substeps, seed = int(steps), int(substeps), int(seed)
    positive_number(dt, "dt")
    positive_number(nll_budget, "nll_budget", allow_zero=True)
    positive_number(fallback_theta, "fallback_theta")
    positive_number(regularization, "regularization", allow_zero=True)
    if regularization > 1:
        raise ValueError("regularization must be at most one")
    try:
        raw_history = np.asarray(history)
    except (TypeError, ValueError) as error:
        raise ValueError('history must have shape (window,3,maturity)') from error
    if (raw_history.ndim != 3 or raw_history.shape[0] < 4
            or raw_history.shape[1] != 3 or raw_history.shape[2] < 1):
        raise ValueError('history needs at least four finite nonnegative (3,maturity) rows')
    window, _, dimensions = raw_history.shape
    workload = walk_workload(window, dimensions, steps, substeps)
    # Check a broadcast view's size before materializing its float64 copy.
    h = _numeric(raw_history, 'history')
    if (h < 0).any():
        raise ValueError('history needs nonnegative state values')
    tenors = _numeric(maturities, "maturities")
    if (tenors.shape != (dimensions,) or (tenors <= 0).any()
            or len(np.unique(tenors)) != dimensions):
        raise ValueError("maturities must be distinct positive numbers matching history")
    intervals = transition_steps(dt if history_dt is None else history_dt, window - 1)
    delta = float(dt) / substeps
    positive_number(delta, "increment dt")
    count = workload['increments']
    scalar_fits = workload['scalar_fits']
    work_units = workload['work_units']
    priors = None if prior_thetas is None else _numeric(prior_thetas, "prior_thetas")
    if priors is not None and (priors.shape != (3, dimensions) or (priors <= 0).any()):
        raise ValueError("prior_thetas must contain a positive speed per family and maturity")
    if normal_shocks is not None and rng_state is not None:
        raise ValueError("normal_shocks and rng_state are mutually exclusive")
    tape = None
    rng = None
    if normal_shocks is not None:
        try:
            tape = iter(normal_shocks)
        except TypeError as error:
            raise ValueError("normal_shocks must be an iterator of (3,maturity) increments") from error
    else:
        rng = np.random.default_rng(seed)
        if rng_state is not None:
            try:
                rng.bit_generator.state = deepcopy(rng_state)
            except (TypeError, ValueError, KeyError, OverflowError) as error:
                raise ValueError("rng_state is not a compatible saved generator state") from error
    if archive is not None and not callable(getattr(archive, "append", None)):
        raise ValueError("archive must provide append for each actual increment")
    state = h[-1].copy()
    reported = np.empty((steps + 1, 3, dimensions))
    reported[0] = state
    projections = np.zeros((3, dimensions), dtype=np.int64)
    first_coefficients = first_correlation = previous_coefficients = previous_correlation = None
    diagnostics = {
        "mode": "single chronological rate/sigma/xi walk",
        "family_order": list(FAMILIES), "update_order": ["xi", "sigma", "rate"],
        "coefficient_order": ["theta", "long_run_mean", "actual_diffusion"],
        "diffusion_sources": ["updated sigma state", "updated xi state", "CIR fitted diffusion"],
        "reported_steps": steps, "substeps": substeps, "increments": count,
        "calibration_count": 0, "family_fit_count": 0, "scalar_fits": scalar_fits,
        "estimated_calibration_work_units": work_units,
        "matrix_refresh_count": 0, "rolling_window": window,
        "reported_step_years": float(dt), "increment_years": delta,
        "regularization": float(regularization),
        "initial_history_elapsed_years": float(intervals.sum()),
        "max_nll_cost": 0., "weak_fits": 0, "regularized_fits": 0,
        "max_coefficient_change": 0., "max_correlation_change": 0.,
        "max_coefficient_change_from_origin": 0., "max_correlation_change_from_origin": 0.}
    for increment in range(count):
        try:
            matrices = family_covariances(h, delta, regularization)
            coefficients, audits = _calibrate(h, tenors, intervals, nll_budget, fallback_theta, priors)
            if np.max(coefficients[:, 0]) * delta > 1.:
                raise ValueError("mean reversion exceeds the increment scale; increase substeps")
            if tape is None:
                draws = rng.standard_normal((3, dimensions))
            else:
                try:
                    draws = next(tape)
                except StopIteration as error:
                    raise ValueError("normal_shocks ended before the walk completed") from error
            draws = _numeric(draws, "normal_shocks increment")
            dw = brownian_increments(draws, matrices["cholesky"], delta)
            updated, hits = _advance(state, coefficients, dw, delta)
            coefficients[0, 2] = updated[1]
            coefficients[1, 2] = updated[2]
            if archive is not None:
                archive.append(increment, increment * delta, delta, matrices, state, updated,
                               brownian_increments=dw, coefficients=coefficients,
                               calibration_audit={"family_order": list(FAMILIES), "families": audits},
                               normal_shocks=draws)
        except (ValueError, np.linalg.LinAlgError) as error:
            raise ValueError("increment %d: %s" % (increment, error)) from error
        corr = matrices["correlation"]
        if first_coefficients is None:
            first_coefficients, first_correlation = coefficients.copy(), corr.copy()
        else:
            diagnostics["max_coefficient_change"] = max(
                diagnostics["max_coefficient_change"], float(np.max(np.abs(coefficients - previous_coefficients))))
            diagnostics["max_correlation_change"] = max(
                diagnostics["max_correlation_change"], float(np.max(np.abs(corr - previous_correlation))))
        diagnostics["max_coefficient_change_from_origin"] = max(
            diagnostics["max_coefficient_change_from_origin"], float(np.max(np.abs(coefficients - first_coefficients))))
        diagnostics["max_correlation_change_from_origin"] = max(
            diagnostics["max_correlation_change_from_origin"], float(np.max(np.abs(corr - first_correlation))))
        previous_coefficients, previous_correlation = coefficients, corr
        for family_records in audits:
            for record in family_records:
                diagnostics["max_nll_cost"] = max(diagnostics["max_nll_cost"], record["nll_cost"])
                diagnostics["weak_fits"] += int(record["weak"])
                diagnostics["regularized_fits"] += int(record["regularized"])
        diagnostics["calibration_count"] += 1
        diagnostics["family_fit_count"] += 3
        diagnostics["matrix_refresh_count"] += 1
        state = updated
        projections += hits
        h[:-1] = h[1:]
        h[-1] = state
        intervals[:-1] = intervals[1:]
        intervals[-1] = delta
        priors = coefficients[:, 0].copy()
        if (increment + 1) % substeps == 0:
            reported[(increment + 1) // substeps] = state
    diagnostics.update(projection_count=int(projections.sum()),
                       final_history_elapsed_years=float(intervals.sum()),
                       prior_thetas=priors.tolist(),
                       rng_state=None if rng is None else deepcopy(rng.bit_generator.state),
                       elapsed_seconds=float(perf_counter() - started))
    return reported, projections, diagnostics, h, intervals
