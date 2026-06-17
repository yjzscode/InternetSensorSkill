#!/usr/bin/env python3
"""Fetch and extract user-provided source links.

This is separate from trend retrieval: source links are factual grounding for the
user's own content (papers, docs, articles), not viral examples to imitate.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover - requirements include requests
    requests = None

try:
    from . import engagement
except ImportError:  # run as a standalone script, not a package module
    import engagement


URL_RE = re.compile(r"https?://[^\s<>)\"'，。；、]+", re.IGNORECASE)
TIMEOUT = 30


def extract_urls(text: str) -> list:
    """Return unique http(s) URLs from text, trimming common trailing punctuation."""
    urls = []
    seen = set()
    for match in URL_RE.findall(text or ""):
        url = match.rstrip(".,;:!?)]}）】")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _is_pdf(url: str, content_type: str = "") -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".pdf") or "pdf" in (content_type or "").lower()


def _extract_pdf_with_library(data: bytes) -> str:
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
        except ImportError:
            continue
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(data)
                tmp.flush()
                reader = module.PdfReader(tmp.name)
                pages = []
                for page in reader.pages:
                    pages.append(page.extract_text() or "")
                return "\n".join(pages)
        except Exception:
            continue
    return ""


def _extract_pdf_with_pdftotext(data: bytes) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as src, tempfile.NamedTemporaryFile(suffix=".txt") as dst:
        src.write(data)
        src.flush()
        try:
            subprocess.run([exe, src.name, dst.name], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            return Path(dst.name).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


def extract_pdf_text(data: bytes) -> str:
    return _extract_pdf_with_library(data) or _extract_pdf_with_pdftotext(data)


def _clean_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:max_chars]


def _section(pattern: str, text: str, max_chars: int = 1200) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _clean_text(match.group(1), max_chars)


def extract_key_sections(text: str) -> dict:
    """Best-effort academic-paper sections."""
    normalized = re.sub(r"\r", "\n", text or "")
    title = ""
    lines = [ln.strip() for ln in normalized.splitlines() if ln.strip()]
    for line in lines[:20]:
        if len(line) > 12 and not re.fullmatch(r"\d+|abstract|arxiv.*", line, flags=re.I):
            title = line[:240]
            break
    abstract = _section(r"\babstract\b\s*(.*?)(?:\b1\s+introduction\b|\bintroduction\b)", normalized)
    introduction = _section(r"\b(?:1\s+)?introduction\b\s*(.*?)(?:\b2\s+|\brelated work\b|\bmethod\b)", normalized)
    conclusion = _section(r"\b(?:conclusion|conclusions)\b\s*(.*?)(?:\breferences\b|$)", normalized)
    return {
        "title_guess": title,
        "abstract": abstract,
        "introduction_excerpt": introduction,
        "conclusion_excerpt": conclusion,
    }


def fetch_source(url: str, timeout: int = TIMEOUT, max_chars: int = 12000,
                 fetcher=None) -> dict:
    """Fetch one source URL and return a normalized source record."""
    record = {
        "url": url,
        "status": "error",
        "content_type": "",
        "kind": "unknown",
        "text_excerpt": "",
        "key_sections": {},
        "error": "",
    }
    if requests is None and fetcher is None:
        record["error"] = "requests is not installed"
        return record
    fetcher = fetcher or (lambda u: requests.get(u, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    }))
    try:
        response = fetcher(url)
        status_code = getattr(response, "status_code", 200)
        if status_code >= 400:
            record["error"] = f"HTTP {status_code}"
            return record
        content_type = getattr(response, "headers", {}).get("content-type", "")
        record["content_type"] = content_type
        data = getattr(response, "content", b"") or b""
        if _is_pdf(url, content_type):
            record["kind"] = "pdf"
            text = extract_pdf_text(data)
        else:
            record["kind"] = "webpage"
            raw_text = getattr(response, "text", "") or data.decode("utf-8", errors="ignore")
            text = engagement.strip_html(raw_text)
        if not text.strip():
            record["error"] = "fetched but no extractable text"
            return record
        record["status"] = "ok"
        record["text_excerpt"] = _clean_text(text, max_chars)
        record["key_sections"] = extract_key_sections(text)
        return record
    except Exception as exc:
        record["error"] = str(exc)
        return record


def collect_sources(content: str, max_urls: int = 5, max_chars: int = 12000,
                    timeout: int = TIMEOUT) -> dict:
    urls = extract_urls(content)[:max_urls]
    return {
        "mode": "online" if urls else "none",
        "count": len(urls),
        "sources": [fetch_source(url, timeout=timeout, max_chars=max_chars) for url in urls],
    }


def write_output(data: dict, output: str) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch user-provided source links for factual grounding")
    parser.add_argument("--content", default="", help="raw content containing URLs")
    parser.add_argument("--content-file", default="", help="read raw content from a file")
    parser.add_argument("--output", default="", help="write source_links.json here")
    parser.add_argument("--max-urls", type=int, default=5)
    parser.add_argument("--max-chars", type=int, default=12000)
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    args = parser.parse_args(argv)

    content = args.content
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    data = collect_sources(content, max_urls=args.max_urls,
                           max_chars=args.max_chars, timeout=args.timeout)
    write_output(data, args.output)
    if args.output:
        ok = sum(1 for s in data["sources"] if s.get("status") == "ok")
        print(f"Wrote {len(data['sources'])} source links to {args.output} ({ok} ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
