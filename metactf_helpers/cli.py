from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import shutil
import subprocess
from typing import Iterable, List, Optional

from .event_index import fetch_problem_urls, write_problem_list
from .http_client import HttpError, make_session
from .parsing import extract_event_info
from .problem_fetcher import ProblemResult, fetch_problem


def _positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def _read_list_file(path: Path) -> List[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def _load_urls(source: str, *, cookies: Path, session) -> tuple[List[str], Optional[Path]]:
    """
    Load URLs from either a file path or problems URL.

    Returns (urls, list_file_path_if_created).
    """
    potential_path = Path(source)
    if potential_path.exists():
        return _read_list_file(potential_path), potential_path

    urls = fetch_problem_urls(source, cookies_path=cookies, session=session)
    host, event_id = extract_event_info(source)
    out_file = write_problem_list(urls, event_id)
    return urls, out_file


def _open_folders(paths: Iterable[Path], *, code_bin: str, new_window: bool) -> int:
    if not shutil.which(code_bin):
        print(f"[!] VS Code CLI not found: {code_bin}", file=sys.stderr)
        return 1

    visited = set()
    rc = 0
    for path in paths:
        resolved = Path(path).resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        if not resolved.exists():
            print(f"[!] Cannot open missing folder: {resolved}", file=sys.stderr)
            rc = 1
            continue

        cmd = [code_bin]
        if new_window:
            cmd.append("-n")
        cmd.append(str(resolved))
        subprocess.run(cmd, check=False)

    return rc


def _add_index_parser(subparsers):
    parser = subparsers.add_parser("index", help="Fetch problem URLs for an event problems page")
    parser.add_argument("problems_url", help="https://compete.metactf.com/<event_id>/problems")
    parser.add_argument("--cookies", default="cookies.txt", type=Path, help="Path to cookies.txt (default: ./cookies.txt)")
    parser.add_argument("--output", type=Path, help="Optional output file path for the URL list")
    parser.set_defaults(func=handle_index)


def _add_fetch_parser(subparsers):
    parser = subparsers.add_parser("fetch", help="Fetch a single MetaCTF problem")
    parser.add_argument("problem_url", help="https://compete.metactf.com/<event_id>/problem?p=<id>")
    parser.add_argument("--cookies", default="cookies.txt", type=Path, help="Path to cookies.txt (default: ./cookies.txt)")
    parser.add_argument("--dest", default=Path("CTFProblems"), type=Path, help="Destination root directory (default: CTFProblems)")
    parser.add_argument("--skip-downloads", action="store_true", help="Do not download linked files")
    parser.add_argument("--open-folder", action="store_true", help="Open the downloaded folder in VS Code")
    parser.add_argument("--code-bin", default="code", help="VS Code command (default: code)")
    parser.add_argument("--code-new-window", action="store_true", help="Open folder in a new VS Code window")
    parser.set_defaults(func=handle_fetch)


def _add_fetch_all_parser(subparsers):
    parser = subparsers.add_parser(
        "fetch-all",
        help="Fetch all problems from a problems URL or prebuilt list file",
    )
    parser.add_argument(
        "source",
        help="Event problems URL (https://.../<event_id>/problems) or list file with one URL per line",
    )
    parser.add_argument("--cookies", default="cookies.txt", type=Path, help="Path to cookies.txt (default: ./cookies.txt)")
    parser.add_argument("--dest", default=Path("CTFProblems"), type=Path, help="Destination root directory (default: CTFProblems)")
    parser.add_argument("--concurrency", default=None, type=_positive_int, help="Number of concurrent fetches (default: CPU count)")
    parser.add_argument("--skip-downloads", action="store_true", help="Do not download linked files")
    parser.add_argument("--open-folders", action="store_true", help="Open each fetched folder in VS Code")
    parser.add_argument("--code-bin", default="code", help="VS Code command (default: code)")
    parser.add_argument("--code-new-window", action="store_true", help="Open each folder in a new VS Code window")
    parser.set_defaults(func=handle_fetch_all)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MetaCTF helper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_index_parser(subparsers)
    _add_fetch_parser(subparsers)
    _add_fetch_all_parser(subparsers)
    return parser


def handle_index(args) -> int:
    try:
        session = make_session(args.cookies)
        urls = fetch_problem_urls(args.problems_url, cookies_path=args.cookies, session=session)
        host, event_id = extract_event_info(args.problems_url)
        out_file = write_problem_list(urls, event_id, args.output)
    except (HttpError, OSError, ValueError, RuntimeError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    for url in urls:
        print(url)
    print(f"[+] Saved {len(urls)} URLs to {out_file}")
    return 0


def handle_fetch(args) -> int:
    try:
        result = fetch_problem(
            args.problem_url,
            cookies_path=args.cookies,
            root_dir=args.dest,
            download_links=not args.skip_downloads,
        )
    except (HttpError, OSError, ValueError, RuntimeError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    print(result.console_output, end="")
    if result.links_file:
        print(f"[+] Saved to {result.problem_file} (links in {result.links_file.name})")
    else:
        print(f"[+] Saved to {result.problem_file} (no links found)")
    if args.open_folder:
        return _open_folders([result.out_dir], code_bin=args.code_bin, new_window=args.code_new_window)
    return 0


def _print_fetch_all_result(result: ProblemResult) -> None:
    links_note = "links saved" if result.links_file else "no links"
    container_note = "container notice" if result.container_notice else "no container"
    line = f"[+] p={result.problem_id} -> {result.problem_file} ({links_note}; {container_note})"
    if result.container_notice:
        red, reset = "\033[31m", "\033[0m"
        line = f"{red}{line}{reset}"
    print(line)


def handle_fetch_all(args) -> int:
    concurrency = args.concurrency or (os.cpu_count() or 4)
    try:
        session = make_session(args.cookies)
        urls, list_file = _load_urls(args.source, cookies=args.cookies, session=session)
    except (HttpError, OSError, ValueError, RuntimeError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    if not urls:
        print("[!] No URLs found to fetch", file=sys.stderr)
        return 1

    if list_file:
        print(f"[*] Using list: {list_file}")
    print(f"[*] Fetching {len(urls)} problem(s) with concurrency={concurrency}")

    failures: list[tuple[str, Exception]] = []
    results: list[ProblemResult] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(
                fetch_problem,
                url,
                cookies_path=args.cookies,
                root_dir=args.dest,
                download_links=not args.skip_downloads,
            ): url
            for url in urls
        }

        for future in as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append((url, exc))
                print(f"[!] Failed: {url} -> {exc}", file=sys.stderr)
                continue
            results.append(result)
            _print_fetch_all_result(result)

    if failures:
        print(f"[!] {len(failures)} problem(s) failed. See logs above.", file=sys.stderr)
        return 1

    if args.open_folders and results:
        rc = _open_folders((r.out_dir for r in results), code_bin=args.code_bin, new_window=args.code_new_window)
        if rc != 0:
            return rc

    print("[+] Done.")
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
