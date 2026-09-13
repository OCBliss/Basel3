"""Compare pathwise and frozen closures using saved real-data calibration.

All uncertainty intervals are conditional Monte Carlo resampling intervals;
no parameter-estimation, historical-vintage or economic-validity coverage is
claimed. No failed simulated paths are discarded. One failure stops this run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.RWA.data.yields.acquire import verify_snapshot
from src.RWA.models.parameter_hierarchy import workflow as model
from src.RWA.models.parameter_hierarchy import recursive

BASE = ROOT / "RWA/Experimental/HIERARCHY/2026-09-13-live"
SNAPSHOT = ROOT / "RWA/FRED/snapshots/2026-09-13-live"
PARAMETERS = ("mu", "theta", "sigma")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def energy_score(samples, actual):
    """Unbiased ensemble estimate of E||X-y|| - E||X-X'||/2; lower is better."""
    samples = np.asarray(samples, dtype=float)
    n = len(samples)
    if n < 2:
        raise ValueError("energy score needs at least two independent paths")
    distances = np.linalg.norm(samples[:, None] - samples[None, :], axis=-1)
    return float(np.linalg.norm(samples - actual, axis=-1).mean()
                 - distances.sum() / (2 * n * (n - 1)))


def js_distance(a, b, edges):
    """sqrt(equal-weight JS), natural logarithms; zero bins contribute zero."""
    p = np.histogram(a, bins=edges)[0].astype(float)
    q = np.histogram(b, bins=edges)[0].astype(float)
    if p.sum() != len(a) or q.sum() != len(b):
        raise ValueError("shared bins omitted a terminal sample")
    p /= p.sum()
    q /= q.sum()
    mixture = (p + q) / 2
    keep_p, keep_q = p > 0, q > 0
    divergence = .5 * (np.sum(p[keep_p] * np.log(p[keep_p] / mixture[keep_p]))
                       + np.sum(q[keep_q] * np.log(q[keep_q] / mixture[keep_q])))
    return float(np.sqrt(max(0., divergence)))


def bounds(values):
    return [float(x) for x in np.quantile(values, [.025, .975])]


def statistics(values):
    return {"mean": float(np.mean(values)), "sample_sd": float(np.std(values, ddof=1)),
            "mean_mc_standard_error": float(np.std(values, ddof=1) / np.sqrt(len(values))),
            "q05": float(np.quantile(values, .05)), "q50": float(np.quantile(values, .5)),
            "q95": float(np.quantile(values, .95))}


def paired_comparisons(terminals, tenors, replicates, seed, actual=None):
    rng = np.random.default_rng(seed)
    reference = terminals["frozen"]
    indices = rng.integers(len(reference), size=(replicates, len(reference)))
    rows, histogram_rows = [], []
    for maturity_index, tenor in enumerate(tenors):
        pooled = np.concatenate([array[:, maturity_index] for array in terminals.values()])
        low, high = float(pooled.min()), float(pooled.max())
        if low == high:
            low, high = low - 1e-9, high + 1e-9
        bins = {count: np.linspace(np.nextafter(low, -np.inf),
                                  np.nextafter(high, np.inf), count + 1)
                for count in (30, 50, 100)}
        a = reference[:, maturity_index]
        for name, values in terminals.items():
            b = values[:, maturity_index]
            row = {"maturity": int(tenor), "mode": name, **statistics(b)}
            if actual is not None:
                realized = float(actual[maturity_index])
                row.update(actual=realized, squared_error_of_mean=float((b.mean() - realized) ** 2),
                           inside_central90=bool(row["q05"] <= realized <= row["q95"]))
            if name != "frozen":
                row["mean_difference_from_frozen"] = float(b.mean() - a.mean())
                row["mean_difference_mc95"] = bounds(b[indices].mean(axis=1) - a[indices].mean(axis=1))
                row["sd_difference_from_frozen"] = float(np.std(b, ddof=1) - np.std(a, ddof=1))
                row["sd_difference_mc95"] = bounds(np.std(b[indices], axis=1, ddof=1)
                                                    - np.std(a[indices], axis=1, ddof=1))
                for quantile, label in ((.05, "q05"), (.5, "q50"), (.95, "q95")):
                    row[label + "_difference_from_frozen"] = float(np.quantile(b, quantile) - np.quantile(a, quantile))
                    row[label + "_difference_mc95"] = bounds(np.quantile(b[indices], quantile, axis=1)
                                                               - np.quantile(a[indices], quantile, axis=1))
                for count, edges in bins.items():
                    histogram_rows.append({"maturity": int(tenor), "mode": name, "bins": count,
                        "edges": edges.tolist(), "distance": js_distance(a, b, edges),
                        "distance_mc95": bounds([js_distance(a[index], b[index], edges) for index in indices]),
                        "reference_occupied_bins": int((np.histogram(a, edges)[0] > 0).sum()),
                        "comparison_occupied_bins": int((np.histogram(b, edges)[0] > 0).sum())})
            rows.append(row)
    scores = []
    if actual is not None:
        base_score = energy_score(reference, actual)
        for name, values in terminals.items():
            score = energy_score(values, actual)
            row = {"mode": name, "energy_score": score, "difference_from_frozen": score - base_score}
            if name != "frozen":
                row["difference_mc95"] = bounds([energy_score(values[index], actual)
                                                   - energy_score(reference[index], actual) for index in indices])
            scores.append(row)
    return {"marginal_statistics": rows, "jensen_shannon_distances": histogram_rows,
            "joint_energy_scores": scores}


