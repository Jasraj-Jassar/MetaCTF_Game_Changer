# MetaCTF Helpers

Utilities for indexing MetaCTF events and downloading problems.

## Setup
- Python 3.9+ recommended.
- Install dependencies: `pip install -r requirements.txt`
- Place `cookies.txt` (Netscape format) in the repo root.

## CLI
```
python -m metactf_helpers <command> [options]
```
- `index`: `python -m metactf_helpers index "https://compete.metactf.com/<event_id>/problems"`
- `fetch`: `python -m metactf_helpers fetch "https://compete.metactf.com/<event_id>/problem?p=<id>" --dest ./CTFProblems`
- `fetch-all`: `python -m metactf_helpers fetch-all "<problems_url | list.txt>" --concurrency 8`

Outputs:
- Problems land under `CTFProblems/<slug>/problem.txt` (containerized challenges go to `CTFProblems/Containerized/<slug>`).
- Linked files are pulled into the same folder; statuses are recorded in `links.txt`.

## Wrapper scripts (backward compatible)
- `fetch_metactf_problem.py` and `metactf_event_index.py` now forward to the CLI.
- `run_all_problems.sh` wraps `python -m metactf_helpers fetch-all` and still honors `CONCURRENCY`, `PYTHON`, `COOKIES`, `DEST`, and `SKIP_DOWNLOADS=1`.
