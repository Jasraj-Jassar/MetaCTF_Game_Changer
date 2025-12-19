#!/usr/bin/env bash
set -euo pipefail

# Wrapper for the Python CLI:
#   ./run_all_problems.sh <event_problems_url | problems_list.txt> [extra fetch-all args]
#
# Environment overrides:
#   PYTHON=<python binary>    (default: python)
#   CONCURRENCY=<num>         -> --concurrency
#   COOKIES=<path>            -> --cookies
#   DEST=<path>               -> --dest
#   SKIP_DOWNLOADS=1          -> --skip-downloads
#   OPEN_FOLDERS=0            -> disable auto-open (default: on)
#   CODE_BIN=<code>           -> --code-bin <code>
#   CODE_NEW_WINDOW=1         -> --code-new-window

input="${1:-}"
if [[ -z "$input" ]]; then
  echo "Usage: $0 <event_problems_url | problems_list.txt> [extra args]" >&2
  exit 1
fi
shift

python_bin="${PYTHON:-python}"

args=(-m metactf_helpers fetch-all "$input")

if [[ -n "${CONCURRENCY:-}" ]]; then
  args+=(--concurrency "$CONCURRENCY")
fi

if [[ -n "${COOKIES:-}" ]]; then
  args+=(--cookies "$COOKIES")
fi

if [[ -n "${DEST:-}" ]]; then
  args+=(--dest "$DEST")
fi

if [[ "${SKIP_DOWNLOADS:-}" == "1" ]]; then
  args+=(--skip-downloads)
fi

# Auto-open fetched folders in VS Code by default; set OPEN_FOLDERS=0 to skip
open_folders="${OPEN_FOLDERS:-1}"
code_bin="${CODE_BIN:-}"
code_new_window="${CODE_NEW_WINDOW:-}"

if [[ -n "$code_bin" ]]; then
  args+=(--code-bin "$code_bin")
fi

if [[ "$code_new_window" == "1" ]]; then
  args+=(--code-new-window)
fi

if [[ "$open_folders" != "0" ]]; then
  args+=(--open-folders)
fi

args+=("$@")

exec "$python_bin" "${args[@]}"