def history_at_origin(yields, first, second, origin, window, dt, shrinkage):
    available = first.loc[first.observation_date <= origin].copy()
    available_second = second.loc[second.observation_date <= origin].copy()
    panels = model.parameter_panels(available)
    dates = panels["mu"].index[-window:]
    tenors = panels["mu"].columns.to_numpy()
    if len(dates) != window or dates[-1] != origin:
        raise ValueError("saved calibration lacks the requested trailing origin window")
    history = np.stack([yields.reindex(index=dates, columns=tenors).to_numpy()]
                       + [panels[p].reindex(index=dates, columns=tenors).to_numpy() for p in PARAMETERS], axis=1)
    initial, coefficients, correlation, factor, origin_audit = model.forecast_inputs(
        yields.loc[yields.index <= origin], available, available_second, window, dt, shrinkage)
    np.testing.assert_array_equal(history[-1], initial)
    if (history <= 0).any() or not np.isfinite(history).all():
        raise ValueError("empirical baseline history must have strictly positive finite states")
    return history, coefficients, factor, tenors, origin_audit


def audit_summary(audit):
    updates = audit["updates"]
    report = {key: value for key, value in audit.items() if key != "updates"}
    per_step = []
    for step in sorted(set(row["origin_step"] for row in updates)):
        rows = [row for row in updates if row["origin_step"] == step]
        signatures = {(row["coefficient_max_change_from_origin"],
                       row["correlation_max_change_from_origin"], row["xi_min"], row["xi_max"])
                      for row in rows}
        per_step.append({"origin_step": step, "path_records": len(rows),
                         "distinct_path_audit_signatures": len(signatures),
                         "coefficient_change_range": [min(row["coefficient_max_change_from_origin"] for row in rows),
                                                      max(row["coefficient_max_change_from_origin"] for row in rows)],
                         "correlation_change_range": [min(row["correlation_max_change_from_origin"] for row in rows),
                                                      max(row["correlation_max_change_from_origin"] for row in rows)]})
    report["per_step_path_variation"] = per_step
    report["maximum_diffusion_changes_by_branch"] = (np.max([row["parameter_diffusion_max_changes"] for row in updates], axis=0).tolist()
                                                       if updates else [0., 0., 0.])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(HERE / "empirical-01"))
    parser.add_argument("--paths", type=int, default=32)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--substeps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=83271)
    parser.add_argument("--bootstrap", type=int, default=200)
    parser.add_argument("--held-out-offset", type=int, default=20)
    args = parser.parse_args(argv)
    output = model.repository_path(args.output)
    if args.paths < 4 or args.bootstrap < 20 or args.steps < 2 or args.held_out_offset < args.steps:
        parser.error("need paths>=4, bootstrap>=20, steps>=2, and held-out offset>=steps")
    if output.exists():
        parser.error("output already exists; choose a new evidence directory")
    output.mkdir(parents=True)
    started = time.perf_counter()
    report = {"status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
              "settings": vars(args), "origins": [], "failures": [],
              "interpretation": [
                  "Compare adaptive finite closures; no infinite hierarchy or valuation claim.",
                  "Saved causal first/second calibrations are reused, not refitted on future data.",
                  "Held-out observations come from one current-revision snapshot, not historical vintages.",
                  "JSD uses shared bins and natural-log square-root convention; difference is not forecast skill.",
                  "32 paths with30/50/100 bins yields sparse histograms; sensitivity and independent frozen control are reported.",
                  "Bootstrap intervals are conditional Monte Carlo uncertainty only, not economic or calibration uncertainty.",
                  "Energy score uses joint Euclidean yield space in percentage points; lower is better at the single realized origin.",
                  "One held-out origin cannot establish predictive superiority.",
                  "Every path is retained; any engine failure aborts and is recorded."],
              "references": {
                  "jsd": "https://www.cise.ufl.edu/~anand/sp06/jensen-shannon.pdf",
                  "energy_score": "https://doi.org/10.1198/016214506000001437"}}
    save(output / "results.json", report)
    try:
        baseline_manifest = json.loads((BASE / "manifest.json").read_text())
        settings = baseline_manifest["settings"]
        provenance = verify_snapshot(SNAPSHOT / "snapshot.json", SNAPSHOT / "series")
        inputs = [BASE / "yield_parameters.csv", BASE / "parameter_dynamics.csv", BASE / "manifest.json",
                  SNAPSHOT / "snapshot.json", SNAPSHOT / "raw/fred.csv", *sorted((SNAPSHOT / "series").glob("DGS*.csv"))]
        hashes = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
        report.update(input_hashes=hashes, acquisition=provenance,
                      engine_sha256=digest(Path(recursive.__file__)), validation_sha256=digest(Path(__file__)))
        yields, _ = model.read_yield_panel(SNAPSHOT / "series")
        first = pd.read_csv(BASE / "yield_parameters.csv", parse_dates=["observation_date"])
        second = pd.read_csv(BASE / "parameter_dynamics.csv", parse_dates=["observation_date"])
        latest = first.observation_date.max()
        latest_index = yields.index.get_loc(latest)
        origins = [("latest", latest, None),
                   ("held_out", yields.index[latest_index - args.held_out_offset],
                    yields.iloc[latest_index - args.held_out_offset + args.steps].to_numpy())]
        for label, origin, actual in origins:
            print("Origin", label, str(origin.date()), flush=True)
            history, coefficients, factor, tenors, origin_audit = history_at_origin(
                yields, first, second, origin, settings["parameter_window"], settings["dt"], settings["shrinkage"])
            origin_report = {"label": label, "origin": str(origin.date()), "historical_window": len(history),
                             "maturities": tenors.tolist(), "origin_dependence": origin_audit, "runs": []}
            if actual is not None:
                origin_report["target_date"] = str(yields.index[latest_index - args.held_out_offset + args.steps].date())
            report["origins"].append(origin_report)
            terminals = {}
            for name, cadence, seed in (("frozen", 0, args.seed), ("cadence_1", 1, args.seed),
                                        ("cadence_5", 5, args.seed), ("frozen_independent", 0, args.seed + 491)):
                before = time.perf_counter()
                print("  Run", name, flush=True)
                samples, projections, audit = recursive.simulate_recursive(
                    history, coefficients, factor, tenors, paths=args.paths, steps=args.steps,
                    dt=settings["dt"], seed=seed, substeps=args.substeps, recalibrate_every=cadence,
                    nll_budget=settings["nll_budget"], fallback_theta=settings["fallback_theta"],
                    shrinkage=settings["shrinkage"])
                elapsed = time.perf_counter() - before
                if not np.isfinite(samples).all() or (samples <= 0).any() or projections.any():
                    raise ValueError(label + "/" + name + ": empirical run reached nonpositive/projected states")
                if name == "frozen":
                    reference, reference_hits = model.simulate(history[-1], coefficients, factor,
                        paths=args.paths, steps=args.steps, dt=settings["dt"], seed=seed, substeps=args.substeps)
                    np.testing.assert_array_equal(samples, reference)
                    np.testing.assert_array_equal(projections, reference_hits)
                    origin_report["frozen_exactly_matches_existing_simulator"] = True
                elif name.startswith("cadence"):
                    expected_updates = args.paths * len(range(cadence, args.steps, cadence))
                    if audit["recalibration_count"] != expected_updates:
                        raise AssertionError("missing path/origin recalibration audit")
                    if audit["max_nll_cost"] > settings["nll_budget"] + 1e-8:
                        raise AssertionError("recalibration exceeded likelihood budget")
                    np.testing.assert_array_equal(samples[:, :cadence + 1], reference[:, :cadence + 1])
                terminals[name] = samples[:, -1, 0].copy()
                np.savez_compressed(output / (label + "-" + name + ".npz"),
                                    states=samples, maturities=tenors, projections=projections)
                save(output / (label + "-" + name + "-audit.json"), audit)
                summary = audit_summary(audit)
                summary.update(mode=name, runtime_seconds=elapsed, output_array_bytes=samples.nbytes + projections.nbytes,
                               process_peak_rss_raw=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                               peak_rss_units="bytes on macOS; kilobytes on Linux; process high-water mark across modes")
                origin_report["runs"].append(summary)
                save(output / "results.json", report)
                print("  Complete", name, "seconds", round(elapsed, 3), "updates", audit["recalibration_count"], flush=True)
            origin_report.update(paired_comparisons(terminals, tenors, args.bootstrap, args.seed + 908,
                                                   actual=actual))
            save(output / "results.json", report)
        if hashes != {str(p.relative_to(ROOT)): digest(p) for p in inputs}:
            raise AssertionError("baseline source artifacts changed during validation")
        report.update(status="complete", input_hashes_unchanged=True,
                      total_runtime_seconds=time.perf_counter() - started)
        save(output / "results.json", report)
        print(json.dumps({"status": report["status"], "output": str(output),
                          "seconds": report["total_runtime_seconds"]}), flush=True)
    except BaseException as error:
        report["status"] = "failed"
        report["failures"].append({"type": type(error).__name__, "message": str(error),
                                    "traceback": traceback.format_exc(), "elapsed_seconds": time.perf_counter() - started})
        save(output / "results.json", report)
        raise


if __name__ == "__main__":
    main()
