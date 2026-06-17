#!/usr/bin/env python3
"""crawl4ai client for trend retrieval.

Unlike the other providers, crawl4ai is a locally installed Python library, not a
hosted API. It crawls given URLs and extracts content. We lazy-import it so the
rest of the retrieval layer works without it installed, mirroring how the
reference repo treats optional playwright.

用法 / Usage:
    python crawl4ai.py --url https://example.com/trending --platform xiaohongshu
    python crawl4ai.py --url "..." --output /tmp/crawl.json

Install with: pip install crawl4ai
"""

import argparse
import asyncio
import json
import sys

try:
    from . import _common
except ImportError:  # run as a standalone script, not a package module
    import _common


def _require_crawl4ai():
    """Import the crawl4ai library lazily; friendly error if it isn't installed.

    This file is itself named crawl4ai.py, so when run as a standalone script its
    own directory sits on sys.path[0] and a bare `import crawl4ai` would re-import
    this module instead of the installed library. We drop our own directory from
    sys.path for the import to make sure we get the real package.
    """
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    saved_path = [p for p in sys.path]
    sys.path = [p for p in sys.path if os.path.abspath(p or ".") != here]
    sys.modules.pop("crawl4ai", None)  # clear any self-shadowed entry
    try:
        import crawl4ai
    except ImportError as exc:
        raise RuntimeError(
            "crawl4ai is not installed. Install it with: pip install crawl4ai"
        ) from exc
    finally:
        sys.path = saved_path

    if not hasattr(crawl4ai, "AsyncWebCrawler"):
        raise RuntimeError(
            "crawl4ai is not installed. Install it with: pip install crawl4ai"
        )
    return crawl4ai


async def _crawl(urls: list, platform: str = "") -> dict:
    """Crawl the given URLs with crawl4ai and normalize the output."""
    crawl4ai = _require_crawl4ai()
    AsyncWebCrawler = crawl4ai.AsyncWebCrawler

    results = []
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            page = await crawler.arun(url=url)
            # crawl4ai exposes extracted markdown and page metadata.
            metadata = getattr(page, "metadata", {}) or {}
            result = _common.make_result(
                title=metadata.get("title", ""),
                url=url,
                snippet=(getattr(page, "markdown", "") or "")[:500],
                score=None,
                published=metadata.get("published", ""),
            )
            author = metadata.get("author") or metadata.get("creator") or metadata.get("site_name")
            if author:
                result["author"] = author
            _common.fill_identity(result, platform)
            results.append(result)

    query = " ".join(urls)
    return _common.make_envelope(query, platform, "crawl4ai", results)


def search(urls: list, platform: str = "") -> dict:
    """Synchronous entry point: crawl the URLs and return a normalized envelope."""
    return asyncio.run(_crawl(urls, platform=platform))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="crawl4ai trend crawler")
    parser.add_argument("--url", action="append", required=True, help="URL to crawl (repeatable)")
    parser.add_argument("--platform", default="", help="target platform tag")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        envelope = search(args.url, platform=args.platform)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output = json.dumps(envelope, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(envelope['results'])} results to {args.output}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
