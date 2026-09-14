"""Stream auditable, separate family covariances for one evolving trajectory.

Each actual Euler increment is an independently readable NPZ file. The archive
keeps one increment's arrays in memory; its checksum inventory is streamed as
JSON Lines. ``manifest.json`` marks successful completion and is written last.
The caller chooses the model's three family names and owns its output location.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np


MATRIX_NAMES = ("factor_covariance", "correlation", "cholesky",
                "brownian_covariance")
COEFFICIENT_NAMES = ("theta", "long_run_mean", "diffusion")
RTOL = 1e-10
ATOL = 1e-12


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value, name, positive=False):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " must be a finite year fraction")
    value = float(value)
    if not np.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(name + " must be " + ("positive" if positive else "nonnegative")
                         + " and finite")
    return value


def _array(value, shape, name):
    array = np.asarray(value)
    if array.dtype.kind not in "iuf":
        raise ValueError(name + " must contain real numeric values")
    array = array.astype(float, copy=False)
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(name + " must have finite values and shape " + str(shape))
    return array


def _symmetric_psd(array, name):
    if not np.allclose(array, array.swapaxes(-1, -2), rtol=RTOL, atol=ATOL):
        raise ValueError(name + " must be symmetric for every family")
    eigenvalues = np.linalg.eigvalsh((array + array.swapaxes(-1, -2)) / 2)
    scale = np.max(np.abs(array), axis=(-1, -2))
    if np.any(eigenvalues[:, 0] < -(ATOL + RTOL * scale)):
        raise ValueError(name + " must be positive semidefinite for every family")


class CovarianceArchive:
    """Write consecutive single-trajectory matrix records into a new directory.

    ``append(step, elapsed_years, dt, matrices, state_before, state_after)``
    accepts zero-based steps and start times in years. ``matrices`` contains
    MATRIX_NAMES, each shaped (3, maturity, maturity), optionally accompanied by
    both ``raw_correlation`` and scalar ``regularization``. State arrays and
    optional realized ``brownian_increments`` have shape (3, maturity).

    Source factor covariance, normalized correlation, its lower-triangular
    Cholesky factor, and Brownian increment covariance remain distinct records.
    The last two must satisfy L @ L.T = correlation and Q = dt * correlation.
    When raw correlation is included, it must normalize source covariance and
    the used correlation must equal (1-alpha)*raw_correlation + alpha*identity.
    Optional coefficients have axes (family, theta/long_run_mean/diffusion,
    maturity); calibration audits are stored as a JSON string without pickle.
    Optional standard normal shocks require matching Brownian increments and
    verify the exact transformation sqrt(dt)*L*Z used by the model.

    Call ``finish()`` only after successful model execution, or use the object
    as a context manager. Any failed append/finish or exceptional context exit
    prevents completion. Incomplete records are retained for investigation.
    """

    def __init__(self, directory, maturities, family_names):
        tenors = np.asarray(maturities, dtype=float)
        if (tenors.ndim != 1 or len(tenors) < 1 or not np.isfinite(tenors).all()
                or (tenors <= 0).any() or len(np.unique(tenors)) != len(tenors)):
            raise ValueError("maturities must be distinct positive finite numbers")
        names = tuple(family_names)
        if (len(names) != 3 or any(not isinstance(name, str) or not name.strip()
                                 or any(ord(character) < 32 for character in name)
                                 for name in names) or len(set(names)) != 3):
            raise ValueError("family_names must contain three distinct nonempty names")
        self.directory = Path(directory)
        self.maturities = tenors.copy()
        self.family_names = names
        self._count = 0
        self._start = None
        self._end = None
        self._failed = False
        self._manifest = None
        self._brownian_records = 0
        self._inventory_digest = hashlib.sha256()
        self.directory.mkdir(parents=True, exist_ok=False)

    def __enter__(self):
        self._open()
        return self

    def __exit__(self, exception_type, exception, traceback):
        if exception_type is not None:
            self._failed = True
            if self._manifest is not None:
                (self.directory / "manifest.json").unlink(missing_ok=True)
                self._manifest = None
        elif self._manifest is None:
            self.finish()
        return False

    def _open(self):
        if self._failed:
            raise ValueError("archive is incomplete after a previous failure")
        if self._manifest is not None:
            raise ValueError("archive is already complete")

    def _atomic(self, destination, write):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".pending-",
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                write(stream)
                stream.flush()
                os.fsync(stream.fileno())
            if destination.exists():
                raise ValueError("archive file already exists: " + destination.name)
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def append(self, step, elapsed_years, dt, matrices, state_before, state_after,
               brownian_increments=None, coefficients=None, calibration_audit=None,
               normal_shocks=None):
        """Validate and persist the matrices actually used in one increment."""
        self._open()
        try:
            if (isinstance(step, (bool, np.bool_)) or not isinstance(step, (int, np.integer))
                    or int(step) != self._count):
                raise ValueError("step must be the next consecutive zero-based integer")
            start = _number(elapsed_years, "elapsed_years")
            delta = _number(dt, "dt", positive=True)
            end = start + delta
            if not np.isfinite(end) or end <= start:
                raise ValueError("dt must produce a finite, advancing end time")
            if self._end is not None and not np.isclose(start, self._end, rtol=RTOL, atol=ATOL):
                raise ValueError("increment times must be contiguous without overlaps or gaps")
            optional = {"raw_correlation", "regularization"}
            keys = set(matrices)
            if keys not in (set(MATRIX_NAMES), set(MATRIX_NAMES) | optional):
                raise ValueError("matrices must contain " + ", ".join(MATRIX_NAMES)
                                 + "; optional raw_correlation and regularization must appear together")
            d = len(self.maturities)
            arrays = {name: _array(matrices[name], (3, d, d), name) for name in MATRIX_NAMES}
            for name in ("factor_covariance", "correlation", "brownian_covariance"):
                _symmetric_psd(arrays[name], name)
            correlation, factor = arrays["correlation"], arrays["cholesky"]
            if not np.allclose(np.diagonal(correlation, axis1=-2, axis2=-1), 1., rtol=RTOL, atol=ATOL):
                raise ValueError("correlation must have unit diagonal for every family")
            if (not np.allclose(factor, np.tril(factor), rtol=RTOL, atol=ATOL)
                    or (np.diagonal(factor, axis1=-2, axis2=-1) < 0).any()):
                raise ValueError("cholesky must be lower triangular with nonnegative diagonal")
            if not np.allclose(factor @ factor.swapaxes(-1, -2), correlation, rtol=RTOL, atol=ATOL):
                raise ValueError("cholesky @ cholesky.T must equal correlation")
            if not np.allclose(arrays["brownian_covariance"], delta * correlation, rtol=RTOL, atol=ATOL):
                raise ValueError("brownian_covariance must equal dt * correlation")
            if optional.issubset(keys):
                raw = _array(matrices["raw_correlation"], (3, d, d), "raw_correlation")
                alpha = _number(matrices["regularization"], "regularization")
                if alpha > 1:
                    raise ValueError("regularization must be between zero and one")
                _symmetric_psd(raw, "raw_correlation")
                variances = np.diagonal(arrays["factor_covariance"], axis1=-2, axis2=-1)
                if (variances <= 0).any():
                    raise ValueError("raw_correlation requires positive factor covariance variances")
                deviations = np.sqrt(variances)
                normalized = arrays["factor_covariance"] / deviations[:, :, None] / deviations[:, None, :]
                if not np.allclose(raw, normalized, rtol=RTOL, atol=ATOL):
                    raise ValueError("raw_correlation must normalize factor_covariance")
                if not np.allclose(correlation, (1-alpha)*raw + alpha*np.eye(d), rtol=RTOL, atol=ATOL):
                    raise ValueError("correlation must match raw_correlation and regularization")
                arrays.update(raw_correlation=raw, regularization=np.float64(alpha))
            arrays.update(state_before=_array(state_before, (3, d), "state_before"),
                          state_after=_array(state_after, (3, d), "state_after"))
            if brownian_increments is not None:
                arrays["brownian_increments"] = _array(brownian_increments, (3, d), "brownian_increments")
            if normal_shocks is not None:
                if brownian_increments is None:
                    raise ValueError("normal_shocks require the realized brownian_increments")
                normals = _array(normal_shocks, (3, d), "normal_shocks")
                transformed = np.einsum("fij,fj->fi", factor, normals) * np.sqrt(delta)
                if not np.allclose(transformed, arrays["brownian_increments"], rtol=RTOL, atol=ATOL):
                    raise ValueError("brownian_increments must equal sqrt(dt) * cholesky * normal_shocks")
                arrays["normal_shocks"] = normals
            if coefficients is not None:
                fitted = _array(coefficients, (3, 3, d), "coefficients")
                if (fitted < 0).any():
                    raise ValueError("coefficients must be nonnegative")
                arrays.update(coefficients=fitted, coefficient_names=np.array(COEFFICIENT_NAMES))
            if calibration_audit is not None:
                arrays["calibration_audit"] = np.array(json.dumps(calibration_audit, allow_nan=False))
            arrays.update(step=np.int64(step), elapsed_years=np.float64(start),
                          elapsed_end_years=np.float64(end), dt_years=np.float64(delta),
                          maturities=self.maturities, family_names=np.array(self.family_names))
            filename = "step_%06d.npz" % step
            destination = self.directory / filename
            self._atomic(destination, lambda stream: np.savez_compressed(stream, **arrays))
            record = {"step": int(step), "file": filename, "sha256": _digest(destination),
                      "elapsed_years": start, "elapsed_end_years": end, "dt_years": delta}
            payload = (json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n").encode()
            with (self.directory / "index.jsonl").open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._inventory_digest.update(payload)
            self._start = start if self._start is None else self._start
            self._end = end
            self._count += 1
            self._brownian_records += int(brownian_increments is not None)
        except Exception:
            self._failed = True
            raise

    def finish(self):
        """Verify the streamed inventory and publish the completion manifest."""
        if self._manifest is not None:
            return json.loads(json.dumps(self._manifest))
        self._open()
        try:
            if self._count == 0:
                raise ValueError("cannot complete an archive without increments")
            inventory = self.directory / "index.jsonl"
            digest = _digest(inventory)
            if digest != self._inventory_digest.hexdigest():
                raise ValueError("archive inventory changed before completion")
            count = 0
            with inventory.open() as stream:
                for count, line in enumerate(stream, start=1):
                    record = json.loads(line)
                    if _digest(self.directory / record["file"]) != record["sha256"]:
                        raise ValueError("archive record changed before completion: " + record["file"])
            if count != self._count:
                raise ValueError("archive inventory count does not match written increments")
            manifest = {"schema_version": 1, "status": "complete", "increments": self._count,
                        "family_names": list(self.family_names), "maturities": self.maturities.tolist(),
                        "matrix_names": list(MATRIX_NAMES),
                        "matrix_axes": ["family", "maturity_row", "maturity_column"],
                        "state_axes": ["family", "maturity"],
                        "coefficient_axes": ["family", "coefficient", "maturity"],
                        "coefficient_names": list(COEFFICIENT_NAMES),
                        "elapsed_start_years": self._start, "elapsed_end_years": self._end,
                        "brownian_increment_records": self._brownian_records,
                        "inventory": {"file": "index.jsonl", "sha256": digest, "records": self._count}}
            payload = (json.dumps(manifest, indent=2, allow_nan=False) + "\n").encode()
            self._atomic(self.directory / "manifest.json", lambda stream: stream.write(payload))
            self._manifest = manifest
            return json.loads(json.dumps(manifest))
        except Exception:
            self._failed = True
            raise
