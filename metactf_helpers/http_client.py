from __future__ import annotations

import re
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Mapping, MutableMapping, Optional
from urllib.parse import urlparse

import requests


class HttpError(RuntimeError):
    """Raised for HTTP/JSON parsing issues."""


DEFAULT_HEADERS: Mapping[str, str] = {
    "User-Agent": "MetaCTF-Helper/1.0",
    "X-Requested-With": "XMLHttpRequest",
}


def load_cookies(cookies_path: Path) -> MozillaCookieJar:
    """
    Load a Netscape-format cookies.txt file.

    Raises FileNotFoundError when the file does not exist.
    """
    cookies_path = Path(cookies_path)
    if not cookies_path.exists():
        raise FileNotFoundError(f"cookies.txt not found at {cookies_path}")

    jar = MozillaCookieJar()
    jar.load(str(cookies_path), ignore_discard=True, ignore_expires=True)
    return jar


def make_session(
    cookies_path: Path,
    *,
    extra_headers: Optional[MutableMapping[str, str]] = None,
) -> requests.Session:
    """Create a requests Session with cookies and baseline headers."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if extra_headers:
        session.headers.update(extra_headers)
    session.cookies.update(load_cookies(cookies_path))
    return session


def fetch_json(
    session: requests.Session,
    url: str,
    *,
    referer: Optional[str] = None,
) -> object:
    """GET JSON and guard against HTML/auth failures."""
    headers = {"Referer": referer} if referer else {}
    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    text = resp.text.lstrip()
    if text.startswith("<"):
        raise HttpError("HTML response received (auth issue or wrong endpoint).")

    try:
        return resp.json()
    except ValueError as exc:
        raise HttpError(f"Failed to parse JSON from {url}: {exc}") from exc


def _filename_from_response(resp: requests.Response, url: str) -> str:
    cd = resp.headers.get("content-disposition")
    if cd:
        match = re.search(r'filename\*?="?([^";]+)"?', cd, flags=re.I)
        if match:
            candidate = Path(match.group(1)).name
            if candidate:
                return candidate

    parsed = urlparse(url)
    fallback = Path(parsed.path).name
    return fallback or "download"


def download_file(session: requests.Session, url: str, dest_dir: Path) -> Path:
    """Download a file with cookies and save to dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    resp = session.get(url, stream=True, allow_redirects=True, timeout=60)
    resp.raise_for_status()

    filename = _filename_from_response(resp, url)
    output_path = dest_dir / filename

    with output_path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)

    return output_path

