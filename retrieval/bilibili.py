#!/usr/bin/env python3
"""Bilibili native search client for trend retrieval.

Unlike the hosted search APIs (tavily/exa/firecrawl), Bilibili's web search API is
**key-free** and returns *structured engagement* directly — play count, likes,
favorites, danmaku (弹幕), and publish time. That makes it the strongest real
source for video / anime / 国漫 trends (e.g. 《完美世界》), and it needs no signup.

The one catch: the API rejects requests without a `buvid3` cookie, so we warm up
a requests.Session against bilibili.com first to pick the cookie up, then search.

与 tavily/exa/firecrawl 不同，B站搜索 API **免密钥**，且直接返回结构化互动量
（播放/点赞/收藏/弹幕 + 发布时间），是视频 / 动漫 / 国漫类热点最强的真实数据源。
唯一注意点：API 需要 buvid3 cookie，先访问 bilibili.com 预热 Session 取 cookie，再搜索。

用法 / Usage:
    python bilibili.py --query "完美世界" --limit 10
    python bilibili.py --query "..." --output /tmp/bili.json
"""

import argparse
import json
import sys
import time
from datetime import datetime

import requests

try:
    from . import _common
except ImportError:  # run as a standalone script, not a package module
    import _common


WARMUP_URL = "https://www.bilibili.com"
SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
TIMEOUT = 20

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}


def _new_session(session=None):
    """Return a warmed-up session holding the buvid3 cookie the search API needs.

    `session` is injectable for tests so no real warmup request is made.
    """
    if session is not None:
        return session
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    try:
        session.get(WARMUP_URL, timeout=TIMEOUT)  # sets buvid3 / b_nut cookies
    except requests.RequestException:
        pass  # search may still work; let it surface a real error if not
    return session


def _published_iso(pubdate) -> str:
    """Convert a Bilibili unix pubdate to an ISO date string, or '' if absent."""
    try:
        return datetime.fromtimestamp(int(pubdate)).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def search(query: str, api_key=None, limit: int = 10, platform: str = "",
           session=None) -> dict:
    """Search Bilibili videos and return a normalized envelope with engagement.

    `api_key` is accepted for a uniform provider signature but ignored (key-free).
    Each result carries an `engagement` dict (likes/comments/saves/shares mapped
    from like/danmaku/favorites/play-derived signals) and `published`, so the
    dispatcher can rank by real traction without crawling pages.
    """
    session = _new_session(session)
    params = {"search_type": "video", "keyword": query, "page": 1}

    def do_request():
        return session.get(SEARCH_URL, params=params, timeout=TIMEOUT)

    response = _common.request_with_retry(do_request)
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        raise RuntimeError(f"bilibili search error: code={data.get('code')} msg={data.get('message')}")

    raw = (data.get("data") or {}).get("result") or []
    results = []
    for item in raw[:limit]:
        # Bilibili wraps matched terms in <em> tags; strip them for a clean title.
        title = item.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
        result = _common.make_result(
            title=title,
            url=item.get("arcurl") or item.get("url", ""),
            snippet=item.get("description", "") or item.get("desc", ""),
            score=item.get("play"),  # play count as the provider's own relevance signal
            published=_published_iso(item.get("pubdate")),
        )
        # Structured engagement straight from the API — no HTML scraping needed.
        # Map Bilibili's signals onto our common engagement fields:
        #   like → likes, video_review/danmaku → comments, favorites → saves,
        #   share → shares (absent in search, left None).
        result["engagement"] = {
            "likes": item.get("like"),
            "comments": item.get("video_review") if item.get("video_review") is not None
                        else item.get("danmaku"),
            "saves": item.get("favorites"),
            "shares": item.get("share"),
            "views": item.get("play"),
        }
        result["author"] = item.get("author", "")
        _common.fill_identity(result, platform or "bilibili")
        result["play"] = item.get("play")
        results.append(result)

    envelope = _common.make_envelope(query, platform or "bilibili", "bilibili", results)
    return envelope


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bilibili native trend search (key-free)")
    parser.add_argument("--query", required=True, help="search keyword")
    parser.add_argument("--platform", default="bilibili", help="platform tag for the envelope")
    parser.add_argument("--limit", type=int, default=10, help="max results")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    try:
        envelope = search(args.query, limit=args.limit, platform=args.platform)
    except Exception as exc:
        print(f"bilibili retrieval failed: {exc}", file=sys.stderr)
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
