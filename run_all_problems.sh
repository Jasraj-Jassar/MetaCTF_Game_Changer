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

args+=("$@")

exec "$python_bin" "${args[@]}"
