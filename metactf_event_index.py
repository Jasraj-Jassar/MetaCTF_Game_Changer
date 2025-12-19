#!/usr/bin/env python3
"""
MetaCTF Event Index (Problem Links)

Fetches all *real* problem links for a given MetaCTF event problems page.

Input:
  https://compete.metactf.com/<event_id>/problems

Output (one per line):
  https://compete.metactf.com/<event_id>/problem?p=<numeric_id>

Requirements:
  - cookies.txt in the same directory (Netscape cookie format, like curl uses)
  - curl installed

Usage:
  python metactf_event_index.py "https://compete.metactf.com/493/problems"
"""

import sys
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def die(msg: str, code: int = 1) -> None:
    print(f"[!] {msg}")
    raise SystemExit(code)


def curl_get(url: str, referer: str) -> bytes:
    cmd = [
        "curl", "-s",
        "--cookie", "cookies.txt",
        "-H", "X-Requested-With: XMLHttpRequest",
        "-H", f"Referer: {referer}",
        url,
    ]
    try:
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        die(f"curl failed: {e}")


def extract_event_id(problems_url: str) -> tuple[str, str]:
    """
    Returns (host, event_id) from:
      https://compete.metactf.com/<event_id>/problems
    """
    parsed = urlparse(problems_url)
    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2 or parts[1] != "problems" or not parts[0].isdigit():
        die("URL must look like: https://compete.metactf.com/<event_id>/problems")

    if not parsed.netloc:
        die("Invalid URL (missing host)")

    return parsed.netloc, parts[0]


def get_problem_ids_only(data) -> list[str]:
    """
    Only take IDs from the real problems array, ignoring category objects.

    Expected JSON shapes:
      - { "problems": [ {...}, ... ] }
      - [ {...}, ... ]   (less common)
    """
    if isinstance(data, dict) and isinstance(data.get("problems"), list):
        problems = data["problems"]
    elif isinstance(data, list):
        problems = data
    else:
        return []

    ids: list[str] = []
    for p in problems:
        if not isinstance(p, dict):
            continue

        pid = p.get("id")
        if pid is None:
            continue

        pid_str = str(pid).strip()
        if pid_str.isdigit():  # real problems are numeric IDs
            ids.append(pid_str)

    # unique + numeric sort
    return sorted(set(ids), key=int)


def main() -> None:
    if len(sys.argv) != 2:
        die('Usage: python metactf_event_index.py "https://compete.metactf.com/<event_id>/problems"')

    problems_page_url = sys.argv[1]
    host, event_id = extract_event_id(problems_page_url)

    # The API endpoint used by the MetaCTF frontend to load problems
    api_url = f"https://{host}/{event_id}/api/problems_json.php"

    raw = curl_get(api_url, referer=problems_page_url).strip()

    if not raw:
        die("Empty response from API (cookies.txt missing/invalid?)")

    if raw.startswith(b"<"):
        first_line = raw.splitlines()[0][:200].decode(errors="ignore")
        die(f"Got HTML instead of JSON (auth/endpoint issue). First line: {first_line}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"JSON parse failed: {e}")

    ids = get_problem_ids_only(data)
    if not ids:
        die("No numeric problem IDs found in the response")

    urls = [f"https://{host}/{event_id}/problem?p={pid}" for pid in ids]

    out_file = Path.cwd() / f"metactf_{event_id}_problems.txt"
    out_file.write_text("\n".join(urls) + "\n", encoding="utf-8")

    for url in urls:
        print(url)
    print(f"[+] Saved {len(urls)} URLs to {out_file}")


if __name__ == "__main__":
    main()
