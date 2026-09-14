"""Separate rolling level dependence for three maturity-indexed families.

The family axis is deliberately uninterpreted here: callers must supply the
three processes required by their model. Each family has its own sample level
covariance and normalized correlation (PDF equation 2.4). No cross-family
correlation is estimated or introduced by the Brownian transformation.
"""

import numpy as np


def _finite_array(values, name):
    """Accept real numeric arrays without coercing strings, objects or booleans."""
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError) as error:
        raise ValueError(name + " must be a finite real numeric array") from error
    if raw.dtype.kind not in "iuf":
        raise ValueError(name + " must contain real numeric values, not strings or booleans")
    with np.errstate(over="ignore", invalid="ignore"):
        result = raw.astype(float, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(name + " must remain finite in float64 precision")
    return result


def _scalar(value, name, minimum, maximum=None, strict_minimum=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be a finite real number")
    try:
        value = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(name + " must remain finite in float64 precision") from error
    if (not np.isfinite(value) or value < minimum
            or (strict_minimum and value == minimum)
            or (maximum is not None and value > maximum)):
        raise ValueError(name + " is outside its permitted range")
    return value


def family_covariances(history, dt, regularization=0.0):
    """Estimate three separate covariance/correlation/factor matrix families.

    ``history`` is (observations, 3, maturities), with at least two observations.
    ``factor_covariance`` contains sample LEVEL covariances with divisor n-1;
    it is never shrunk. ``raw_correlation`` normalizes those covariances.
    ``correlation`` is the matrix actually factored, ``cholesky`` contains its
    lower-triangular factors, and ``brownian_covariance`` is dt*correlation.
    Each matrix field has shape (3, maturities, maturities), never a pooled
    matrix. Brownian covariance does not include an SDE's diffusion multipliers.

    Default regularization=0 preserves empirical correlation and rejects
    numerically rank-deficient histories. Explicit alpha in (0,1] instead uses
    (1-alpha)*raw_correlation + alpha*I; the returned alpha records that change.
    Zero-variance columns always fail because their normalized correlation is
    undefined. Regularization cannot silently manufacture their variance.
    """
    step = _scalar(dt, "dt", 0., strict_minimum=True)
    alpha = _scalar(regularization, "regularization", 0., maximum=1.)
    values = _finite_array(history, "history")
    if values.ndim != 3 or values.shape[0] < 2 or values.shape[1] != 3 or values.shape[2] < 1:
        raise ValueError("history must have shape (at least 2 observations, 3 families, maturities)")
    observations, _, dimensions = values.shape
    covariance = np.empty((3, dimensions, dimensions))
    raw_correlation = np.empty_like(covariance)
    correlation = np.empty_like(covariance)
    factors = np.empty_like(covariance)
    identity = np.eye(dimensions)
    for family in range(3):
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            centered = values[:, family] - values[:, family].mean(axis=0)
            matrix = centered.T @ centered / (observations - 1)
        if not np.isfinite(matrix).all():
            raise ValueError("family %d: level covariance is nonfinite; inspect numeric scale" % family)
        variances = np.diag(matrix)
        constant = np.flatnonzero((variances <= 0.)
                                  | np.all(values[:, family] == values[0, family], axis=0))
        if len(constant):
            raise ValueError("family %d: zero-variance maturity columns %s have undefined correlation"
                             % (family, constant.tolist()))
        deviations = np.sqrt(variances)
        empirical = matrix / deviations[:, None] / deviations[None, :]
        if not np.isfinite(empirical).all():
            raise ValueError("family %d: normalized level correlation is nonfinite" % family)
        # Normalization gives unit diagonals analytically; assign them exactly
        # to avoid changing Brownian marginal variance through roundoff.
        np.fill_diagonal(empirical, 1.)
        if alpha == 0. and np.linalg.matrix_rank(centered / deviations) < dimensions:
            raise ValueError("family %d: level correlation is rank deficient; use more independent history"
                             " or explicitly request regularization" % family)
        used = (1. - alpha) * empirical + alpha * identity
        try:
            factor = np.linalg.cholesky(used)
        except np.linalg.LinAlgError as error:
            raise ValueError("family %d: level correlation is not positive definite;"
                             " inspect history or explicitly request regularization" % family) from error
        covariance[family] = matrix
        raw_correlation[family] = empirical
        correlation[family] = used
        factors[family] = factor
    with np.errstate(over="ignore", invalid="ignore"):
        brownian_covariance = step * correlation
    if not np.isfinite(brownian_covariance).all():
        raise ValueError("dt produces nonfinite Brownian increment covariance")
    return {"factor_covariance": covariance, "raw_correlation": raw_correlation,
            "correlation": correlation, "cholesky": factors,
            "brownian_covariance": brownian_covariance, "regularization": alpha}


def brownian_increments(normal_shocks, cholesky, dt):
    """Apply one separate family factor to independent standard normal draws.

    Draws have shape (3,maturities), factors (3,maturities,maturities).
    Returns sqrt(dt)*L_family*Z_family (PDF equation 2.10). Independence across
    families is preserved when supplied normals are independent; this function
    does not draw, reuse, or mix random values between families.
    """
    step = _scalar(dt, "dt", 0., strict_minimum=True)
    draws = _finite_array(normal_shocks, "normal_shocks")
    factors = _finite_array(cholesky, "cholesky")
    if draws.ndim != 2 or draws.shape[0] != 3 or draws.shape[1] < 1:
        raise ValueError("normal_shocks must have shape (3,maturities) for one increment")
    dimensions = draws.shape[-1]
    if factors.shape != (3, dimensions, dimensions):
        raise ValueError("cholesky must have three separate (maturities,maturities) factors")
    if np.any(np.triu(factors, 1) != 0.) or np.any(np.diagonal(factors, axis1=1, axis2=2) <= 0.):
        raise ValueError("cholesky factors must be lower triangular with positive diagonals")
    with np.errstate(over="ignore", invalid="ignore"):
        marginal_variances = np.sum(factors * factors, axis=2)
    if not np.allclose(marginal_variances, 1., rtol=1e-12, atol=1e-12):
        raise ValueError("cholesky factors must produce unit marginal Brownian variances")
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.einsum("fij,fj->fi", factors, draws) * np.sqrt(step)
    if not np.isfinite(result).all():
        raise ValueError("nonfinite Brownian increments; inspect draws and timestep")
    return result
