#!/usr/bin/env python3
"""Firecrawl search client for trend retrieval.

Thin REST wrapper over the Firecrawl Search API. Returns results normalized to
the shared schema (title / url / snippet / score / published).

用法 / Usage:
    python firecrawl.py --query "linkedin career growth post" --platform linkedin --limit 10
    python firecrawl.py --query "..." --output /tmp/firecrawl.json

API key resolved from env TREND_FIRECRAWL_API_KEY or ~/.trend-improver/config.json.
"""

import argparse
import json
import sys

import requests

try:
    from . import _common
except ImportError:  # run as a standalone script, not a package module
    import _common


API_URL = "https://api.firecrawl.dev/v1/search"
TIMEOUT = 60  # Firecrawl can be slower as it crawls pages


def search(query: str, api_key: str, limit: int = 10, platform: str = "") -> dict:
    """Query Firecrawl and return a normalized envelope.

    Raises requests.HTTPError on non-2xx (other than 429, which is retried).
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"query": query, "limit": limit}

    def do_request():
        return requests.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT)

    response = _common.request_with_retry(do_request)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("data", []):
        # Firecrawl nests page metadata under "metadata".
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
        results.append(
            _common.make_result(
                title=item.get("title") or metadata.get("title", ""),
                url=item.get("url") or metadata.get("sourceURL", ""),
                snippet=item.get("description") or metadata.get("description", ""),
                score=None,  # Firecrawl search doesn't return a relevance score
                published=metadata.get("publishedTime", ""),
            )
        )

    return _common.make_envelope(query, platform, "firecrawl", results)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Firecrawl trend search client")
    parser.add_argument("--query", required=True, help="search query")
    parser.add_argument("--platform", default="", help="target platform tag")
    parser.add_argument("--limit", type=int, default=10, help="max results")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    api_key = _common.get_api_key("firecrawl")
    if not api_key:
        print("No Firecrawl API key configured (TREND_FIRECRAWL_API_KEY).", file=sys.stderr)
        return 2

    envelope = search(args.query, api_key, limit=args.limit, platform=args.platform)
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
