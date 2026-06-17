#!/usr/bin/env python3
"""Weibo native search client for trend retrieval.

Uses the public m.weibo.cn search JSON endpoint and normalizes posts with
structured engagement: attitudes (likes), comments, and reposts (shares). This
is key-free and does not drive the user's browser, so it behaves like the
Bilibili native provider from the dispatcher's point of view.
"""

import argparse
import json
import re
import sys

import requests

try:
    from . import _common
except ImportError:  # run as a standalone script, not a package module
    import _common


API_URL = "https://m.weibo.cn/api/container/getIndex"
TIMEOUT = 20

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    ),
    "Referer": "https://m.weibo.cn/search",
    "Accept": "application/json, text/plain, */*",
}


def _strip_html(text: str) -> str:
    """Strip Weibo's highlighted HTML while preserving readable text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def _iter_mblogs(cards):
    """Yield mblog dicts from Weibo's nested card tree."""
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        mblog = card.get("mblog")
        if isinstance(mblog, dict):
            yield mblog
        yield from _iter_mblogs(card.get("card_group"))


def _post_url(mblog: dict) -> str:
    if mblog.get("scheme"):
        return mblog["scheme"]
    bid = mblog.get("bid") or mblog.get("mblogid") or mblog.get("id")
    return f"https://m.weibo.cn/detail/{bid}" if bid else ""


def search(query: str, api_key=None, limit: int = 10, platform: str = "",
           session=None) -> dict:
    """Search Weibo posts and return a normalized envelope with engagement."""
    session = session or requests.Session()
    session.headers.update(_HEADERS)
    params = {
        "containerid": f"100103type=1&q={query}",
        "page_type": "searchall",
        "page": 1,
    }

    def do_request():
        return session.get(API_URL, params=params, timeout=TIMEOUT)

    response = _common.request_with_retry(do_request)
    response.raise_for_status()
    data = response.json()
    if data.get("ok") not in (1, "1", True):
        raise RuntimeError(f"weibo search error: ok={data.get('ok')} msg={data.get('msg')}")

    cards = (data.get("data") or {}).get("cards") or []
    results = []
    seen = set()
    for mblog in _iter_mblogs(cards):
        mid = mblog.get("id") or mblog.get("mblogid") or mblog.get("bid")
        if not mid or mid in seen:
            continue
        seen.add(mid)

        text = mblog.get("text_raw") or _strip_html(mblog.get("text", ""))
        if not text:
            continue
        user = mblog.get("user") or {}
        result = _common.make_result(
            title=text[:80],
            url=_post_url(mblog),
            snippet=text[:240],
            score=mblog.get("attitudes_count"),
            published=mblog.get("created_at", ""),
        )
        result["engagement"] = {
            "likes": mblog.get("attitudes_count"),
            "comments": mblog.get("comments_count"),
            "saves": None,
            "shares": mblog.get("reposts_count"),
            "views": mblog.get("reads_count"),
        }
        result["author"] = user.get("screen_name", "")
        _common.fill_identity(result, platform or "weibo")
        results.append(result)
        if len(results) >= limit:
            break

    return _common.make_envelope(query, platform or "weibo", "weibo", results)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Weibo native trend search (key-free)")
    parser.add_argument("--query", required=True, help="search keyword")
    parser.add_argument("--platform", default="weibo", help="platform tag for the envelope")
    parser.add_argument("--limit", type=int, default=10, help="max results")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        envelope = search(args.query, limit=args.limit, platform=args.platform)
    except Exception as exc:
        print(f"weibo retrieval failed: {exc}", file=sys.stderr)
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
