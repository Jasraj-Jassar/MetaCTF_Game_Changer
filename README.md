# MetaCTF Helpers

Small scripts to pull MetaCTF events and problems.

## Scripts
- `metactf_event_index.py` — given `https://compete.metactf.com/<event_id>/problems`, fetches problem URLs and writes `metactf_<event_id>_problems.txt`.
- `fetch_metactf_problem.py` — given a single problem URL, saves `problem.txt` and (if present) `links.txt`, downloads linked files into a folder named after the problem.
- `run_all_problems.sh` — accepts an event problems URL or a list file; builds the list if needed, then fetches all problems in parallel. Concurrency via `CONCURRENCY=<num>`.

## Prereqs
- `cookies.txt` (Netscape format) in this directory.
- `python` available; `wget` for link downloading.

## Examples
- `python metactf_event_index.py "https://compete.metactf.com/493/problems"`
- `python fetch_metactf_problem.py "https://compete.metactf.com/493/problem?p=3"`
- `CONCURRENCY=8 ./run_all_problems.sh "https://compete.metactf.com/493/problems"`
