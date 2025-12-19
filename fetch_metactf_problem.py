#!/usr/bin/env python3

import sys
import re
import json
import subprocess
import shutil
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urljoin

def die(msg):
    print(f"[!] {msg}")
    sys.exit(1)

if len(sys.argv) != 2:
    die("Usage: python fetch_metactf_problem.py <problem_url>")

problem_url = sys.argv[1]

# ---- Parse URL ----
parsed = urlparse(problem_url)
qs = parse_qs(parsed.query)

if "p" not in qs:
    die("URL must contain ?p=<problem_id>")

problem_id = qs["p"][0]
path_parts = parsed.path.strip("/").split("/")

if len(path_parts) < 1 or not path_parts[0].isdigit():
    die("Could not determine event ID from URL")

event_id = path_parts[0]

api_url = f"https://{parsed.netloc}/{event_id}/api/problems_json.php"

# ---- Fetch JSON using curl + cookies.txt ----
curl_cmd = [
    "curl",
    "-s",
    "--cookie", "cookies.txt",
    "-H", "X-Requested-With: XMLHttpRequest",
    "-H", f"Referer: {problem_url}",
    api_url
]

try:
    raw = subprocess.check_output(curl_cmd)
except subprocess.CalledProcessError:
    die("curl failed (check cookies.txt)")

if not raw.strip():
    die("Empty response from API")

if raw.lstrip().startswith(b"<"):
    die("Got HTML instead of JSON (auth failure or wrong endpoint)")

data = json.loads(raw)

# ---- Normalize JSON structure ----
items = data.get("problems") if isinstance(data, dict) else data
if not isinstance(items, list):
    die("Unexpected JSON structure")

# ---- Find problem ----
problem = None
for p in items:
    if str(p.get("id")) == problem_id:
        problem = p
        break

if not problem:
    die(f"Problem ID {problem_id} not found")

title = problem.get("name") or problem.get("title") or ""
desc  = problem.get("description") or problem.get("prompt") or problem.get("body") or ""
problem_slug = re.sub(r'[^a-zA-Z0-9._-]+', '_', title.strip())
problem_slug = re.sub(r'_+', '_', problem_slug).strip("_") or f"problem_{problem_id}"

# ---- Extract links ----
raw_links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', desc, flags=re.I)
links = []
seen = set()
for l in raw_links:
    full = urljoin(problem_url, l.strip())
    if full and full not in seen:
        links.append(full)
        seen.add(full)

# ---- Strip HTML for readable text ----
text = desc
text = re.sub(r'<\s*br\s*/?\s*>', '\n', text, flags=re.I)
text = re.sub(r'</p\s*>', '\n\n', text, flags=re.I)
text = re.sub(r'<[^>]+>', '', text)
text = re.sub(r'\n{3,}', '\n\n', text).strip()

# ---- Build base problem text ----
separator = "=" * 60
problem_lines = [separator, title, separator, text]
problem_lines.append("")

out_dir = Path.cwd() / problem_slug
out_dir.mkdir(parents=True, exist_ok=True)

# ---- Download linked files ----
downloaded = []
failed_downloads = []
if links:
    if not shutil.which("wget"):
        die("wget not found in PATH (install it to auto-download links)")
    for link in links:
        cmd = [
            "wget",
            "-q",
            "--content-disposition",
            "-nd",
            "-P", str(out_dir),
            link,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            downloaded.append(link)
        else:
            err = (result.stderr or result.stdout or "wget failed").strip()
            failed_downloads.append((link, err))

# ---- Save links to separate file ----
links_file = None
if links:
    links_lines = []
    links_lines.append("Links:")
    downloaded_set = set(downloaded)
    failed_map = {l: err for l, err in failed_downloads}
    for l in links:
        status = []
        if l in downloaded_set:
            status.append("downloaded")
        if l in failed_map:
            status.append(f"download failed: {failed_map[l]}")
        suffix = f" ({'; '.join(status)})" if status else ""
        links_lines.append(f"- {l}{suffix}")

    links_text = "\n".join(links_lines).rstrip() + "\n"
    links_file = out_dir / "links.txt"
    links_file.write_text(links_text, encoding="utf-8")

# ---- Add summaries to problem text (no links) ----
summaries = []
if links_file:
    summaries.append(f"Links saved to {links_file.name}")
if downloaded:
    summaries.append(f"Downloaded {len(downloaded)} link(s) with wget into {out_dir}")
if failed_downloads:
    summaries.append(f"{len(failed_downloads)} download(s) failed; see {links_file.name}")

if summaries:
    problem_lines.extend(summaries)

output_text = "\n".join(problem_lines).rstrip() + "\n"

# ---- Save to problem.txt ----
out_file = out_dir / "problem.txt"
out_file.write_text(output_text, encoding="utf-8")

# ---- Output ----
print(output_text, end="")
if links_file:
    print(f"[+] Saved to {out_file} (links in {links_file})")
else:
    print(f"[+] Saved to {out_file} (no links found)")
