#!/usr/bin/env python3
"""Download, validate and preserve a FRED Treasury yield snapshot."""

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[4]
TENORS = (1, 2, 3, 5, 7, 10, 20, 30)
ENDPOINT = "https://fred.stlouisfed.org/graph/fredgraph.csv"
MAX_BYTES = 8 * 1024 * 1024


def repository_path(value):
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        raise ValueError("yield paths must remain inside the repository")
    return path


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name + " must be an integer >= " + str(minimum))
    return value


def _date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("dates must use YYYY-MM-DD")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("dates must use YYYY-MM-DD")
    return result


def _settings(maturities, start, end, max_fill_days, max_age_days):
    maturities = tuple(maturities)
    if (not maturities or len(set(maturities)) != len(maturities)
            or any(isinstance(n, bool) or not isinstance(n, int) or n not in TENORS
                   for n in maturities)):
        raise ValueError("maturities must be distinct supported Treasury tenors")
    if _date(start) > _date(end):
        raise ValueError("start must not follow end")
    _integer(max_fill_days, "max_fill_days", 1)
    _integer(max_age_days, "max_age_days")
    return maturities


def parse_yields(payload, maturities=TENORS, start="2000-01-01", end=None,
                 max_fill_days=7, max_age_days=7):
    """Keep genuine quotes and produce bounded causal fills for CIR consumers.

    Each series keeps its own initial support before the common panel start.
    Filling therefore occurs before a consumer inner-joins the maturity dates.
    No observations are synthesized for dates absent from the source response.
    """
    end = end or date.today().isoformat()
    maturities = _settings(maturities, start, end, max_fill_days, max_age_days)
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_BYTES:
        raise ValueError("empty or oversized yield response")
    text = payload.decode("utf-8-sig")
    if any(ord(character) < 32 and character not in "\r\n\t" for character in text):
        raise ValueError("FRED response contains invalid control characters")
    try:
        records = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as error:
        raise ValueError("malformed FRED CSV: " + str(error)) from error
    header = records[0] if records else []
    expected = ["DGS%d" % n for n in maturities]
    if (len(header) != len(expected) + 1 or len(set(header)) != len(header)
            or not header or header[0] not in {"observation_date", "DATE"}
            or set(header[1:]) != set(expected)):
        raise ValueError("FRED response has unexpected date/series columns")
    rows = [row for row in records[1:] if row]
    if any(len(row) != len(header) for row in rows):
        raise ValueError("FRED response contains a malformed CSV row")
    frame = pd.DataFrame(rows, columns=header, dtype=str)
    frame = frame.rename(columns={header[0]: "observation_date"})
    if frame.empty or not frame.observation_date.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("FRED response needs valid ISO observation dates")
    frame["observation_date"] = pd.to_datetime(frame.observation_date, format="%Y-%m-%d", errors="raise")
    if frame.observation_date.duplicated().any():
        raise ValueError("FRED response contains duplicate observation dates")
    # The graph endpoint can ignore date bounds for a multi-series request.
    frame = frame.loc[frame.observation_date.between(start, end)].sort_values("observation_date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("no observations in requested date range")
    series, details = {}, {}
    firsts, lasts = [], []
    for tenor, column in zip(maturities, expected):
        tokens = frame[column].str.strip()
        missing = tokens.isin(["", "."])
        values = pd.to_numeric(tokens.mask(missing), errors="raise").astype(float)
        genuine = ~missing
        if not genuine.any():
            raise ValueError(column + " has no genuine quotes in requested range")
        if not np.isfinite(values[genuine]).all():
            raise ValueError(column + " contains nonfinite quotes")
        if (values[genuine] <= 0).any():
            raise ValueError(column + " contains nonpositive quotes incompatible with the current CIR model; no clipping applied")
        quoted_dates = frame.loc[genuine, "observation_date"]
        first, last = quoted_dates.iloc[0], quoted_dates.iloc[-1]
        if (pd.Timestamp(end) - last).days > max_age_days:
            raise ValueError(column + " is stale: last genuine quote " + last.date().isoformat())
        if (quoted_dates.diff().dt.days.dropna() > max_fill_days).any():
            raise ValueError(column + " has a quote gap exceeding max_fill_days")
        source_date = frame.observation_date.where(genuine).ffill()
        age = (frame.observation_date - source_date).dt.days
        supported = frame.observation_date.between(first, last)
        if (age[supported] > max_fill_days).any():
            raise ValueError(column + " requires a fill exceeding max_fill_days")
        result = pd.DataFrame({"observation_date": frame.observation_date,
                               column: values, "yield_clean": values.ffill(),
                               "is_imputed": missing, "source_date": source_date})
        result = result.loc[supported].copy()
        series[tenor] = result
        firsts.append(first)
        lasts.append(last)
        details[column] = {"first_observed": first.date().isoformat(),
                           "last_observed": last.date().isoformat(),
                           "leading_rows_excluded": int((frame.observation_date < first).sum())}
    common_start, common_end = max(firsts), min(lasts)
    if common_start > common_end:
        raise ValueError("maturities have no common observation history")
    common_dates = None
    for tenor, result in series.items():
        result = result.loc[result.observation_date <= common_end].copy()
        series[tenor] = result
        column = "DGS%d" % tenor
        ages = (result.observation_date - result.source_date).dt.days
        details[column].update(rows=len(result), filled_quotes=int(result.is_imputed.sum()),
                               trailing_rows_excluded=int((frame.observation_date > common_end).sum()),
                               oldest_fill_days=int(ages.max()))
        dates = pd.DatetimeIndex(result.observation_date)
        common_dates = dates if common_dates is None else common_dates.intersection(dates)
    if common_dates.empty:
        raise ValueError("maturities have no common observation dates")
    quality = {"common_start": common_dates.min().date().isoformat(),
               "common_end": common_dates.max().date().isoformat(), "rows": len(common_dates),
               "max_fill_days": max_fill_days, "max_age_days": max_age_days,
               "units": "percentage points", "series": details}
    return series, quality


def download_yields(session, maturities, start, end):
    """Bound transient retries, read time, redirects and decompressed body size."""
    params = {"id": ",".join("DGS%d" % n for n in maturities), "cosd": start, "coed": end}
    for attempt in range(3):
        response = None
        try:
            response = session.get(ENDPOINT, params=params, timeout=(10, 30),
                                   stream=True, allow_redirects=False)
            status = response.status_code
            if status == 429 or 500 <= status < 600:
                if attempt == 2:
                    raise ValueError("FRED unavailable after three attempts (HTTP %d)" % status)
                time.sleep(2 ** attempt)
                continue
            if status != 200:
                raise ValueError("FRED download failed (HTTP %d)" % status)
            if "text/html" in response.headers.get("Content-Type", "").lower():
                raise ValueError("FRED returned HTML instead of yield data")
            body = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError("FRED response exceeds size limit")
            return bytes(body), requests.Request("GET", ENDPOINT, params=params).prepare().url
        except (requests.Timeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError):
            if attempt == 2:
                raise ValueError("FRED connection failed after three attempts") from None
            time.sleep(2 ** attempt)
        finally:
            if response is not None:
                response.close()
    raise ValueError("FRED retrieval failed")


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def acquire_snapshot(output, start="2000-01-01", end=None, maturities=TENORS,
                     max_fill_days=7, max_age_days=7, session=None):
    """Publish a fresh snapshot only after all maturity histories validate."""
    end = end or date.today().isoformat()
    maturities = _settings(maturities, start, end, max_fill_days, max_age_days)
    output = repository_path(output)
    if output.exists():
        raise ValueError("snapshot output already exists; choose a new directory")
    owned_session = session is None
    session = requests.Session() if owned_session else session
    try:
        payload, url = download_yields(session, maturities, start, end)
    finally:
        if owned_session:
            session.close()
    series, quality = parse_yields(payload, maturities, start, end, max_fill_days, max_age_days)
    manifest = {"schema_version": 1, "status": "complete",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "provider": "FRED graph CSV HTTPS GET", "vintage": "current revision at retrieval; not a historical real-time vintage",
                "requested_start": start, "requested_end": end, "maturities": list(maturities),
                "quality": quality,
                "raw": {"path": "raw/fred.csv", "sha256": _sha(payload), "bytes": len(payload), "url": url},
                "sources": []}
    # Reserve only this new directory; never replace a historical snapshot.
    output = repository_path(output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "raw").mkdir()
        (output / "series").mkdir()
        (output / "raw/fred.csv").write_bytes(payload)
        for tenor, frame in series.items():
            relative = "series/DGS%d.csv" % tenor
            path = output / relative
            frame.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.17g")
            manifest["sources"].append({"maturity": tenor, "series_id": "DGS%d" % tenor,
                                        "path": relative, "sha256": _sha(path.read_bytes())})
        (output / "snapshot.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    except BaseException:
        shutil.rmtree(output)
        raise
    return manifest


def verify_snapshot(manifest_path, input_directory, maturities=TENORS):
    """Verify complete acquisition evidence before the model reads its series."""
    path, directory = repository_path(manifest_path), repository_path(input_directory)
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
            or manifest.get("schema_version") != 1 or manifest.get("status") != "complete"):
        raise ValueError("yield snapshot manifest is not complete/supported")
    if directory != path.parent / "series":
        raise ValueError("input directory does not belong to yield snapshot")
    requested = tuple(maturities)
    available = manifest.get("maturities")
    sources = manifest.get("sources")
    if (not isinstance(available, list) or not available
            or any(type(n) is not int or n not in TENORS for n in available)
            or len(available) != len(set(available))
            or not isinstance(sources, list) or len(sources) != len(available)
            or any(not isinstance(source, dict) for source in sources)
            or any(type(source.get("maturity")) is not int for source in sources)
            or [source.get("maturity") for source in sources] != available
            or not requested or any(type(n) is not int or n not in TENORS for n in requested)
            or len(set(requested)) != len(requested)
            or not set(requested).issubset(available)):
        raise ValueError("yield snapshot maturity contract mismatch")
    for source in sources:
        tenor = source["maturity"]
        if (source.get("series_id") != "DGS%d" % tenor
                or source.get("path") != "series/DGS%d.csv" % tenor):
            raise ValueError("unexpected snapshot source path")
        source_path = repository_path(path.parent / source["path"])
        if source_path.parent != directory or _sha(source_path.read_bytes()) != source.get("sha256"):
            raise ValueError("yield snapshot source hash/path mismatch")
    raw = manifest.get("raw")
    if not isinstance(raw, dict) or raw.get("path") != "raw/fred.csv":
        raise ValueError("unexpected raw snapshot path")
    raw_path = repository_path(path.parent / raw["path"])
    raw_bytes = raw_path.read_bytes()
    if raw_path.parent != path.parent / "raw" or _sha(raw_bytes) != raw.get("sha256"):
        raise ValueError("raw yield snapshot hash/path mismatch")
    quality = manifest.get("quality")
    if not isinstance(quality, dict):
        raise ValueError("yield snapshot quality metadata is missing")
    expected, expected_quality = parse_yields(
        raw_bytes, available, manifest["requested_start"], manifest["requested_end"],
        quality["max_fill_days"], quality["max_age_days"])
    if expected_quality != quality or raw.get("bytes") != len(raw_bytes):
        raise ValueError("yield snapshot quality does not match preserved raw observations")
    for tenor, frame in expected.items():
        canonical = frame.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.17g").encode("utf-8")
        if _sha(canonical) != _sha((directory / ("DGS%d.csv" % tenor)).read_bytes()):
            raise ValueError("yield snapshot series is not the recorded causal preparation of its raw source")
    return {"path": str(path.relative_to(ROOT)), "sha256": _sha(manifest_bytes),
            "retrieved_at": manifest["retrieved_at"], "vintage": manifest["vintage"],
            "requested_start": manifest["requested_start"], "requested_end": manifest["requested_end"],
            "quality": manifest["quality"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new snapshot directory inside the repository")
    parser.add_argument("--start", default="2000-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--maturities", nargs="+", type=int, default=list(TENORS))
    parser.add_argument("--max-fill-days", type=int, default=7)
    parser.add_argument("--max-age-days", type=int, default=7)
    args = parser.parse_args(argv)
    try:
        manifest = acquire_snapshot(args.output, args.start, args.end, args.maturities,
                                    args.max_fill_days, args.max_age_days)
        print(json.dumps({"output": args.output, "quality": manifest["quality"]}))
    except (ValueError, KeyError, OSError, requests.RequestException) as error:
        parser.exit(2, "Yield acquisition failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
