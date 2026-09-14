"""Path-conditioned rolling recalibration of the finite CIR parameter hierarchy.

This adaptive closure evolves X, mu, theta and sigma as states. At a requested
reported-step cadence, each path learns the three parameter processes and joint
innovation dependence from its own trailing history. It does not replace the
simulated parameter states with new yield MLEs or introduce an infinite hierarchy.
"""

import numpy as np

if __package__:
    from .core import (integer, positive_number, stabilize_panel,
                       innovation_correlation, step_hierarchy,
                       transition_steps, joint_standardized_residuals)
else:
    from core import (integer, positive_number, stabilize_panel,
                      innovation_correlation, step_hierarchy,
                      transition_steps, joint_standardized_residuals)


PARAMETERS = ("mu", "theta", "sigma")
MAX_ELEMENTS = 20_000_000
MAX_WORK_UNITS = 50_000_000
MAX_SCALAR_FITS = 150_000
MAX_UPDATE_RECORDS = 10_000
MAX_PATH_SUBSTEPS = 250_000


def _mixed_boundaries(history, maturities):
    """Reject histories needing a boundary-aware likelihood, without clipping."""
    mixed = (history == 0).any(axis=0) & (history > 0).any(axis=0)
    if mixed.any():
        component, tenor = np.argwhere(mixed)[0]
        raise ValueError("mixed zero/positive " + ("X", *PARAMETERS)[component]
                         + " history at maturity " + str(maturities[tenor])
                         + " requires a boundary-aware fit")


def _refit(history, coefficients, maturities, dt, nll_budget, fallback_theta,
           shrinkage):
    """Fit one ordered path window; supplied coefficients provide causal anchors."""
    _mixed_boundaries(history, maturities)
    updated = np.empty_like(coefficients)
    audits = []
    for component, name in enumerate(PARAMETERS):
        try:
            fits, audit = stabilize_panel(
                history[:, component + 1], maturities, dt, nll_budget,
                fallback_theta, prior_thetas=coefficients[component, 0])
        except ValueError as error:
            raise ValueError("cannot refit " + name + ": " + str(error)) from error
        for tenor, (fit, item) in enumerate(zip(fits, audit)):
            if (not item["usable"] or not np.isfinite([fit.theta, fit.mu, fit.sigma, fit.nll]).all()
                    or not np.isfinite(item["nll_cost"])
                    or fit.theta <= 0 or fit.mu < 0 or fit.sigma < 0):
                raise ValueError("unusable " + name + " fit at maturity "
                                 + str(maturities[tenor]))
            updated[component, :, tenor] = fit.theta, fit.mu, fit.sigma
        audits.extend(audit)
    residuals = joint_standardized_residuals(history, updated, dt)
    correlation, factor, dependence = innovation_correlation(
        residuals.reshape(len(residuals), -1), shrinkage)
    sources = {}
    for item in audits:
        source = item["anchor_source"]
        sources[source] = sources.get(source, 0) + 1
    report = {"max_nll_cost": float(max(item["nll_cost"] for item in audits)),
              "weak_fits": int(sum(item["weak"] for item in audits)),
              "regularized_fits": int(sum(item["regularized"] for item in audits)),
              "anchor_sources": sources,
              "min_correlation_eigenvalue": dependence["min_eigenvalue"],
              "constant_innovation_columns": dependence["constant_columns"]}
    return updated, correlation, factor, report


