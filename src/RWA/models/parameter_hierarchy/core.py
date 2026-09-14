"""Conditional Euler CIR calibration and endogenous parameter dynamics.

The fitted drift is a - theta*x, a=theta*mu. Profiling a and sigma at a
chosen theta lets us regularize a weak mean-reversion fit without separately
interpolating two parameters whose product determines the observed drift.
See readme.md for assumptions, derivations and validation limits.
"""

from dataclasses import dataclass, replace

import numpy as np


@dataclass(frozen=True)
class CIRFit:
    a: float
    theta: float
    mu: float
    sigma: float
    theta_se: float
    nll: float
    weak: bool
    deterministic: bool = False


@dataclass(frozen=True)
class DriftFit:
    """CIR drift fitted conditional on a supplied volatility history.

    There is no fitted diffusion parameter: each transition variance is known
    from its matched higher-layer state. Constant observations do not make that
    positive-variance conditional model deterministic.
    """
    a: float
    theta: float
    mu: float
    theta_se: float
    nll: float
    weak: bool
    deterministic: bool = False


def positive_number(value, name, allow_zero=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be a finite number")
    if not np.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(name + " must be finite and " +
                         ("nonnegative" if allow_zero else "positive"))


def integer(value, name, minimum):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(name + " must be an integer")
    if value < minimum:
        raise ValueError(name + " must be at least " + str(minimum))


def transition_steps(dt, n):
    """Return one positive finite year interval per chronological transition.

    A scalar preserves the fixed-step interface; an array must have exactly n
    entries. Do not broadcast a one-element vector, coerce numeric strings or
    accept booleans as elapsed time. The returned array never aliases the input.
    """
    integer(n, "transition count", 1)
    try:
        raw = np.asarray(dt)
    except (TypeError, ValueError) as error:
        raise ValueError("dt must be a positive number or one-dimensional transition array") from error
    if raw.ndim > 1 or raw.dtype.kind not in "iuf":
        raise ValueError("dt must contain finite positive numeric transition intervals")
    # NumPy promotes a mixed Python [True, .1] sequence to float; retain the
    # strict scalar contract before that implicit coercion loses its type.
    if isinstance(dt, (list, tuple)) and any(isinstance(x, (bool, np.bool_)) for x in dt):
        raise ValueError("dt must not contain booleans")
    if raw.ndim == 0:
        positive_number(raw.item(), "dt")
        value = float(raw)
        positive_number(value, "dt")
        return np.full(n, value, dtype=float)
    if raw.shape != (n,) or not np.isfinite(raw).all() or (raw <= 0).any():
        raise ValueError("dt must have one finite positive interval per transition (" + str(n) + ")")
    result = raw.astype(float, copy=True)
    if not np.isfinite(result).all() or (result <= 0).any():
        raise ValueError("dt must remain finite and positive in float64 precision")
    return result


def _sample(values):
    v = np.asarray(values, dtype=float)
    if v.ndim != 1 or len(v) < 4 or not np.isfinite(v).all() or (v < 0).any():
        raise ValueError("CIR history needs at least four finite nonnegative states")
    # An identically zero process is admissible and absorbing. Mixed zeros need
    # a boundary-aware likelihood; they must not become artificial huge weights.
    if (v == 0).any() and not np.all(v == 0):
        raise ValueError("mixed zero/positive states require a boundary-aware fit")
    return v


def fit_cir(values, dt=1 / 252, fixed_theta=None):
    """Minimize the same conditional Gaussian Euler NLL as the calibration/yields/calibrate.py stage.

    Solve the two-variable weighted least-squares problem including its active
    boundaries, then profile sigma. At theta=0, mu is undefined, not enormous.
    theta_se is a local regression diagnostic, not a boundary confidence interval.
    Constant histories return a deterministic, unidentified process explicitly.
    dt is a scalar or one positive elapsed-year interval per transition.
    """
    v = _sample(values)
    intervals = transition_steps(dt, len(v) - 1)
    if fixed_theta is not None:
        positive_number(fixed_theta, "fixed_theta", allow_zero=True)
    if np.ptp(v) <= np.finfo(float).eps * max(float(np.max(v)), 1e-100) * 8:
        b = 0.0 if fixed_theta is None else float(fixed_theta)
        return CIRFit(b * v[-1], b, float(v[-1]), 0.0,
                      float("inf"), 0.0, True, True)
    scale = float(np.mean(v))
    x = v[:-1] / scale
    y = np.diff(v / scale) / intervals
    # Euler increment variance is sigma^2 * X * h. For derivative responses
    # Delta(X/scale)/h the WLS weights are h/x. Divide by the first interval
    # solely to preserve the fixed-step arithmetic and improve typical scaling.
    step_scale = float(intervals[0])
    w = (intervals / step_scale) / x
    xbar = float(np.average(x, weights=w))
    ybar = float(np.average(y, weights=w))
    sx = float(np.sum(w * (x - xbar) ** 2))
    mu_min = 1e-12  # relative to the mean state; only a positivity boundary

    def profile(b):
        intercept = max(ybar + b * xbar, b * mu_min)
        residual = y - intercept + b * x
        loss = float(np.sum(w * residual ** 2))
        return loss, intercept, b

    if fixed_theta is None:
        candidates = [profile(0.0)]
        if sx > 0:
            b = max(0.0, -float(np.sum(w * (x - xbar) * (y - ybar))) / sx)
            candidates.append(profile(b))
        # The optimum can lie on a=theta*mu_min, where intercept profiling is
        # constrained. Solve that edge as well, rather than clipping an OLS fit.
        z = mu_min - x
        edge = max(0.0, float(np.sum(w * z * y) / np.sum(w * z * z)))
        candidates.append(profile(edge))
        loss, intercept, b = min(candidates)
    else:
        loss, intercept, b = profile(float(fixed_theta))
    sigma2 = loss * step_scale * scale / len(x)
    if sigma2 <= 0 or not np.isfinite(sigma2):
        raise ValueError("nonconstant history has degenerate transition variance")
    variance = sigma2 * v[:-1] * intervals
    residual = np.diff(v) - (intercept * scale - b * v[:-1]) * intervals
    nll = .5 * float(np.sum(np.log(2 * np.pi * variance) + residual ** 2 / variance))
    se = np.sqrt(sigma2 / (scale * step_scale * sx)) if sx > 0 else float("inf")
    mu = intercept * scale / b if b > 0 else float("nan")
    return CIRFit(intercept * scale, b, mu, float(np.sqrt(sigma2)), float(se),
                  nll, bool(b < 1e-4 or b <= se))


def stabilize_panel(histories, maturities, dt=1 / 252, nll_budget=2.0,
                    fallback_theta=.25, prior_thetas=None):
    """Regularize weak fits using same-date tenor anchors or causal prior speeds.

    Healthy nodes remain unchanged. Interpolate log(theta) over log(maturity)
    using healthy nodes; with none, use the prior date or an explicit fallback.
    Move toward the target only within a per-series profiled NLL budget. This
    is regularization, not evidence that an unidentified parameter was recovered.
    """
    positive_number(nll_budget, "nll_budget", allow_zero=True)
    positive_number(fallback_theta, "fallback_theta")
    h = np.asarray(histories, dtype=float)
    tenors = np.asarray(maturities, dtype=float)
    if tenors.ndim != 1 or tenors.size == 0 or h.ndim != 2 or h.shape[1] != len(tenors):
        raise ValueError("history columns must match maturities")
    if (not np.isfinite(tenors).all() or (tenors <= 0).any() or
            len(np.unique(tenors)) != len(tenors)):
        raise ValueError("maturities must be distinct, finite and positive")
    if prior_thetas is not None:
        prior_thetas = np.asarray(prior_thetas, dtype=float)
        if prior_thetas.shape != tenors.shape or not np.isfinite(prior_thetas).all() or (prior_thetas <= 0).any():
            raise ValueError("prior_thetas must contain a positive speed per maturity")
    raw = [fit_cir(h[:, j], dt) for j in range(len(tenors))]
    anchors = sorted((j for j, f in enumerate(raw) if not f.weak), key=lambda j: tenors[j])
    healed, audit = [], []
    for j, original in enumerate(raw):
        target, source = original.theta, "unmodified"
        if original.weak:
            if anchors:
                target = float(np.exp(np.interp(
                    np.log(tenors[j]), np.log(tenors[anchors]),
                    np.log([raw[k].theta for k in anchors]))))
                source = "tenor_anchors"
            elif prior_thetas is not None:
                target, source = float(prior_thetas[j]), "previous_date"
            else:
                target, source = fallback_theta, "explicit_fallback"
        chosen = original
        if original.weak and target != original.theta:
            candidate = fit_cir(h[:, j], dt, fixed_theta=target)
            if candidate.nll - original.nll <= nll_budget:
                chosen = candidate
            else:
                # Profile SSE is convex in theta; the interval from the optimum
                # to the proposed anchor has a single admissible boundary.
                lower, upper = 0.0, 1.0
                for _ in range(45):
                    fraction = (lower + upper) / 2
                    trial = fit_cir(h[:, j], dt, fixed_theta=
                                    original.theta + fraction * (target - original.theta))
                    if trial.nll - original.nll <= nll_budget:
                        lower, chosen = fraction, trial
                    else:
                        upper = fraction
        # Preserve the identification warning after regularization.
        chosen = replace(chosen, weak=original.weak)
        healed.append(chosen)
        audit.append({"raw_theta": original.theta, "raw_mu": original.mu,
                      "raw_sigma": original.sigma, "raw_a": original.a,
                      "raw_nll": original.nll, "theta_se": original.theta_se,
                      "weak": original.weak, "deterministic": original.deterministic,
                      "target_theta": target, "anchor_source": source,
                      "regularized": chosen.theta != original.theta,
                      "nll_cost": max(0.0, chosen.nll - original.nll),
                      "usable": np.isfinite(chosen.mu) and chosen.theta > 0})
    return healed, audit


def _conditioned_array(values, name):
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError) as error:
        raise ValueError(name + " must contain finite real numeric values") from error
    if raw.dtype.kind not in "iuf":
        raise ValueError(name + " must contain real numbers, not strings or booleans")
    with np.errstate(over="ignore", invalid="ignore"):
        array = raw.astype(float, copy=False)
    if not np.isfinite(array).all():
        raise ValueError(name + " must remain finite in float64 precision")
    return array


