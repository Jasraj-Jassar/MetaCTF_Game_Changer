from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import requests

from .http_client import download_file, fetch_json, make_session
from .parsing import (
    detect_category,
    detect_container_notice,
    gather_links,
    html_to_text,
    parse_problem_url,
    slugify,
)


@dataclass
class ProblemResult:
    problem_id: str
    title: str
    out_dir: Path
    problem_file: Path
    links_file: Optional[Path]
    downloaded: List[Path]
    failed_downloads: List[Tuple[str, str]]
    category: Optional[str]
    container_notice: Optional[str]
    console_output: str


def _pick_problem(items: Sequence[dict], problem_id: str) -> dict:
    for p in items:
        if str(p.get("id")) == problem_id:
            return p
    raise RuntimeError(f"Problem ID {problem_id} not found in API response")


def _normalize_problem_list(data: object) -> Sequence[dict]:
    items = data.get("problems") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("Unexpected JSON structure from API")
    return items


def _write_links_file(
    out_dir: Path,
    links: List[str],
    downloaded_map: dict[str, Path],
    failed: List[Tuple[str, str]],
) -> Path:
    lines = ["Links:"]
    for link in links:
        status: List[str] = []
        if link in downloaded_map:
            status.append(f"downloaded -> {downloaded_map[link].name}")
        for failed_link, err in failed:
            if failed_link == link:
                status.append(f"download failed: {err}")
        suffix = f" ({'; '.join(status)})" if status else ""
        lines.append(f"- {link}{suffix}")
    links_file = out_dir / "links.txt"
    links_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return links_file


def _render_problem_text(
    title: str,
    category: Optional[str],
    text: str,
    summaries: List[str],
    container_notice: Optional[str],
) -> Tuple[str, str]:
    separator = "=" * 60
    lines = [separator, title, separator]
    if category:
        lines.append(f"Category: {category}")
    lines.append(text)
    if container_notice:
        lines.extend(["", f"NOTE: {container_notice}"])
    lines.append("")
    if summaries:
        lines.extend(summaries)

    output_text = "\n".join(lines).rstrip() + "\n"

    if container_notice:
        red, reset = "\033[31m", "\033[0m"
        color_lines = []
        for line in lines:
            if container_notice in line or line.strip().startswith("NOTE:"):
                color_lines.append(f"{red}{line}{reset}")
            else:
                color_lines.append(line)
        console_output = "\n".join(color_lines).rstrip() + "\n"
    else:
        console_output = output_text

    return output_text, console_output


def fetch_problem(
    problem_url: str,
    *,
    cookies_path: Path | str = "cookies.txt",
    root_dir: Path | str = "CTFProblems",
    session: Optional[requests.Session] = None,
    download_links: bool = True,
) -> ProblemResult:
    host, event_id, problem_id = parse_problem_url(problem_url)

    root_dir = Path(root_dir)
    session = session or make_session(Path(cookies_path))

    api_url = f"https://{host}/{event_id}/api/problems_json.php"
    data = fetch_json(session, api_url, referer=problem_url)
    items = _normalize_problem_list(data)
    problem = _pick_problem(items, problem_id)

    title = problem.get("name") or problem.get("title") or f"problem_{problem_id}"
    desc = problem.get("description") or problem.get("prompt") or problem.get("body") or ""
    category = detect_category(problem, title, desc)
    text = html_to_text(desc)
    container_notice = detect_container_notice(desc, text)
    links = gather_links(desc, problem_url)

    slug = slugify(title, fallback=f"problem_{problem_id}")
    out_dir = (root_dir / "Containerized" / slug) if container_notice else (root_dir / slug)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded: List[Path] = []
    downloaded_map: dict[str, Path] = {}
    failed_downloads: List[Tuple[str, str]] = []
    if links and download_links:
        for link in links:
            try:
                path = download_file(session, link, out_dir)
                downloaded.append(path)
                downloaded_map[link] = path
            except Exception as exc:  # noqa: BLE001
                failed_downloads.append((link, str(exc)))

    links_file: Optional[Path] = None
    if links:
        links_file = _write_links_file(out_dir, links, downloaded_map, failed_downloads)

    summaries: List[str] = []
    if links_file:
        summaries.append(f"Links saved to {links_file.name}")
    if downloaded:
        summaries.append(f"Downloaded {len(downloaded)} link(s) into {out_dir}")
    if links and not download_links:
        summaries.append("Downloads skipped (links listed only)")
    if failed_downloads:
        summaries.append(f"{len(failed_downloads)} download(s) failed; see {links_file.name if links_file else 'links.txt'}")
    if container_notice:
        summaries.append(container_notice)

    problem_text, console_output = _render_problem_text(title, category, text, summaries, container_notice)

    out_file = out_dir / "problem.txt"
    out_file.write_text(problem_text, encoding="utf-8")

    return ProblemResult(
        problem_id=problem_id,
        title=title,
        out_dir=out_dir,
        problem_file=out_file,
        links_file=links_file,
        downloaded=downloaded,
        failed_downloads=failed_downloads,
        category=category,
        container_notice=container_notice,
        console_output=console_output,
    )