def simulate_recursive(history, coefficients, factor, maturities, paths=256,
                       steps=20, dt=1 / 252, seed=1234, substeps=4,
                       recalibrate_every=1, nll_budget=2., fallback_theta=.25,
                       shrinkage=.05, history_dt=None):
    """Return states, projection counts and JSON-compatible pathwise fit evidence.

    ``history`` has shape (window, 4, maturities), ordered oldest to origin with
    at least five rows. Coefficients have shape (3, 3, maturities), with parameter
    branches mu/theta/sigma and coefficient order theta/mu/sigma. ``factor`` is
    the origin's joint factor in flattened state-major order.

    ``history_dt`` supplies a scalar or one year interval per historical
    transition; omission uses ``dt`` for compatibility. Future reported steps
    remain exactly ``dt`` years. Historical intervals leave the window with
    their state transitions, and each appended forecast state adds one ``dt``.

    Supplied origin coefficients/factor drive the first reported step. Append
    only reported states to each path's fixed-size buffer. At positive multiples
    of ``recalibrate_every`` strictly before the final step, refit from the now
    available window before drawing the next shock. Cadence zero disables refits
    and exactly reproduces workflow.simulate for the same origin and RNG inputs.

    A run is rejected before allocation above 20 million numeric array elements,
    50 million window*3*maturities*path-refits work units, 150,000 scalar fits or
    10,000 path/origin audit records or 250,000 path/substep advances. These are
    transparent workload ceilings,
    not wall-clock guarantees. Reduce paths, horizon, window or refit frequency.
    No failed paths are discarded or replaced; one failure aborts the whole run.
    """
    for value, name, minimum in ((paths, "paths", 1), (steps, "steps", 1),
                                  (seed, "seed", 0), (substeps, "substeps", 1),
                                  (recalibrate_every, "recalibrate_every", 0)):
        integer(value, name, minimum)
    paths, steps, seed, substeps, recalibrate_every = map(
        int, (paths, steps, seed, substeps, recalibrate_every))
    positive_number(dt, "dt")
    positive_number(nll_budget, "nll_budget", allow_zero=True)
    positive_number(fallback_theta, "fallback_theta")
    positive_number(shrinkage, "shrinkage")
    if shrinkage > 1:
        raise ValueError("shrinkage must be at most one")
    h = np.asarray(history, dtype=float)
    c = np.asarray(coefficients, dtype=float)
    origin_factor = np.asarray(factor, dtype=float)
    tenors = np.asarray(maturities, dtype=float)
    if (h.ndim != 3 or h.shape[0] < 5 or h.shape[1] != 4 or h.shape[2] < 1
            or not np.isfinite(h).all() or (h < 0).any()):
        raise ValueError("history needs at least five finite nonnegative (4,maturity) rows")
    window, _, dimensions = h.shape
    rolling_intervals = transition_steps(dt if history_dt is None else history_dt,
                                        window - 1)
    if (tenors.ndim != 1 or len(tenors) != dimensions or not np.isfinite(tenors).all()
            or (tenors <= 0).any() or len(np.unique(tenors)) != dimensions):
        raise ValueError("maturities must be distinct positive numbers matching history")
    initial = h[-1]
    delta = dt / substeps
    origin_count = (steps - 1) // recalibrate_every if recalibrate_every else 0
    update_count = paths * origin_count
    scalar_fits = update_count * 3 * dimensions
    work_units = scalar_fits * window
    path_substeps = paths * steps * substeps
    # Include returned states, rolling buffers, path coefficients/factors, state
    # and shock arrays, plus one ordered-window scratch space used by all paths.
    elements = paths * (steps + 3) * 4 * dimensions + 2 * (4 * dimensions) ** 2
    elements += window - 1  # one shared chronological transition clock
    if origin_count:
        elements += (paths * window * 4 * dimensions + paths * 9 * dimensions
                     + paths * (4 * dimensions) ** 2 + window * 4 * dimensions)
    if elements > MAX_ELEMENTS:
        raise ValueError("recursive simulation exceeds the 20-million-element memory bound")
    if (work_units > MAX_WORK_UNITS or scalar_fits > MAX_SCALAR_FITS
            or update_count > MAX_UPDATE_RECORDS):
        raise ValueError("recursive recalibration exceeds the work bound; reduce paths, horizon or window, or increase recalibrate_every")
    if path_substeps > MAX_PATH_SUBSTEPS:
        raise ValueError("simulation exceeds the 250,000 path/substep work bound; reduce paths, horizon or substeps")
    origins = list(range(recalibrate_every, steps, recalibrate_every)) if origin_count else []
    # Same shape/value checks as the frozen simulator, after work bounds and
    # before allocating paths. Factor validation itself multiplies dense arrays.
    step_hierarchy(initial, c, np.zeros_like(initial), origin_factor, dt)
    if np.max(c[:, 0]) * delta > 1:
        raise ValueError("path 0, origin step 0: parameter mean reversion exceeds the step scale; increase substeps")
    if origins and (c[:, 0] <= 0).any():
        raise ValueError("path 0, origin step 0: recursive prior speeds must be positive")
    state = np.broadcast_to(initial, (paths, 4, dimensions)).copy()
    result = np.empty((paths, steps + 1, 4, dimensions))
    result[:, 0] = state
    projections = np.zeros((4, dimensions), dtype=np.int64)
    origin_correlation = origin_factor @ origin_factor.T
    diagnostics = {
        "closure": "pathwise rolling finite-depth parameter calibration",
        "rolling_window": int(window), "recalibrate_every": int(recalibrate_every),
        "recalibrated_origins": origins, "recalibration_count": 0,
        "work_units": int(work_units), "scalar_fits": int(scalar_fits),
        "path_substeps": int(path_substeps),
        "forecast_step_years": float(dt),
        "initial_history_elapsed_years": float(rolling_intervals.sum()),
        "initial_history_min_transition_years": float(rolling_intervals.min()),
        "initial_history_max_transition_years": float(rolling_intervals.max()),
        "max_nll_cost": 0., "max_coefficient_change_from_origin": 0.,
        "max_correlation_change_from_origin": 0., "projection_count": 0,
        "updates": []}
    if origins:
        buffers = np.broadcast_to(h, (paths,) + h.shape).copy()
        ordered = np.empty_like(h)
        path_coefficients = np.broadcast_to(c, (paths,) + c.shape).copy()
        path_factors = np.broadcast_to(origin_factor, (paths,) + origin_factor.shape).copy()
    cursor = 0
    adapted = False
    rng = np.random.default_rng(seed)
    for step in range(steps):
        if step and recalibrate_every and step % recalibrate_every == 0:
            for path in range(paths):
                # cursor is the oldest row; restore chronological order into a
                # preallocated scratch buffer, never borrowing another path.
                tail = window - cursor
                ordered[:tail] = buffers[path, cursor:]
                ordered[tail:] = buffers[path, :cursor]
                try:
                    updated, correlation, new_factor, report = _refit(
                        ordered, path_coefficients[path], tenors, rolling_intervals,
                        nll_budget, fallback_theta, shrinkage)
                    if np.max(updated[:, 0]) * delta > 1:
                        raise ValueError("refitted parameter mean reversion exceeds the step scale; increase substeps")
                except (ValueError, np.linalg.LinAlgError) as error:
                    raise ValueError("path %d, origin step %d: %s" % (path, step, error)) from error
                change = np.abs(updated - path_coefficients[path])
                previous_correlation = path_factors[path] @ path_factors[path].T
                report.update(
                    path=int(path), origin_step=int(step),
                    observed_history_rows=int(max(0, window - step)),
                    simulated_history_rows=int(min(window, step)),
                    observed_history_transitions=int(max(0, window - step - 1)),
                    simulated_history_transitions=int(min(window - 1, step)),
                    history_elapsed_years=float(rolling_intervals.sum()),
                    history_min_transition_years=float(rolling_intervals.min()),
                    history_max_transition_years=float(rolling_intervals.max()),
                    coefficient_max_change=float(change.max()),
                    correlation_max_change=float(np.max(np.abs(correlation - previous_correlation))),
                    coefficient_max_change_from_origin=float(np.max(np.abs(updated - c))),
                    correlation_max_change_from_origin=float(np.max(np.abs(correlation - origin_correlation))),
                    parameter_coefficient_max_changes=change.max(axis=(1, 2)).tolist(),
                    parameter_diffusion_max_changes=change[:, 2].max(axis=1).tolist(),
                    xi_min=float(updated[2, 2].min()), xi_max=float(updated[2, 2].max()))
                diagnostics["updates"].append(report)
                diagnostics["recalibration_count"] += 1
                diagnostics["max_nll_cost"] = max(diagnostics["max_nll_cost"], report["max_nll_cost"])
                for name in ("coefficient", "correlation"):
                    key = "max_" + name + "_change_from_origin"
                    diagnostics[key] = max(diagnostics[key], report[name + "_max_change_from_origin"])
                path_coefficients[path] = updated
                path_factors[path] = new_factor
            adapted = True
        for substep in range(substeps):
            unstable = np.argwhere(state[:, 2] * delta > 1)
            if len(unstable):
                raise ValueError("path %d, step %d, substep %d: yield mean reversion exceeds the step scale; increase substeps"
                                 % (unstable[0, 0], step + 1, substep + 1))
            # Preserve the frozen simulator's draw shape and ordering, including
            # when independently applying the learned factor to each path.
            shocks = rng.standard_normal(state.shape)
            if not adapted:
                try:
                    next_state, hits = step_hierarchy(state, c, shocks, origin_factor, delta)
                except ValueError as error:
                    # Re-evaluate the already drawn shocks only to identify the
                    # failing path; never replace a draw or filter survivors.
                    for path in range(paths):
                        try:
                            step_hierarchy(state[path], c, shocks[path], origin_factor, delta)
                        except ValueError as cause:
                            raise ValueError("path %d, step %d, substep %d: %s"
                                             % (path, step + 1, substep + 1, cause)) from cause
                    raise ValueError("step %d, substep %d: %s" % (step + 1, substep + 1, error)) from error
                state = next_state
                projections += hits.sum(axis=0)
            else:
                for path in range(paths):
                    try:
                        state[path], hits = step_hierarchy(
                            state[path], path_coefficients[path], shocks[path],
                            path_factors[path], delta)
                    except ValueError as error:
                        raise ValueError("path %d, step %d, substep %d: %s"
                                         % (path, step + 1, substep + 1, error)) from error
                    projections += hits
        result[:, step + 1] = state
        if origins:
            buffers[:, cursor] = state
            cursor = (cursor + 1) % window
            # The clock is common to all paths, even though their states and
            # learned coefficients differ. Keep it chronological independently
            # of the circular state buffer so refits cannot misalign intervals.
            rolling_intervals[:-1] = rolling_intervals[1:]
            rolling_intervals[-1] = dt
    diagnostics["projection_count"] = int(projections.sum())
    return result, projections, diagnostics
