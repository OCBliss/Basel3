"""Convert and merge local Call Report data from explicit input/output paths."""

import argparse
import csv
from pathlib import Path
import sys
import zipfile

from .preparation import convert_txt_to_csv, merge_schedules, prepare_archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Extract a local quarterly ZIP and produce a merged CSV")
    prepare.add_argument("archive", type=Path)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--date", help="Reporting quarter end, YYYYMMDD; otherwise inferred from filenames")
    convert = commands.add_parser("convert", help="Convert one quarter's extracted TXT schedules to CSV")
    convert.add_argument("input_dir", type=Path)
    convert.add_argument("--output-dir", type=Path, required=True)
    merge = commands.add_parser("merge", help="Merge one quarter's schedule CSVs by IDRSSD")
    merge.add_argument("input_dir", type=Path)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--date", help="Reporting quarter end, YYYYMMDD; otherwise inferred from filenames")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(prepare_archive(args.archive, args.output_dir, args.date))
        elif args.command == "convert":
            for path in convert_txt_to_csv(args.input_dir, args.output_dir):
                print(path)
        else:
            merge_schedules(args.input_dir, args.output, args.date)
            print(args.output)
    except (OSError, ValueError, zipfile.BadZipFile, csv.Error) as error:
        print("CallReports: " + str(error), file=sys.stderr)
        return 1
    return 0
