"""Convert Basel3's extracted FFIEC quarters through the CallReports library."""

import argparse
from pathlib import Path

from callreports import convert_txt_to_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TXT_DIR = PROJECT_ROOT / "data/TXT"
SCHEDULES_DIR = PROJECT_ROOT / "data/CSV/Schedules"


def batch_process_txt_to_csv(delimiter="\t", txt_dir=TXT_DIR, output_dir=SCHEDULES_DIR):
    written = []
    for folder in sorted(Path(txt_dir).iterdir()):
        if folder.is_dir():
            written.extend(convert_txt_to_csv(folder, Path(output_dir) / folder.name.split()[-1], delimiter))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--txt-dir", type=Path, default=TXT_DIR)
    parser.add_argument("--output-dir", type=Path, default=SCHEDULES_DIR)
    args = parser.parse_args(argv)
    for path in batch_process_txt_to_csv(txt_dir=args.txt_dir, output_dir=args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
