"""mergers download entry point using the shared material-event argument parser."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from Material_events_download import parse_args as parse_event_args, run_downloads


def parse_args(argv=None):
    return parse_event_args(argv, default_events=["mergers"])


def main(argv=None):
    return run_downloads(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