def fit_conditioned_cir(values, diffusion_history, dt=1 / 252, fixed_theta=None):
    """Fit drift a-theta*Y with the ordered update's known conditional variance.

    For each transition t -> t+1, variance is A[t+1]**2 * Y[t] * h[t].
    Thus the supplied higher-layer history has the same length as Y and its
    right endpoints determine the weights. No constant sigma is estimated.
    The derivative regression weights are h/(A_right**2 * Y_left), including
    each actual elapsed interval. All drift constraint edges are evaluated.

    Mu has a relative positivity boundary at 1e-12 times the mean state. At
    theta=0, mu is undefined. Theta SE is a local regression-information
    diagnostic, not a boundary confidence interval. Zero states or nonpositive
    known transition variances require a boundary-aware likelihood and fail.
    """
    v = _conditioned_array(values, "conditioned state history")
    driver = _conditioned_array(diffusion_history, "diffusion history")
    if v.ndim != 1 or len(v) < 4 or (v < 0).any():
        raise ValueError("conditioned CIR history needs at least four nonnegative states")
    if driver.shape != v.shape or (driver < 0).any():
        raise ValueError("diffusion history must match states with nonnegative amplitudes")
    intervals = transition_steps(dt, len(v) - 1)
    if fixed_theta is not None:
        positive_number(fixed_theta, "fixed_theta", allow_zero=True)
    if (v == 0).any():
        raise ValueError("zero states require a boundary-aware conditioned fit")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        variance = driver[1:]**2 * v[:-1] * intervals
    if not np.isfinite(variance).all():
        raise ValueError("nonfinite known transition variance; inspect state, driver and time units")
    if (variance <= 0).any():
        raise ValueError("nonpositive known transition variance requires a boundary-aware conditioned fit")
    # Normalize both response and regressor by the same state scale, retaining
    # the exact inverse-variance weights for that normalized regression. This
    # preserves physical-unit likelihoods and regression information.
    scale = float(np.max(v))
    relative_mean = float(np.mean(v / scale))
    scale *= relative_mean
    x = v[:-1] / scale
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        y = np.diff(v / scale) / intervals
        w = scale * intervals / (driver[1:]**2 * x)
    if not np.isfinite(y).all() or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError("nonfinite conditioned regression weights; inspect numeric scale")
    xbar = float(np.average(x, weights=w))
    ybar = float(np.average(y, weights=w))
    sx = float(np.sum(w * (x - xbar)**2))
    mu_min = 1e-12

    def profile(theta):
        intercept = max(ybar + theta*xbar, theta*mu_min)
        loss = float(np.sum(w * (y - intercept + theta*x)**2))
        return loss, intercept, theta

    if fixed_theta is None:
        candidates = [profile(0.)]
        if sx > 0:
            theta = max(0., -float(np.sum(w*(x-xbar)*(y-ybar))) / sx)
            candidates.append(profile(theta))
        z = mu_min-x
        edge = max(0., float(np.sum(w*z*y) / np.sum(w*z*z)))
        candidates.append(profile(edge))
        _, intercept, theta = min(candidates)
    else:
        _, intercept, theta = profile(float(fixed_theta))
    a = intercept * scale
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        residual = np.diff(v) - (a-theta*v[:-1])*intervals
        nll = .5*float(np.sum(np.log(2*np.pi) + np.log(variance) + residual**2/variance))
    if not np.isfinite([a, theta, nll]).all():
        raise ValueError("nonfinite conditioned drift or likelihood; inspect numeric scale")
    se = 1 / np.sqrt(sx) if sx > 0 else float("inf")
    mu = a/theta if theta > 0 else float("nan")
    return DriftFit(float(a), float(theta), float(mu), float(se), nll,
                    bool(theta < 1e-4 or theta <= se))


