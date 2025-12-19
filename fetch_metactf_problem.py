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


def detect_container_notice(*chunks):
    patterns = [
        r"container\s+spawn",
        r"container\s+spawned",
        r"spawning\s+container",
        r"container\s+started",
        r"container\s+ready",
        r"container\s+will\s+be\s+ready",
        r"your\s+container",
        r"container\s+may\s+take",
        r"container\s+running",
        r"container\s+initializing",
    ]
    js_markers = (
        "getchaldetails",
        "getchaldetails2",
        "setinterval(() => getchaldetails2",
        "loading ...",
    )
    for chunk in chunks:
        if not chunk:
            continue
        lower = chunk.lower()
        for pat in patterns:
            if re.search(pat, lower):
                return "Container spawn message detected; manual action may be required."
        for marker in js_markers:
            if marker in lower:
                return "Dynamic challenge content detected (likely container/polling); open in browser to spawn/manage the container."
    return None


def detect_category(problem, *chunks):
    # Prefer explicit category fields from the API
    for key in ("category", "cat", "topic", "type", "domain", "challengeType"):
        val = problem.get(key)
        if isinstance(val, (list, tuple)):
            val = ", ".join(str(v) for v in val if v)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Heuristic keywords fallback
    text = " ".join(c for c in chunks if c).lower()
    keyword_map = {
        "web": ["http", "cookie", "xss", "sqli", "sql", "csrf", "cors", "lfi", "rfi", "web"],
        "crypto": ["rsa", "cipher", "encrypt", "decrypt", "crypto", "aes", "xor", "hash", "modulus"],
        "reverse": ["reverse", "disasm", "decompile", "binary", "elf", "ghidra", "ida"],
        "pwn": ["overflow", "fmtstr", "heap", "stack", "shellcode", "ret2", "rop", "pwn"],
        "forensics": ["pcap", "memory", "forensic", "disk", "image", "artifact"],
        "osint": ["twitter", "social", "osint", "linkedin", "geo", "exif"],
    }
    for cat, keywords in keyword_map.items():
        if any(k in text for k in keywords):
            return cat

    return None

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
category = detect_category(problem, title, desc)
problem_slug = re.sub(r'[^a-zA-Z0-9._-]+', '_', title.strip())
problem_slug = re.sub(r'_+', '_', problem_slug).strip("_") or f"problem_{problem_id}"
root_dir = Path.cwd() / "CTFProblems"
root_dir.mkdir(parents=True, exist_ok=True)

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

# ---- Detect container spawn hints ----
container_notice = detect_container_notice(desc, text)

# ---- Build base problem text ----
separator = "=" * 60
problem_lines = [separator, title, separator]
if category:
    problem_lines.append(f"Category: {category}")
problem_lines.append(text)
if container_notice:
    problem_lines.extend(["", f"NOTE: {container_notice}"])
problem_lines.append("")

out_dir = (root_dir / "Containerized" / problem_slug) if container_notice else (root_dir / problem_slug)
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
if container_notice:
    summaries.append(container_notice)

if summaries:
    problem_lines.extend(summaries)

output_text = "\n".join(problem_lines).rstrip() + "\n"

# ---- Build console output (add red color for warnings) ----
console_output_text = output_text
if container_notice:
    red, reset = "\033[31m", "\033[0m"
    console_lines = []
    for line in problem_lines:
        if container_notice in line or line.strip().startswith("NOTE:"):
            console_lines.append(f"{red}{line}{reset}")
        else:
            console_lines.append(line)
    console_output_text = "\n".join(console_lines).rstrip() + "\n"

# ---- Save to problem.txt ----
out_file = out_dir / "problem.txt"
out_file.write_text(output_text, encoding="utf-8")

# ---- Output ----
print(console_output_text, end="")
if links_file:
    print(f"[+] Saved to {out_file} (links in {links_file})")
else:
    print(f"[+] Saved to {out_file} (no links found)")
