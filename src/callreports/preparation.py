"""Prepare local FFIEC single-quarter ZIP/TXT schedules without a Basel3 checkout."""

import calendar
import csv
from datetime import date, datetime
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

import numpy as np
import pandas as pd


MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
STAMP = re.compile(r" (\d{8})(?:\(\d+ of \d+\))?\.(?:txt|csv)$", re.I)


def _quarter(value):
    if isinstance(value, date):
        result = date(value.year, value.month, value.day)
    else:
        result = datetime.strptime(str(value), "%Y%m%d").date()
    if result.month not in (3, 6, 9, 12) or result.day != calendar.monthrange(result.year, result.month)[1]:
        raise ValueError("Reporting date must be a calendar quarter end")
    return result


def _file_quarter(path):
    match = STAMP.search(Path(path).name)
    if not match:
        raise ValueError("Cannot infer the reporting date from " + str(path))
    return _quarter(datetime.strptime(match.group(1), "%m%d%Y").date())


def _files(directory, extension):
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))
    found = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() == extension)
    names = [p.name.casefold() for p in found]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate schedule filenames in " + str(directory))
    return found


def _identifier(value):
    value = str(value).strip()
    return str(int(value)) if value.isascii() and value.isdecimal() else None


def extract_archive(archive_path, output_dir):
    """Extract a local ZIP into a new directory after validating its members.

    Nested member paths are preserved. Absolute paths, parent traversal,
    backslashes, links, duplicate names and oversized archives are rejected.
    """
    archive_path, output_dir = Path(archive_path), Path(output_dir)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("ZIP exceeds the compressed-size limit")
    if output_dir.exists():
        raise FileExistsError(str(output_dir))
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if sum(m.file_size for m in members) > MAX_EXTRACTED_BYTES:
            raise ValueError("ZIP exceeds the extracted-size limit")
        names = set()
        for member in members:
            path = PurePosixPath(member.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.filename
                    or ":" in member.filename or not path.parts
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError("Unsafe ZIP member: " + member.filename)
            if member.filename.casefold() in names:
                raise ValueError("Duplicate ZIP member: " + member.filename)
            names.add(member.filename.casefold())
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_dir.mkdir()
            for member in members:
                destination = output_dir.joinpath(*PurePosixPath(member.filename).parts)
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, destination.open("xb") as target:
                        shutil.copyfileobj(source, target)
        except Exception:
            shutil.rmtree(output_dir)
            raise
    return output_dir


def convert_txt_to_csv(input_dir, output_dir, delimiter="\t", encoding="utf-8-sig"):
    """Convert schedules, removing description rows and attaching POR certificates.

    Returns the written schedule CSV paths. Input headers retain their FFIEC
    codes. A POR file supplies the IDRSSD-to-FDIC-certificate mapping and is not
    exported as a schedule. Input files are never modified.
    """
    files = _files(input_dir, ".txt")
    por_files = [p for p in files if p.name.lower().startswith("ffiec cdr call bulk por")]
    if len(por_files) != 1:
        raise ValueError("Expected exactly one FFIEC Call Bulk POR file")
    certificates = {}
    with por_files[0].open(newline="", encoding=encoding) as source:
        reader = csv.reader(source, delimiter=delimiter)
        header = next(reader, [])
        if len(header) < 2 or header[0].strip() != "IDRSSD":
            raise ValueError("POR must begin with IDRSSD and a certificate column")
        certificate_column = header.index("FDIC Certificate Number") if "FDIC Certificate Number" in header else 1
        for row in reader:
            identifier = _identifier(row[0]) if row else None
            if identifier is None:
                continue
            if len(row) <= certificate_column:
                raise ValueError("Incomplete POR row for IDRSSD " + identifier)
            certificate = row[certificate_column].strip()
            if identifier in certificates and certificates[identifier] != certificate:
                raise ValueError("Conflicting POR certificates for IDRSSD " + identifier)
            certificates[identifier] = certificate
    if not certificates:
        raise ValueError("POR contains no bank identifiers")
    schedules = [p for p in files if p.name.lower().startswith("ffiec cdr call schedule ")]
    if not schedules:
        raise ValueError("No TXT schedules found")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for schedule in schedules:
        destination = output_dir / (schedule.stem + ".csv")
        with schedule.open(newline="", encoding=encoding) as source:
            reader = csv.reader(source, delimiter=delimiter)
            header = [value.strip() for value in next(reader, [])]
            while header and not header[-1]:
                header.pop()
            if not header or header[0] != "IDRSSD" or len(header) != len(set(header)):
                raise ValueError("Schedule requires unique headers beginning with IDRSSD: " + schedule.name)
            if "FDIC Certificate Number" in header:
                raise ValueError("TXT schedule already contains a certificate column: " + schedule.name)
            with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8",
                                             dir=output_dir, delete=False) as target:
                temporary = Path(target.name)
                try:
                    writer = csv.writer(target)
                    writer.writerow(header[:1] + ["FDIC Certificate Number"] + header[1:])
                    for row in reader:
                        identifier = _identifier(row[0]) if row else None
                        if identifier is None:
                            continue
                        if len(row) > len(header) and any(value.strip() for value in row[len(header):]):
                            raise ValueError("Schedule row exceeds header width: " + schedule.name)
                        row = row[:len(header)] + [""] * max(0, len(header) - len(row))
                        row[0] = identifier
                        writer.writerow(row[:1] + [certificates.get(identifier, "")] + row[1:])
                except Exception:
                    temporary.unlink()
                    raise
        temporary.replace(destination)
        written.append(destination)
    return written