def stabilize_conditioned_panel(histories, driver_histories, maturities,
                                dt=1 / 252, nll_budget=2., fallback_theta=.25,
                                prior_thetas=None):
    """Couple weak conditional drift fits within their known-variance NLL budget.

    Driver columns align exactly with each maturity's state history. Healthy
    tenor speeds, otherwise causal prior speeds or the explicit fallback,
    provide the same regularization targets as stabilize_panel. Reprofiling
    changes drift only; supplied diffusion histories and variances stay fixed.
    """
    positive_number(nll_budget, "nll_budget", allow_zero=True)
    positive_number(fallback_theta, "fallback_theta")
    h = _conditioned_array(histories, "conditioned histories")
    drivers = _conditioned_array(driver_histories, "driver histories")
    tenors = _conditioned_array(maturities, "maturities")
    if (h.ndim != 2 or drivers.shape != h.shape or tenors.ndim != 1
            or tenors.size == 0 or h.shape[1] != len(tenors)):
        raise ValueError("state and driver history columns must match maturities")
    if (tenors <= 0).any() or len(np.unique(tenors)) != len(tenors):
        raise ValueError("maturities must be distinct, finite and positive")
    if prior_thetas is not None:
        prior_thetas = _conditioned_array(prior_thetas, "prior_thetas")
        if prior_thetas.shape != tenors.shape or (prior_thetas <= 0).any():
            raise ValueError("prior_thetas must contain a positive speed per maturity")
    raw = [fit_conditioned_cir(h[:, j], drivers[:, j], dt) for j in range(len(tenors))]
    anchors = sorted((j for j, fit in enumerate(raw) if not fit.weak), key=lambda j: tenors[j])
    healed, audit = [], []
    for j, original in enumerate(raw):
        target, source = original.theta, "unmodified"
        if original.weak:
            if anchors:
                target = float(np.exp(np.interp(np.log(tenors[j]), np.log(tenors[anchors]),
                                                np.log([raw[k].theta for k in anchors]))))
                source = "tenor_anchors"
            elif prior_thetas is not None:
                target, source = float(prior_thetas[j]), "previous_date"
            else:
                target, source = fallback_theta, "explicit_fallback"
        chosen = original
        if original.weak and target != original.theta:
            candidate = fit_conditioned_cir(h[:, j], drivers[:, j], dt, fixed_theta=target)
            if candidate.nll-original.nll <= nll_budget:
                chosen = candidate
            else:
                lower, upper = 0., 1.
                for _ in range(45):
                    fraction = (lower+upper)/2
                    trial = fit_conditioned_cir(h[:, j], drivers[:, j], dt,
                                               fixed_theta=original.theta+fraction*(target-original.theta))
                    if trial.nll-original.nll <= nll_budget:
                        lower, chosen = fraction, trial
                    else:
                        upper = fraction
        chosen = replace(chosen, weak=original.weak)
        healed.append(chosen)
        audit.append({"raw_theta": original.theta, "raw_mu": original.mu,
                      "raw_a": original.a, "raw_nll": original.nll,
                      "theta_se": original.theta_se, "weak": original.weak,
                      "deterministic": original.deterministic,
                      "target_theta": target, "anchor_source": source,
                      "regularized": chosen.theta != original.theta,
                      "nll_cost": max(0., chosen.nll-original.nll),
                      "diffusion_source": "observed_right_endpoint_higher_layer",
                      "variance_source": "observed_right_endpoint_higher_layer",
                      "usable": np.isfinite(chosen.mu) and chosen.theta > 0})
    return healed, audit
