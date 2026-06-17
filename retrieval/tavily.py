#!/usr/bin/env python3
"""Tavily search client for trend retrieval.

Thin REST wrapper over the Tavily Search API. Returns results normalized to the
shared schema (title / url / snippet / score / published).

用法 / Usage:
    python tavily.py --query "小红书 校园美食 爆款" --platform xiaohongshu --limit 10
    python tavily.py --query "..." --output /tmp/tavily.json

API key resolved from env TREND_TAVILY_API_KEY or ~/.trend-improver/config.json.
"""

import argparse
import json
import sys

import requests

try:
    from . import _common
except ImportError:  # run as a standalone script, not a package module
    import _common


API_URL = "https://api.tavily.com/search"
TIMEOUT = 30


def search(query: str, api_key: str, limit: int = 10, platform: str = "") -> dict:
    """Query Tavily and return a normalized envelope.

    Raises requests.HTTPError on non-2xx (other than 429, which is retried).
    """
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": limit,
        "search_depth": "advanced",
    }

    def do_request():
        return requests.post(API_URL, json=payload, timeout=TIMEOUT)

    response = _common.request_with_retry(do_request)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("results", []):
        results.append(
            _common.make_result(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                score=item.get("score"),
                published=item.get("published_date", ""),
            )
        )

    return _common.make_envelope(query, platform, "tavily", results)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tavily trend search client")
    parser.add_argument("--query", required=True, help="search query")
    parser.add_argument("--platform", default="", help="target platform tag")
    parser.add_argument("--limit", type=int, default=10, help="max results")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    api_key = _common.get_api_key("tavily")
    if not api_key:
        print("No Tavily API key configured (TREND_TAVILY_API_KEY).", file=sys.stderr)
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
