"""Merge Basel3's selected FFIEC schedules through the CallReports library."""

import argparse
import os
from pathlib import Path

from callreports import merge_schedule_files

PROJECT_ROOT = Path(__file__).resolve().parents[2]
schedules_directory = PROJECT_ROOT / "data/CSV/Schedules"
output_directory = PROJECT_ROOT / "data/CSV/Cleaned"


def merge_files_sequentially(base_file_path, files_to_append, output_path):
    """Retain the historical selection and first-column-wins join contract."""
    return merge_schedule_files(base_file_path, files_to_append, output_path)


def determine_files_to_append(input_directory, subfolder):
    folder_date = int(subfolder)  # Convert folder name to an integer for comparison
    mmddyyyy = convert_to_mmddyyyy(subfolder)

    if folder_date >= 20170331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRI {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(1 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(2 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(3 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(4 of 4).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    elif 20150331 <= folder_date < 20170331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRI {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(1 of 3).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(2 of 3).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(3 of 3).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    elif 20140331 <= folder_date < 20150331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRII {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRIA {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCRIB {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    elif 20090331 <= folder_date < 20140331:
        files_to_append = [
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RC {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCB {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCR {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCR {mmddyyyy}(2 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCE {mmddyyyy}.csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(1 of 2).csv'),
            os.path.join(input_directory, f'FFIEC CDR Call Schedule RCO {mmddyyyy}(2 of 2).csv')
        ]
    else:
        files_to_append = []  # Default to an empty list if the folder_date doesn't match any range

    return files_to_append

def convert_to_mmddyyyy(yyyymmdd):
    return f"{yyyymmdd[4:6]}{yyyymmdd[6:]}{yyyymmdd[:4]}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=schedules_directory)
    parser.add_argument("--output-dir", type=Path, default=output_directory)
    args = parser.parse_args(argv)
    for folder in sorted(args.input_dir.iterdir()):
        if not folder.is_dir():
            continue
        base = folder / ("FFIEC CDR Call Schedule ENT " + convert_to_mmddyyyy(folder.name) + ".csv")
        if not base.is_file():
            raise FileNotFoundError("Base file not found: " + str(base))
        output = args.output_dir / ("Cleaned_Call_Report_" + folder.name + ".csv")
        merge_files_sequentially(base, determine_files_to_append(str(folder), folder.name), output)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
