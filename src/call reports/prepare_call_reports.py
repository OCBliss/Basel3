"""Prepare FFIEC single-period Call Reports from the pipeline's event date ranges."""

import argparse
import calendar
import csv
from datetime import date, datetime
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import time
import uuid
import zipfile
import zlib

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
import Task_manager_Global_yaml_driven as manager

URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
PRODUCT = "ReportingSeriesSinglePeriod"
# The public site's application gateway rejects requests' default User-Agent.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/140.0.0.0 Safari/537.36")
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024


class PreparationError(Exception):
    """A requested quarter could not be prepared completely."""


def quarter_ends(start, end):
    return [date(year, month, calendar.monthrange(year, month)[1])
            for year in range(start.year, end.year + 1)
            for month in (3, 6, 9, 12)
            if start <= date(year, month, calendar.monthrange(year, month)[1]) <= end]


def previous_quarter(quarter, count):
    absolute_month = quarter.year * 12 + quarter.month - 1 - count * 3
    year, month = divmod(absolute_month, 12)
    month += 1
    return date(year, month, calendar.monthrange(year, month)[1])


def plan_quarters(config_path, history_quarters=3):
    if history_quarters < 0:
        raise PreparationError("history quarters must not be negative")
    config = manager.load_config(Path(config_path))
    ranges, event_quarters = [], set()
    for step, script in config.scripts.items():
        if script.path.name != "Material_events_download.py":
            continue
        spec = importlib.util.spec_from_file_location("ffiec_event_arguments", script.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        arguments = module.parse_args(list(script.args))
        try:
            start, end = date.fromisoformat(arguments.start_date), date.fromisoformat(arguments.end_date)
        except ValueError as error:
            raise PreparationError("Invalid material-event dates in step {}: {}".format(step, error)) from error
        if start > end:
            raise PreparationError("Material-event start date exceeds end date in step " + step)
        selected = quarter_ends(start, end)
        if not selected:
            raise PreparationError("No quarter-end dates in material-event step " + step)
        event_quarters.update(selected)
        ranges.append({"step": step, "events": arguments.events,
                       "start_date": start.isoformat(), "end_date": end.isoformat()})
    if not ranges:
        raise PreparationError("No material-event download stages found in " + str(config.path))
    required = event_quarters | {previous_quarter(quarter, lag)
                                 for quarter in event_quarters
                                 for lag in range(1, history_quarters + 1)}
    return {"config": str(config.path), "ranges": ranges, "history_count": history_quarters,
            "event_quarters": [q.strftime("%Y%m%d") for q in sorted(event_quarters)],
            "history_quarters": [q.strftime("%Y%m%d") for q in sorted(required - event_quarters)],
            "required_quarters": [q.strftime("%Y%m%d") for q in sorted(required)]}


class DownloadForm(HTMLParser):
    """Read the public ASP.NET form controls and current postback state."""

    def __init__(self, html):
        super().__init__()
        self.hidden, self.controls, self.options = {}, {}, {}
        self.current_select = self.current_option = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("input", "select") and "id" in attrs:
            self.controls[attrs["id"]] = attrs
        if tag == "input" and attrs.get("type") == "hidden" and "name" in attrs:
            self.hidden[attrs["name"]] = attrs.get("value", "")
        if tag == "select":
            self.current_select = attrs["id"]
            self.options[self.current_select] = []
        if tag == "option" and self.current_select:
            self.current_option = [attrs.get("value", ""), ""]
            self.options[self.current_select].append(self.current_option)

    def handle_data(self, data):
        if self.current_option is not None:
            self.current_option[1] += data

    def handle_endtag(self, tag):
        if tag == "option":
            self.current_option = None
        if tag == "select":
            self.current_select = None

    def control(self, name):
        try:
            return self.controls[name]
        except KeyError as error:
            raise PreparationError("FFIEC download form is missing control " + name) from error


class FFIECBulkClient:
    def __init__(self, retries=3, timeout=180):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Referer": URL})
        self.retries, self.timeout = retries, (15, timeout)
        self.form = None

    def close(self):
        self.session.close()

    def periods(self):
        with self.session.get(URL, timeout=self.timeout) as response:
            response.raise_for_status()
            form = DownloadForm(response.text)
        series = form.control("ListBox1")["name"]
        if PRODUCT not in {value for value, label in form.options.get("ListBox1", [])}:
            raise PreparationError("FFIEC does not offer Call Reports -- Single Period")
        data = dict(form.hidden)
        data.update({series: PRODUCT, "__EVENTTARGET": series})
        with self.session.post(URL, data=data, timeout=self.timeout) as response:
            response.raise_for_status()
            self.form = DownloadForm(response.text)
        periods = {}
        for value, label in self.form.options.get("DatesDropDownList", []):
            try:
                quarter = datetime.strptime(label.strip(), "%m/%d/%Y").date()
            except ValueError:
                continue
            periods[quarter] = value
        if not periods:
            raise PreparationError("FFIEC returned no single-period reporting dates")
        return periods

    def download(self, quarter, destination):
        for attempt in range(1, self.retries + 1):
            try:
                self._download(quarter, destination)
                validate_archive(destination, quarter)
                return
            except (requests.RequestException, PreparationError, zipfile.BadZipFile) as error:
                Path(destination).unlink(missing_ok=True)
                if attempt == self.retries:
                    raise PreparationError("{} failed after {} attempt(s): {}".format(
                        quarter, attempt, error)) from error
                print("Retrying {} ({}/{}): {}".format(quarter, attempt, self.retries, error), flush=True)
                time.sleep(min(2 ** (attempt - 1), 8))

    def _download(self, quarter, destination):
        periods = self.periods()
        if quarter not in periods:
            raise PreparationError("FFIEC has no single-period report for {} (available {} through {})".format(
                quarter, min(periods), max(periods)))
        form = self.form
        series = form.control("ListBox1")["name"]
        date_field = form.control("DatesDropDownList")["name"]
        data = dict(form.hidden)
        data.update({series: PRODUCT, date_field: periods[quarter], "__EVENTTARGET": date_field})
        with self.session.post(URL, data=data, timeout=self.timeout) as response:
            response.raise_for_status()
            form = DownloadForm(response.text)
        radio, button = form.control("TSVRadioButton"), form.control("Download_0")
        data = dict(form.hidden)
        data.update({series: PRODUCT, date_field: periods[quarter], radio["name"]: radio["value"],
                     button["name"]: button["value"], "__EVENTTARGET": ""})
        with self.session.post(URL, data=data, timeout=self.timeout, stream=True) as response:
            response.raise_for_status()
            if "text/html" in response.headers.get("Content-Type", "").lower():
                raise PreparationError("FFIEC returned an HTML page instead of a ZIP")
            expected_size = response.headers.get("Content-Length")
            size = 0
            with Path(destination).open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_ARCHIVE_BYTES:
                        raise PreparationError("FFIEC archive exceeds the download size limit")
                    output.write(chunk)
            if expected_size is not None and size != int(expected_size):
                raise PreparationError("FFIEC download was truncated")


def validate_archive(path, quarter):
    suffix = quarter.strftime("%m%d%Y")
    required = {"FFIEC CDR Call Bulk POR " + suffix + ".txt",
                "FFIEC CDR Call Schedule ENT " + suffix + ".txt",
                "FFIEC CDR Call Schedule RC " + suffix + ".txt"}
    try:
        with zipfile.ZipFile(path) as archive:
            members, names, parts = [], set(), {}
            for item in archive.infolist():
                name = PurePosixPath(item.filename)
                if name.is_absolute() or ".." in name.parts or "\\" in item.filename:
                    raise PreparationError("Unsafe archive path: " + item.filename)
                if item.is_dir():
                    continue
                if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                    raise PreparationError("Archive contains a link or encrypted member: " + item.filename)
                if name.name in names or not name.name.lower().endswith(".txt"):
                    raise PreparationError("Duplicate or unexpected archive member: " + item.filename)
                if name.name.startswith("FFIEC CDR Call ") and suffix not in name.name:
                    raise PreparationError("Wrong reporting quarter in " + item.filename)
                names.add(name.name)
                members.append(item)
                split = re.fullmatch(r"(.+)\((\d+) of (\d+)\)\.txt", name.name)
                if split:
                    stem, number, total = split.groups()
                    parts.setdefault((stem, int(total)), set()).add(int(number))
            if not required <= names:
                raise PreparationError("Missing required Call Report files: " + ", ".join(sorted(required - names)))
            if any(numbers != set(range(1, count + 1)) for (stem, count), numbers in parts.items()):
                raise PreparationError("Incomplete split schedule in archive")
            if sum(item.file_size for item in members) > MAX_EXTRACTED_BYTES:
                raise PreparationError("Call Report archive exceeds the extraction size limit")
            if archive.testzip() is not None:
                raise PreparationError("Call Report ZIP failed CRC verification")
            for item in members:
                if PurePosixPath(item.filename).name not in required:
                    continue
                with archive.open(item) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as source:
                    rows = csv.reader(source, delimiter="\t")
                    header = next(rows, [])
                    if len(header) < 2 or header[0].strip() != "IDRSSD":
                        raise PreparationError("Invalid required file header: " + item.filename)
                    is_por = PurePosixPath(item.filename).name.startswith("FFIEC CDR Call Bulk POR")
                    if not any(len(row) >= 2 and row[0].strip() and (not is_por or row[1].strip()) for row in rows):
                        raise PreparationError("Required file has no bank rows: " + item.filename)
            return members
    except (zipfile.BadZipFile, EOFError, RuntimeError, zlib.error, UnicodeError) as error:
        raise PreparationError("Invalid Call Report ZIP {}: {}".format(path, error)) from error


def file_record(path):
    digest, checksum, size = hashlib.sha256(), 0, 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
            checksum = zlib.crc32(chunk, checksum)
    return {"name": path.name, "size": size, "crc32": checksum & 0xffffffff,
            "sha256": digest.hexdigest()}


def checked_files(directory, members, quarter):
    if not directory.is_dir() or directory.is_symlink():
        return None
    expected = {PurePosixPath(item.filename).name for item in members}
    # Existing README files and Finder metadata are not converter inputs.
    if {p.name for p in directory.iterdir() if p.name.lower().endswith(".txt")} != expected:
        return None
    records = []
    for item in members:
        path = directory / PurePosixPath(item.filename).name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item.file_size:
            return None
        record = file_record(path)
        if record["crc32"] != item.CRC:
            return None
        records.append(record)
    por = directory / ("FFIEC CDR Call Bulk POR " + quarter.strftime("%m%d%Y") + ".txt")
    with por.open(encoding="utf-8-sig", newline="") as source:
        rows = csv.reader(source, delimiter="\t")
        header = next(rows, [])
        if len(header) < 2 or header[0].strip() != "IDRSSD":
            raise PreparationError("Invalid POR header in " + str(por))
        if not any(len(row) >= 2 and row[0].strip() and row[1].strip() for row in rows):
            raise PreparationError("POR has no bank/certificate mapping: " + str(por))
    return records


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_quarter(quarter, txt_dir, cache_dir, client, refresh=False):
    txt_dir, cache_dir = Path(txt_dir), Path(cache_dir)
    txt_dir.mkdir(parents=True, exist_ok=True)
    key = quarter.strftime("%Y%m%d")
    archive = cache_dir / "archives" / (key + ".zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    members = None
    if archive.is_file() and not refresh:
        try:
            members = validate_archive(archive, quarter)
        except PreparationError:
            print("Replacing invalid cached ZIP for " + key, flush=True)
    if members is None:
        temporary = archive.with_name(key + "." + uuid.uuid4().hex + ".part")
        try:
            print("Downloading Call Reports -- Single Period: " + key, flush=True)
            client.download(quarter, temporary)
            members = validate_archive(temporary, quarter)
            os.replace(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
    target = txt_dir / ("FFIEC CDR Call Bulk All Schedules " + key)
    records = checked_files(target, members, quarter)
    result = {"quarter": key, "directory": str(target), "archive": str(archive), "status": "verified"}
    if records is None:
        if target.exists() and (not target.is_dir() or target.is_symlink()):
            raise PreparationError("Extraction target is not an ordinary directory: " + str(target))
        # Stage outside TXT, because the converter visits every child of TXT.
        with tempfile.TemporaryDirectory(prefix=".ffiec-", dir=txt_dir.parent) as stage:
            staged = Path(stage) / target.name
            staged.mkdir()
            with zipfile.ZipFile(archive) as source:
                for item in members:
                    with source.open(item) as inp, (staged / PurePosixPath(item.filename).name).open("wb") as out:
                        shutil.copyfileobj(inp, out)
            records = checked_files(staged, members, quarter)
            if records is None:
                raise PreparationError("Incomplete extraction for " + key)
            backup = None
            if target.exists():
                for existing in target.iterdir():
                    if existing.is_file() and not existing.is_symlink() and existing.suffix.lower() == ".md":
                        shutil.copy2(existing, staged / existing.name)
                backup = txt_dir.parent / "FFIEC_backups" / (key + "_" + uuid.uuid4().hex)
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, backup)
                result["backup"] = str(backup)
            try:
                os.replace(staged, target)
            except OSError:
                if backup is not None:
                    os.replace(backup, target)
                raise
            result["status"] = "updated" if backup is not None else "extracted"
    result["files"] = records
    write_json(cache_dir / "quarters" / (key + ".json"), result)
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=manager.DEFAULT_CONFIG)
    parser.add_argument("--txt-dir", type=Path, default=PROJECT_ROOT / "data/TXT")
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / "data/FFIEC")
    parser.add_argument("--manifest", type=Path,
                        help="Completion record; defaults to <cache-dir>/prepared.json.")
    parser.add_argument("--history-quarters", type=int, default=3,
                        help="Earlier reports needed by the current P1Q/P2Q/P3Q calculations (default: 3).")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180, help="Seconds allowed for each HTTP read.")
    parser.add_argument("--refresh", action="store_true", help="Download fresh ZIPs even when cached ZIPs are valid.")
    parser.add_argument("--plan", action="store_true", help="Print the required quarters without downloading or writing files.")
    args = parser.parse_args(argv)
    if args.history_quarters < 0 or args.retries < 1 or args.timeout < 1:
        parser.error("history must be nonnegative; retries and timeout must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    client = None
    try:
        manifest = args.manifest or args.cache_dir / "prepared.json"
        # A failed new plan must not leave an old completion marker in place.
        if not args.plan:
            manifest.unlink(missing_ok=True)
        plan = plan_quarters(args.config, args.history_quarters)
        if args.plan:
            print(json.dumps(plan, indent=2))
            return 0
        client = FFIECBulkClient(args.retries, args.timeout)
        quarters = plan["required_quarters"]
        print("Preparing {} requested quarters and {} history quarters ({} through {}).".format(
            len(plan["event_quarters"]), len(plan["history_quarters"]), quarters[0], quarters[-1]), flush=True)
        completed = []
        for index, key in enumerate(quarters, 1):
            result = prepare_quarter(datetime.strptime(key, "%Y%m%d").date(), args.txt_dir,
                                     args.cache_dir, client, args.refresh)
            completed.append(result)
            print("[{}/{}] {}: {} ({} files)".format(index, len(quarters), key,
                  result["status"], len(result["files"])), flush=True)
        plan.update({"source": URL, "product": PRODUCT, "format": "Tab Delimited", "quarters": completed})
        write_json(manifest, plan)
        print("All {} quarters verified. Completion record: {}".format(len(quarters), manifest), flush=True)
        return 0
    except (PreparationError, manager.ConfigError, OSError, ValueError) as error:
        print("Call Report preparation failed: " + str(error), file=sys.stderr, flush=True)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
