#!/usr/bin/env python3

"""
Compatibility wrapper for the refactored MetaCTF helper CLI.

Usage (unchanged):
  python metactf_event_index.py "https://compete.metactf.com/<event_id>/problems"
"""

import sys
from typing import List

from metactf_helpers.cli import main as cli_main


def main(argv: List[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        return cli_main(["index", "--help"])
    if not argv:
        print('Usage: python metactf_event_index.py "https://compete.metactf.com/<event_id>/problems"', file=sys.stderr)
        return 1
    return cli_main(["index", *argv])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
