#!/usr/bin/env python3

"""
Compatibility wrapper for the refactored MetaCTF helper CLI.

Usage (unchanged):
  python fetch_metactf_problem.py "https://compete.metactf.com/<event_id>/problem?p=<id>"

Extra options supported from the new CLI:
  python fetch_metactf_problem.py <url> --cookies cookies.txt --dest ./CTFProblems --skip-downloads
"""

import sys
from typing import List

from metactf_helpers.cli import main as cli_main


def main(argv: List[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        return cli_main(["fetch", "--help"])
    if not argv:
        print("Usage: python fetch_metactf_problem.py <problem_url> [--dest DIR] [--cookies FILE]", file=sys.stderr)
        return 1
    return cli_main(["fetch", *argv])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
