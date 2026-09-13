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


def _sample(values, dt):
    positive_number(dt, "dt")
    v = np.asarray(values, dtype=float)
    if v.ndim != 1 or len(v) < 4 or not np.isfinite(v).all() or (v < 0).any():
        raise ValueError("CIR history needs at least four finite nonnegative states")
    # An identically zero process is admissible and absorbing. Mixed zeros need
    # a boundary-aware likelihood; they must not become artificial huge weights.
    if (v == 0).any() and not np.all(v == 0):
        raise ValueError("mixed zero/positive states require a boundary-aware fit")
    return v


def fit_cir(values, dt=1 / 252, fixed_theta=None):
    """Minimize the same conditional Gaussian Euler NLL as the yield_calibration/calibrate.py stage.

    Solve the two-variable weighted least-squares problem including its active
    boundaries, then profile sigma. At theta=0, mu is undefined, not enormous.
    theta_se is a local regression diagnostic, not a boundary confidence interval.
    Constant histories return a deterministic, unidentified process explicitly.
    """
    v = _sample(values, dt)
    if fixed_theta is not None:
        positive_number(fixed_theta, "fixed_theta", allow_zero=True)
    if np.ptp(v) <= np.finfo(float).eps * max(float(np.max(v)), 1e-100) * 8:
        b = 0.0 if fixed_theta is None else float(fixed_theta)
        return CIRFit(b * v[-1], b, float(v[-1]), 0.0,
                      float("inf"), 0.0, True, True)
    scale = float(np.mean(v))
    x = v[:-1] / scale
    y = np.diff(v / scale) / dt
    w = 1 / x
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
    sigma2 = loss * dt * scale / len(x)
    if sigma2 <= 0 or not np.isfinite(sigma2):
        raise ValueError("nonconstant history has degenerate transition variance")
    variance = sigma2 * v[:-1] * dt
    residual = np.diff(v) - (intercept * scale - b * v[:-1]) * dt
    nll = .5 * float(np.sum(np.log(2 * np.pi * variance) + residual ** 2 / variance))
    se = np.sqrt(sigma2 / (scale * dt * sx)) if sx > 0 else float("inf")
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


def innovation_correlation(residuals, shrinkage=.05):
    """Estimate a full joint correlation, shrink to identity, return its factor.

    Constant residual columns have zero off-diagonal correlation. Their diffusion
    coefficient remains zero; identity diagonal does not add noise to that state.
    """
    positive_number(shrinkage, "shrinkage")
    if shrinkage > 1:
        raise ValueError("shrinkage must be at most one")
    r = np.asarray(residuals, dtype=float)
    if r.ndim != 2 or r.shape[0] < 4 or r.shape[1] < 1 or not np.isfinite(r).all():
        raise ValueError("joint residuals need at least four finite aligned rows")
    centered = r - r.mean(axis=0)
    norms = np.linalg.norm(centered, axis=0)
    z = np.divide(centered, norms, out=np.zeros_like(centered), where=norms > 0)
    empirical = z.T @ z
    np.fill_diagonal(empirical, 1.)
    correlation = (1 - shrinkage) * empirical + shrinkage * np.eye(r.shape[1])
    correlation = (correlation + correlation.T) / 2
    factor = np.linalg.cholesky(correlation)
    return correlation, factor, {
        "observations": len(r), "shrinkage": shrinkage,
        "constant_columns": np.flatnonzero(norms == 0).tolist(),
        "min_eigenvalue": float(np.linalg.eigvalsh(correlation)[0]),
        "max_correlation_adjustment": float(np.max(np.abs(correlation - empirical)))}


def step_hierarchy(state, coefficients, normal_shocks, factor, dt):
    """One simultaneous left-point projected Euler step.

    State last axes: [X, mu, theta, sigma], maturity. Coefficients have axes
    [parameter(mu,theta,sigma), fitted(theta,mu,sigma), maturity]. Normal shocks
    have the state shape. All coefficients multiplying shocks use the old state.
    """
    positive_number(dt, "dt")
    s = np.asarray(state, dtype=float)
    c = np.asarray(coefficients, dtype=float)
    z = np.asarray(normal_shocks, dtype=float)
    if s.ndim < 2 or s.shape[-2] != 4 or s.shape[-1] < 1 or z.shape != s.shape:
        raise ValueError("state and shocks must have matching (...,4,maturity) shapes")
    d = s.shape[-1]
    if c.shape != (3, 3, d):
        raise ValueError("coefficient shape must be (3,3,maturity)")
    l = np.asarray(factor, dtype=float)
    if l.shape != (4 * d, 4 * d) or not np.isfinite(l).all():
        raise ValueError("joint factor must have shape (4*maturity,4*maturity)")
    if not np.allclose(np.diag(l @ l.T), 1., atol=1e-10):
        raise ValueError("factor must produce unit marginal shock variances")
    if not np.isfinite(s).all() or (s < 0).any() or not np.isfinite(c).all() or (c < 0).any() or not np.isfinite(z).all():
        raise ValueError("states/coefficients must be finite nonnegative and shocks finite")
    dw = (z.reshape(-1, 4 * d) @ l.T).reshape(s.shape) * np.sqrt(dt)
    drift = np.empty_like(s)
    diffusion = np.empty_like(s)
    drift[..., 0, :] = s[..., 2, :] * (s[..., 1, :] - s[..., 0, :])
    diffusion[..., 0, :] = s[..., 3, :] * np.sqrt(s[..., 0, :])
    drift[..., 1:, :] = c[:, 0, :] * (c[:, 1, :] - s[..., 1:, :])
    diffusion[..., 1:, :] = c[:, 2, :] * np.sqrt(s[..., 1:, :])
    unprojected = s + drift * dt + diffusion * dw
    if not np.isfinite(unprojected).all():
        raise ValueError("nonfinite simulated state; inspect calibration and step size")
    return np.maximum(unprojected, 0.), unprojected < 0