def _read_schedule(path):
    table = pd.read_csv(path, low_memory=False)
    if "IDRSSD" not in table:
        raise ValueError("Missing IDRSSD in " + str(path))
    identifiers = pd.to_numeric(table["IDRSSD"], errors="coerce")
    if (identifiers.isna().any() or not np.isfinite(identifiers).all()
            or identifiers.mod(1).ne(0).any() or identifiers.le(0).any()):
        raise ValueError("Invalid IDRSSD in " + str(path))
    table["IDRSSD"] = identifiers.astype("int64")
    if table["IDRSSD"].duplicated().any():
        raise ValueError("Duplicate IDRSSD in " + str(path))
    return table


def merge_schedule_files(base_file, files_to_append, output_file=None):
    """Left-join existing schedules to a base bank population by IDRSSD.

    Repeated columns retain the first schedule's value, matching Basel3's
    historical merge contract. Missing optional file paths are skipped. Duplicate
    bank identifiers fail rather than multiplying bank rows.
    """
    result = _read_schedule(base_file)
    seen = set(result.columns)
    for path in files_to_append:
        path = Path(path)
        if not path.is_file():
            continue
        table = _read_schedule(path)
        columns = [column for column in table if column not in seen or column == "IDRSSD"]
        result = result.merge(table[columns], on="IDRSSD", how="left", sort=False, validate="one_to_one")
        seen.update(columns)
    if output_file is not None:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_file, index=False)
    return result


def clean_report(table, reporting_date):
    """Set the reporting date and remove the legacy RCON9224 text field.

    Other values, including missing observations, are preserved. This function
    does not coerce all fields to numbers or fill absent observations with zero.
    """
    quarter = _quarter(reporting_date)
    result = table.drop(columns=["RCON9224"], errors="ignore").copy()
    result["RCON9999"] = int(quarter.strftime("%Y%m%d"))
    return result


def merge_schedules(input_dir, output_file=None, reporting_date=None):
    """Merge every converted schedule for one quarter using ENT as the base.

    This includes all available schedule columns, independently of Basel3's
    selection of schedules and ratios. Bank order and membership follow ENT.
    """
    files = _files(input_dir, ".csv")
    bases = [p for p in files if p.name.lower().startswith("ffiec cdr call schedule ent ")]
    if len(bases) != 1:
        raise ValueError("Expected exactly one ENT schedule for one reporting quarter")
    quarter = _quarter(reporting_date) if reporting_date is not None else _file_quarter(bases[0])
    for path in files:
        if _file_quarter(path) != quarter:
            raise ValueError("Mixed reporting quarters in " + str(input_dir))
    result = merge_schedule_files(bases[0], [p for p in files if p != bases[0]])
    if "RCON9999" in result:
        dates = pd.to_numeric(result["RCON9999"], errors="coerce").dropna()
        if dates.ne(int(quarter.strftime("%Y%m%d"))).any():
            raise ValueError("Reported RCON9999 disagrees with the schedule date")
    result = clean_report(result, quarter)
    if output_file is not None:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_file, index=False)
    return result


def prepare_archive(archive_path, output_dir, reporting_date=None):
    """Create an atomic quarter directory with TXT, schedules and a merged CSV.

    Returns ``<output_dir>/<YYYYMMDD>/Cleaned_Call_Report_<YYYYMMDD>.csv``.
    Existing quarter directories are never replaced. No network is accessed.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".callreports-", dir=output_dir) as temporary:
        staging = Path(temporary) / "quarter"
        staging.mkdir()
        txt = extract_archive(archive_path, staging / "TXT")
        files = [p for p in _files(txt, ".txt")
                 if p.name.lower().startswith(("ffiec cdr call schedule ", "ffiec cdr call bulk por "))]
        bases = [p for p in files if p.name.lower().startswith("ffiec cdr call schedule ent ")]
        if len(bases) != 1:
            raise ValueError("Expected exactly one ENT schedule in the ZIP")
        quarter = _quarter(reporting_date) if reporting_date is not None else _file_quarter(bases[0])
        for path in files:
            if _file_quarter(path) != quarter:
                raise ValueError("Mixed reporting quarters in the ZIP")
        key = quarter.strftime("%Y%m%d")
        destination = output_dir / key
        if destination.exists():
            raise FileExistsError(str(destination))
        convert_txt_to_csv(txt, staging / "Schedules")
        name = "Cleaned_Call_Report_" + key + ".csv"
        merge_schedules(staging / "Schedules", staging / name, quarter)
        staging.rename(destination)
    return destination / name
