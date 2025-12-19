from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import requests

from .http_client import fetch_json, make_session
from .parsing import extract_event_info


def _extract_problem_ids(data: object) -> List[str]:
    """
    Extract numeric problem IDs from the API response.

    Expected JSON shapes:
      - { "problems": [ {...}, ... ] }
      - [ {...}, ... ]
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
        if pid_str.isdigit():
            ids.append(pid_str)

    return sorted(set(ids), key=int)


def fetch_problem_urls(
    problems_url: str,
    *,
    cookies_path: Path | str = "cookies.txt",
    session: Optional[requests.Session] = None,
) -> List[str]:
    """
    Return a list of problem URLs for a MetaCTF event problems page.

    Does not write files; callers may save the output.
    """
    host, event_id = extract_event_info(problems_url)
    session = session or make_session(Path(cookies_path))
    api_url = f"https://{host}/{event_id}/api/problems_json.php"
    data = fetch_json(session, api_url, referer=problems_url)
    ids = _extract_problem_ids(data)
    if not ids:
        raise RuntimeError("No numeric problem IDs found in the response")
    return [f"https://{host}/{event_id}/problem?p={pid}" for pid in ids]


def write_problem_list(urls: Iterable[str], event_id: str, output_path: Optional[Path] = None) -> Path:
    """Write URLs to a file; returns the resulting path."""
    out_file = output_path or Path.cwd() / f"metactf_{event_id}_problems.txt"
    out_file.write_text("\n".join(urls) + "\n", encoding="utf-8")
    return out_file

