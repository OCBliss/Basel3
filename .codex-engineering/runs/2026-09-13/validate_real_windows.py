"""Reproduce the temporal repair on real FRED windows without altering data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
TEMP = EVIDENCE / "tmp"
TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEMP)
SOURCE = ROOT / "src/RWA/yield_calibration/calibrate.py"
BASE_REVISION = "269f9487975d03e93bdea3b869785258e4972da5"

spec = importlib.util.spec_from_file_location("rwa_current", SOURCE)
current = importlib.util.module_from_spec(spec)
spec.loader.exec_module(current)
baseline_source = subprocess.run(
    ["git", "show", BASE_REVISION + ":src/RWA/quasi-MLE-Euler.py"],
    cwd=str(ROOT), check=True, capture_output=True, text=True,
).stdout
baseline = {"__name__": "rwa_baseline", "__file__": str(SOURCE)}
exec(compile(baseline_source, str(SOURCE), "exec"), baseline)

summary = {"baseline_revision": BASE_REVISION, "window": current.WINDOW_SIZE,
           "dt": current.DT, "series": {}}
parameter_series = {key: [] for key in ("theta", "mu", "sigma")}

with tempfile.TemporaryDirectory(dir=str(TEMP)) as directory:
    fixture = Path(directory)
    for order in ("descending", "ascending"):
        (fixture / order / "FRED").mkdir(parents=True)
    for filename in current.CSV_FILES:
        path = ROOT / "RWA/FRED" / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        df = pd.read_csv(path)
        dgs = path.stem
        dates = pd.to_datetime(df.observation_date, errors="raise")
        assert dates.notna().all() and not dates.duplicated().any()
        assert dates.is_monotonic_decreasing
        cleaned = pd.to_numeric(df[dgs].iloc[::-1], errors="coerce").ffill()
        assert np.isfinite(cleaned).all() and (cleaned > 0).all()

        # Take the latest three full default-size windows, including an older
        # valid observation if the subset boundary falls on a missing quote.
        count = current.WINDOW_SIZE + 2
        while pd.isna(pd.to_numeric(df.iloc[count - 1][dgs], errors="coerce")):
            count += 1
        sample = df.iloc[:count]
        sample.to_csv(fixture / "descending/FRED" / filename, index=False)
        sample.iloc[::-1].to_csv(fixture / "ascending/FRED" / filename, index=False)
        results = {}
        for order in ("descending", "ascending"):
            current.RWA_DIR = str(fixture / order)
            current.OUTPUT_DIR = str(fixture / (order + "_output"))
            result = pd.read_csv(current.process_csv(filename), parse_dates=["observation_date"])
            results[order] = result.set_index("observation_date").sort_index()
        cols = [dgs, "yield_clean", "theta", "mu", "sigma"]
        pd.testing.assert_frame_equal(results["ascending"][cols], results["descending"][cols])
        assert results["ascending"].iloc[:current.WINDOW_SIZE - 1][
            ["theta", "mu", "sigma"]].isna().all().all()

        baseline["RWA_DIR"] = str(fixture / "descending")
        baseline["OUTPUT_DIR"] = str(fixture / "baseline_output")
        before = pd.read_csv(baseline["process_csv"](filename), parse_dates=["observation_date"])
        before = before.set_index("observation_date").sort_index()
        latest = results["ascending"].iloc[-1]
        old_latest = before.iloc[-1]
        fitted = results["ascending"].iloc[current.WINDOW_SIZE - 1:]
        for key in parameter_series:
            parameter_series[key].append(fitted[key].rename(key + dgs[3:] + "y"))
        summary["series"][dgs] = {
            "source_rows": len(df), "source_sha256": digest,
            "all_source_dates_valid_unique_descending": True,
            "all_causally_cleaned_yields_finite_positive": True,
            "sample_rows": len(sample), "attempted_windows": len(fitted),
            "successful_windows": int(fitted[["theta", "mu", "sigma"]].notna().all(axis=1).sum()),
            "input_order_invariance": True,
            "oldest_window_minus_one_rows_unestimated": True,
            "latest_date": str(results["ascending"].index[-1].date()),
            "latest_forward_parameters": {key: float(latest[key]) for key in ("theta", "mu", "sigma")},
            "latest_baseline_reverse_parameters": {key: float(old_latest[key]) for key in ("theta", "mu", "sigma")},
        }
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        summary["series"][dgs]["source_unchanged"] = True

    def load_module(name, filename):
        module_spec = importlib.util.spec_from_file_location(name, ROOT / "src/RWA" / filename)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module

    mu_repair = load_module("rwa_real_mu", "curve_repair/mu.py")
    theta_repair = load_module("rwa_real_theta", "curve_repair/theta.py")
    rebuild = load_module("rwa_real_rebuild", "parameter_rebuild/rebuild.py")
    curves = {key: pd.concat(series, axis=1) for key, series in parameter_series.items()}
    # Compare tenors on the same actual date, never by row number or by merging
    # their different latest dates. DGS20 has two additional source dates.
    common_date = pd.concat(list(curves.values()), axis=1).dropna().index.max()
    assert not pd.isna(common_date)
    repaired_paths = {}
    audits = {}
    for key, module in (("mu", mu_repair), ("theta", theta_repair)):
        row = curves[key].loc[common_date].copy()
        row["observation_date"] = str(common_date.date())
        repaired = module.repair_mu_row(row)
        print("NSS candidate", key, common_date, repaired.to_dict(), flush=True)
        # The actual theta extrapolation is negative at the short end. It must
        # now be explicitly rejected without changing the original estimates.
        assert bool(repaired["curve_fit_success"]) == (key == "mu")
        assert bool(repaired["curve_repair_performed"]) == (key == "mu")
        columns = [key + tenor + "y" for tenor in ("1", "2", "3", "5", "7", "10", "20", "30")]
        if key == "theta":
            pd.testing.assert_series_equal(row[columns], repaired[columns])
            assert "positive" in repaired["curve_fit_error"]
        assert np.isfinite(repaired[columns].astype(float)).all()
        assert (repaired[columns].astype(float) > 0).all()
        repaired_paths[key] = fixture / (key + "_repaired.csv")
        pd.DataFrame([repaired]).to_csv(repaired_paths[key], index=False)
        audits[key] = {"date": str(common_date.date()), "model": repaired["curve_model"],
                       "repair_accepted": bool(repaired["curve_repair_performed"]),
                       "rejection_reason": repaired["curve_fit_error"],
                       "anomaly_count": int(repaired["anomaly_count"]),
                       "repaired": {column: float(repaired[column]) for column in columns},
                       "rmse": (float(repaired["curve_fit_rmse"])
                                if pd.notna(repaired["curve_fit_rmse"]) else None)}
    sigma_path = fixture / "sigma_curve.csv"
    curves["sigma"].loc[[common_date]].to_csv(sigma_path)
    rebuild.DGS_RAW_DIR = str(fixture / "descending_output")
    rebuild.MLE_VOL_RAW_DIR = str(fixture / "rebuilt")
    rebuild.MU_REPAIRED_FILE = str(repaired_paths["mu"])
    rebuild.THETA_REPAIRED_FILE = str(repaired_paths["theta"])
    rebuild.SIGMA_CURVE_FILE = str(sigma_path)
    rebuild.main()
    for dgs_name, mapping in rebuild.MATURITY_MAP.items():
        rebuilt = pd.read_csv(fixture / "rebuilt" / (dgs_name + "_with_parameters.csv"),
                              parse_dates=["observation_date"]).set_index("observation_date")
        for key in ("mu", "theta"):
            np.testing.assert_allclose(rebuilt.loc[common_date, key], audits[key]["repaired"][mapping[key]],
                                       rtol=1e-12, atol=1e-12)
        assert rebuilt.index.is_monotonic_decreasing
    summary["actual_anomaly_path"] = audits
    summary["actual_anomaly_path"]["eight_rebuilt_files_date_aligned"] = True

(EVIDENCE / "real-windows.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
print(json.dumps(summary, indent=2, allow_nan=False))
