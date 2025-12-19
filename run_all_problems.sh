#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_all_problems.sh <event_problems_url | problems_list.txt>
# - If given an event problems URL, runs metactf_event_index.py to build the list file first.
# - If given a .txt file, uses it directly (one URL per line; blanks/# comments ignored).
# - Runs fetch_metactf_problem.py for each URL in parallel.
# - Concurrency: CONCURRENCY=<num> (default: CPU count). Python override: PYTHON=<path>.

input="${1:-}"
if [[ -z "$input" ]]; then
  echo "Usage: $0 <event_problems_url | problems_list.txt>" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fetch_script="${script_dir}/fetch_metactf_problem.py"
event_script="${script_dir}/metactf_event_index.py"
python_bin="${PYTHON:-python}"
concurrency="${CONCURRENCY:-$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN || echo 4)}"

if [[ ! -x "$fetch_script" && ! -f "$fetch_script" ]]; then
  echo "[!] fetch_metactf_problem.py not found beside this script" >&2
  exit 1
fi

if [[ ! -x "$event_script" && ! -f "$event_script" ]]; then
  echo "[!] metactf_event_index.py not found beside this script" >&2
  exit 1
fi

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "[!] Python executable not found: $python_bin" >&2
  exit 1
fi

list_file=""

if [[ -f "$input" ]]; then
  list_file="$input"
else
  problems_url="$input"
  # Validate and extract event_id using Python (same logic as metactf_event_index.py)
  event_id="$("$python_bin" - "$problems_url" <<'PY'
import sys
from urllib.parse import urlparse

url = sys.argv[1]
parsed = urlparse(url)
parts = parsed.path.strip("/").split("/")
if len(parts) < 2 or parts[1] != "problems" or not parts[0].isdigit() or not parsed.netloc:
    sys.stderr.write("[!] URL must look like: https://compete.metactf.com/<event_id>/problems\n")
    sys.exit(1)
print(parts[0])
PY
)"

  list_file="metactf_${event_id}_problems.txt"
  echo "[*] Generating list via metactf_event_index.py -> $list_file"
  "$python_bin" "$event_script" "$problems_url"
fi

if [[ ! -f "$list_file" ]]; then
  echo "[!] List file not found after setup: $list_file" >&2
  exit 1
fi

grep -Ev '^\s*(#|$)' "$list_file" \
  | xargs -P "$concurrency" -n 1 -I {} \
    bash -c '"$0" "$1" "$2"' "$python_bin" "$fetch_script" {}

echo "[+] Done. Launched fetches for list: $list_file"
