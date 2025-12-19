from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse


def extract_event_info(problems_url: str) -> Tuple[str, str]:
    """
    Return (host, event_id) from a MetaCTF problems URL.

    Expected: https://compete.metactf.com/<event_id>/problems
    """
    parsed = urlparse(problems_url)
    parts = parsed.path.strip("/").split("/")

    if len(parts) < 2 or parts[1] != "problems" or not parts[0].isdigit():
        raise ValueError("URL must look like: https://compete.metactf.com/<event_id>/problems")
    if not parsed.netloc:
        raise ValueError("Invalid URL (missing host)")

    return parsed.netloc, parts[0]


def parse_problem_url(problem_url: str) -> Tuple[str, str, str]:
    """
    Return (host, event_id, problem_id) for a single problem URL.

    Expected: https://compete.metactf.com/<event_id>/problem?p=<numeric_id>
    """
    parsed = urlparse(problem_url)
    qs = parse_qs(parsed.query)
    if "p" not in qs:
        raise ValueError("URL must contain ?p=<problem_id>")

    pid = qs["p"][0]
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 1 or not parts[0].isdigit():
        raise ValueError("Could not determine event ID from URL")
    if not parsed.netloc:
        raise ValueError("Invalid URL (missing host)")

    return parsed.netloc, parts[0], pid


def slugify(text: str, *, fallback: str = "problem") -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", text.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or fallback


def detect_category(problem: dict, *chunks: str) -> Optional[str]:
    # Prefer explicit category fields from the API
    for key in ("category", "cat", "topic", "type", "domain", "challengeType"):
        val = problem.get(key)
        if isinstance(val, (list, tuple)):
            val = ", ".join(str(v) for v in val if v)
        if isinstance(val, str) and val.strip():
            return val.strip()

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


def detect_container_notice(*chunks: str) -> Optional[str]:
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


def html_to_text(html: str) -> str:
    """Coarse HTML-to-text conversion for problem statements."""
    text = html or ""
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self.links.append(urljoin(self.base_url, href.strip()))


def gather_links(html: str, base_url: str) -> List[str]:
    extractor = _LinkExtractor(base_url)
    extractor.feed(html or "")
    seen = set()
    links: List[str] = []
    for link in extractor.links:
        if link not in seen:
            links.append(link)
            seen.add(link)
    return links

