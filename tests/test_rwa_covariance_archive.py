"""Deterministic matrix identities, streaming records and completion integrity."""

import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
module = importlib.import_module("src.RWA.models.parameter_hierarchy.covariance_archive")
CovarianceArchive = module.CovarianceArchive


def matrices(dt=.125):
    """Three distinguishable two-tenor matrices with known triangular factors."""
    rho = np.array([.2, -.4, .6])
    correlation = np.array([[[1., value], [value, 1.]] for value in rho])
    factor = np.array([[[1., 0.], [value, np.sqrt(1-value**2)]] for value in rho])
    scales = np.array([[2., 3.], [4., 5.], [6., 7.]])
    covariance = scales[:, :, None] * correlation * scales[:, None, :]
    return dict(factor_covariance=covariance, correlation=correlation,
                cholesky=factor, brownian_covariance=dt*correlation)


class CovarianceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.before = np.arange(6, dtype=float).reshape(3, 2) + 1
        self.after = self.before + .25

    def writer(self, name="archive", **kwargs):
        settings = dict(maturities=[1, 10], family_names=["X", "nu", "xi"])
        settings.update(kwargs)
        return CovarianceArchive(self.root / name, **settings)

    def append(self, writer, step=0, elapsed_years=0., dt=.125, values=None, **kwargs):
        writer.append(step, elapsed_years, dt, matrices(dt) if values is None else values,
                      self.before, self.after, **kwargs)

    def test_records_preserve_distinct_matrices_axes_states_and_realized_increments(self):
        writer = self.writer()
        expected = matrices()
        brownian = np.array([[.1, .2], [.3, .4], [.5, .6]])
        self.append(writer, values=expected, brownian_increments=brownian)
        self.assertFalse((writer.directory / "manifest.json").exists())
        with np.load(writer.directory / "step_000000.npz", allow_pickle=False) as record:
            self.assertEqual(record["family_names"].tolist(), ["X", "nu", "xi"])
            self.assertEqual(record["maturities"].tolist(), [1., 10.])
            self.assertEqual(record["step"].item(), 0)
            self.assertEqual(record["elapsed_years"].item(), 0.)
            self.assertEqual(record["elapsed_end_years"].item(), .125)
            self.assertEqual(record["dt_years"].item(), .125)
            for name, array in expected.items():
                self.assertEqual(record[name].shape, (3, 2, 2))
                np.testing.assert_array_equal(record[name], array)
            np.testing.assert_array_equal(record["state_before"], self.before)
            np.testing.assert_array_equal(record["state_after"], self.after)
            np.testing.assert_array_equal(record["brownian_increments"], brownian)
        manifest = writer.finish()
        self.assertEqual(manifest["matrix_axes"], ["family", "maturity_row", "maturity_column"])
        self.assertEqual(manifest["state_axes"], ["family", "maturity"])
        self.assertEqual(manifest["brownian_increment_records"], 1)
        self.assertEqual(manifest["increments"], 1)

    def test_inventory_checksums_and_completion_are_independently_verifiable(self):
        with self.writer() as writer:
            self.append(writer)
            self.append(writer, step=1, elapsed_years=.125, dt=.25)
        manifest = json.loads((writer.directory / "manifest.json").read_text())
        inventory = writer.directory / manifest["inventory"]["file"]
        self.assertEqual(hashlib.sha256(inventory.read_bytes()).hexdigest(), manifest["inventory"]["sha256"])
        lines = [json.loads(line) for line in inventory.read_text().splitlines()]
        self.assertEqual([row["step"] for row in lines], [0, 1])
        for row in lines:
            actual = hashlib.sha256((writer.directory / row["file"]).read_bytes()).hexdigest()
            self.assertEqual(actual, row["sha256"])
        self.assertEqual(manifest["elapsed_end_years"], .375)
        self.assertEqual(manifest["inventory"]["records"], 2)
        self.assertEqual(writer.finish(), manifest)
        manifest["family_names"][0] = "changed"
        self.assertEqual(writer.finish()["family_names"][0], "X")
        with self.assertRaisesRegex(ValueError, "already complete"):
            self.append(writer, step=2, elapsed_years=.375)

    def test_refit_audit_and_fixed_shocks_are_saved_for_exact_replay(self):
        writer = self.writer()
        values = matrices()
        raw = values["correlation"].copy()
        alpha = .25
        values["correlation"] = (1-alpha)*raw + alpha*np.eye(2)
        rho = values["correlation"][:, 1, 0]
        values["cholesky"] = np.array([[[1., 0.], [r, np.sqrt(1-r*r)]] for r in rho])
        values["brownian_covariance"] = .125*values["correlation"]
        values.update(raw_correlation=raw, regularization=alpha)
        normals = np.arange(6, dtype=float).reshape(3, 2) / 8
        increments = np.array([np.sqrt(.125)*factor.dot(z)
                               for factor, z in zip(values["cholesky"], normals)])
        coefficients = np.arange(18, dtype=float).reshape(3, 3, 2) / 4
        audit = {"families": [[{"weak": True, "raw_mu": None,
                                "undefined_numeric_fields": ["raw_mu"]}]]}
        self.append(writer, values=values, coefficients=coefficients,
                    calibration_audit=audit, normal_shocks=normals,
                    brownian_increments=increments)
        with np.load(writer.directory / "step_000000.npz", allow_pickle=False) as record:
            np.testing.assert_array_equal(record["raw_correlation"], raw)
            np.testing.assert_array_equal(record["coefficients"], coefficients)
            np.testing.assert_array_equal(record["normal_shocks"], normals)
            np.testing.assert_array_equal(record["brownian_increments"], increments)
            self.assertEqual(record["regularization"].item(), alpha)
            self.assertEqual(record["coefficient_names"].tolist(), ["theta", "long_run_mean", "diffusion"])
            self.assertEqual(json.loads(record["calibration_audit"].item()), audit)
        writer.finish()

    def test_optional_correlation_metadata_cannot_misstate_normalization_or_shrinkage(self):
        invalid = []
        wrong = matrices(); wrong["raw_correlation"] = wrong["correlation"].copy(); invalid.append(wrong)
        wrong = matrices(); wrong["regularization"] = .1; invalid.append(wrong)
        wrong = matrices(); wrong.update(raw_correlation=wrong["correlation"], regularization=1.1); invalid.append(wrong)
        wrong = matrices(); wrong.update(raw_correlation=wrong["correlation"]*.8, regularization=0.); invalid.append(wrong)
        wrong = matrices(); wrong.update(raw_correlation=wrong["correlation"], regularization=.5); invalid.append(wrong)
        for index, values in enumerate(invalid):
            writer = self.writer(str(index))
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.append(writer, values=values)

    def test_optional_coefficients_audits_and_draws_reject_invalid_replay_evidence(self):
        cases = [dict(coefficients=np.full((3, 3, 2), -1.)),
                 dict(coefficients=np.ones((3, 2))),
                 dict(coefficients=np.ones((3, 3, 2), dtype=bool)),
                 dict(calibration_audit={"nll": np.nan}),
                 dict(normal_shocks=np.ones((3, 2))),
                 dict(normal_shocks=np.ones((3, 2)), brownian_increments=np.zeros((3, 2)))]
        for index, kwargs in enumerate(cases):
            writer = self.writer(str(index))
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.append(writer, **kwargs)
            self.assertFalse(list(writer.directory.glob("step_*.npz")))

    def test_actual_covariance_helper_eight_tenor_output_round_trips_without_pooling(self):
        covariance = importlib.import_module("src.RWA.models.parameter_hierarchy.covariance")
        clock = np.arange(40)[:, None]
        frequencies = np.arange(1, 9)[None, :]
        observed = np.stack([2 + np.sin(clock*frequencies/9 + phase)
                             for phase in (0., .2, .7)], axis=1)
        values = covariance.family_covariances(observed, 1/252)
        writer = self.writer(maturities=[1, 2, 3, 5, 7, 10, 20, 30])
        normals = np.arange(24).reshape(3, 8) / 24
        increments = covariance.brownian_increments(normals, values["cholesky"], 1/252)
        writer.append(0, 0., 1/252, values, observed[-1], observed[-1]+.01,
                      brownian_increments=increments, normal_shocks=normals)
        writer.finish()
        with np.load(writer.directory / "step_000000.npz") as record:
            for name in module.MATRIX_NAMES:
                self.assertEqual(record[name].shape, (3, 8, 8))
            np.testing.assert_array_equal(record["brownian_increments"], increments)

    def test_streaming_retains_no_record_arrays_or_growing_in_memory_inventory(self):
        writer = self.writer()
        values = matrices()
        self.append(writer, values=values)
        values["factor_covariance"][:] = 0.
        for step in range(1, 24):
            self.append(writer, step=step, elapsed_years=step / 8)
        self.assertEqual(len(list(writer.directory.glob("step_*.npz"))), 24)
        retained = [value for value in vars(writer).values() if isinstance(value, np.ndarray)]
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].shape, (2,))  # immutable output-axis metadata
        self.assertFalse(any(isinstance(value, list) for value in vars(writer).values()))
        with np.load(writer.directory / "step_000000.npz") as first:
            np.testing.assert_array_equal(first["factor_covariance"], matrices()["factor_covariance"])
        self.assertEqual(writer.finish()["increments"], 24)

    def test_invalid_family_maturity_metadata_and_existing_directory_fail(self):
        invalid = [dict(family_names=["X", "nu"]), dict(family_names=["X", "X", "xi"]),
                   dict(family_names=["X", "nu", ""]), dict(family_names=["X", "nu", "xi\n"]),
                   dict(maturities=[]), dict(maturities=[1, 1]), dict(maturities=[0, 2]),
                   dict(maturities=[1, np.nan])]
        for index, settings in enumerate(invalid):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.writer(str(index), **settings)
            self.assertFalse((self.root / str(index)).exists())
        self.writer()
        with self.assertRaises(FileExistsError):
            self.writer()

    def test_step_and_clock_errors_prevent_completion(self):
        invalid = [dict(step=1), dict(step=True), dict(step=.0), dict(dt=0.),
                   dict(dt=-1.), dict(dt=np.inf), dict(elapsed_years=-1.),
                   dict(elapsed_years=np.nan), dict(elapsed_years=True)]
        for index, settings in enumerate(invalid):
            writer = self.writer(str(index))
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.append(writer, **settings)
            with self.assertRaisesRegex(ValueError, "previous failure"):
                writer.finish()
            self.assertFalse((writer.directory / "manifest.json").exists())
        for index, start in enumerate([.124, .126]):
            writer = self.writer("gap%d" % index)
            self.append(writer)
            with self.assertRaisesRegex(ValueError, "contiguous"):
                self.append(writer, step=1, elapsed_years=start)

    def test_matrix_contract_rejects_pooled_dimensions_wrong_semantics_and_nonfinite_values(self):
        variants = []
        wrong = matrices(); wrong["correlation"] = np.eye(6); variants.append(wrong)
        wrong = matrices(); wrong["factor_covariance"][0, 0, 1] += 1.; variants.append(wrong)
        wrong = matrices(); wrong["factor_covariance"][0] = [[1., 2.], [2., 1.]]; variants.append(wrong)
        wrong = matrices(); wrong["correlation"][0, 0, 0] = 2.; variants.append(wrong)
        wrong = matrices(); wrong["cholesky"][0, 0, 1] = .1; variants.append(wrong)
        wrong = matrices(); wrong["cholesky"][0] *= -1.; variants.append(wrong)
        wrong = matrices(); wrong["cholesky"][0, 1, 0] += .1; variants.append(wrong)
        wrong = matrices(); wrong["brownian_covariance"] *= 2.; variants.append(wrong)
        wrong = matrices(); wrong["factor_covariance"][0, 0, 0] = np.nan; variants.append(wrong)
        wrong = matrices(); wrong["pooled_covariance"] = np.eye(6); variants.append(wrong)
        for index, values in enumerate(variants):
            writer = self.writer(str(index))
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.append(writer, values=values)
            self.assertFalse(list(writer.directory.glob("step_*.npz")))
            self.assertFalse((writer.directory / "manifest.json").exists())

    def test_state_and_realized_increment_shapes_have_no_ensemble_axis(self):
        for index, invalid in enumerate([np.ones((1, 3, 2)), np.ones((3, 3)), np.full((3, 2), np.nan)]):
            writer = self.writer(str(index))
            with self.assertRaisesRegex(ValueError, "brownian_increments"):
                self.append(writer, brownian_increments=invalid)
        writer = self.writer("bad-state")
        with self.assertRaisesRegex(ValueError, "state_before"):
            writer.append(0, 0., .125, matrices(), np.ones((2, 3, 2)), self.after)

    def test_interrupted_record_write_is_atomic_and_never_marks_completion(self):
        writer = self.writer()

        def fail(stream, **arrays):
            stream.write(b"incomplete NPZ")
            raise OSError("disk unavailable")

        with mock.patch.object(module.np, "savez_compressed", side_effect=fail):
            with self.assertRaisesRegex(OSError, "disk unavailable"):
                self.append(writer)
        self.assertEqual(list(writer.directory.iterdir()), [])
        with self.assertRaisesRegex(ValueError, "previous failure"):
            writer.finish()

    def test_context_failure_preserves_records_without_completion_marker(self):
        writer = self.writer()
        with self.assertRaisesRegex(RuntimeError, "model failed"):
            with writer:
                self.append(writer)
                raise RuntimeError("model failed")
        self.assertTrue((writer.directory / "step_000000.npz").exists())
        self.assertFalse((writer.directory / "manifest.json").exists())
        with self.assertRaisesRegex(ValueError, "previous failure"):
            writer.finish()

    def test_exception_after_early_finish_within_context_removes_completion_marker(self):
        writer = self.writer()
        with self.assertRaisesRegex(RuntimeError, "later failure"):
            with writer:
                self.append(writer)
                writer.finish()
                raise RuntimeError("later failure")
        self.assertFalse((writer.directory / "manifest.json").exists())
        with self.assertRaisesRegex(ValueError, "previous failure"):
            writer.finish()

    def test_changed_step_or_inventory_is_detected_before_completion(self):
        for index, filename in enumerate(["step_000000.npz", "index.jsonl"]):
            writer = self.writer(str(index))
            self.append(writer)
            with (writer.directory / filename).open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "changed before completion"):
                writer.finish()
            self.assertFalse((writer.directory / "manifest.json").exists())

    def test_empty_archive_and_failed_manifest_write_cannot_appear_complete(self):
        empty = self.writer("empty")
        with self.assertRaisesRegex(ValueError, "without increments"):
            empty.finish()
        writer = self.writer()
        self.append(writer)
        with mock.patch.object(module.os, "replace", side_effect=OSError("manifest unavailable")):
            with self.assertRaisesRegex(OSError, "manifest unavailable"):
                writer.finish()
        self.assertFalse((writer.directory / "manifest.json").exists())
        self.assertFalse(list(writer.directory.glob(".pending-*")))


if __name__ == "__main__":
    unittest.main()
