#!/usr/bin/env python3
"""Key-free web search via SearXNG / DuckDuckGo — the open-source替代 keyed APIs.

Twitter/X and LinkedIn have no native key-free source like Bilibili, and the
hosted search APIs (Tavily/Exa/Firecrawl) all need a paid key. This provider is
the free, open-source path the user asked for: no signup, no API key.

Two strategies, tried in order:

  1. **SearXNG JSON** — if the user runs/points to a SearXNG instance (the OSS
     metasearch engine, https://github.com/searxng/searxng) that allows the JSON
     output format. Set TREND_SEARXNG_URL (e.g. http://localhost:8888). This is
     the cleanest path: structured JSON, no scraping. Most *public* instances now
     disable JSON / rate-limit hard, so this is really for a self-hosted one.

  2. **DuckDuckGo via the user's browser (CDP)** — fallback that needs nothing
     installed. DuckDuckGo's HTML endpoint is key-free but anti-bots server-side
     scraping; driving the user's real browser (the same CDP path 小红书/知乎 use)
     sails past that. Returns real results with `site:` targeting honored.

无需 API key 的开源检索：优先用自建 SearXNG 的 JSON 接口（设 TREND_SEARXNG_URL），
否则回退到「用用户真实浏览器（CDP）跑 DuckDuckGo」——免密钥、免安装，site: 定向有效。

The DDG-via-CDP fallback drives the user's browser, so it requires `consent=True`
exactly like the other CDP providers.
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import quote

import requests

try:
    from . import _common
    from .cdp_client import CDPClient, CDPError, ConsentRequired
except ImportError:  # standalone script
    import _common
    from cdp_client import CDPClient, CDPError, ConsentRequired


TIMEOUT = 20

# A self-hosted (or trusted) SearXNG base URL, e.g. "http://localhost:8888".
SEARXNG_URL_ENV = "TREND_SEARXNG_URL"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}


# ---------------------------------------------------------------------------
# Strategy 1: SearXNG JSON API (self-hosted / configured instance).
# ---------------------------------------------------------------------------

def _search_searxng_json(base_url: str, query: str, limit: int, platform: str) -> dict:
    """Query a SearXNG instance's JSON API and normalize the results.

    Raises on transport/HTTP error or when the instance refuses JSON (so the
    caller can fall through to the DuckDuckGo path).
    """
    url = base_url.rstrip("/") + "/search"
    params = {"q": query, "format": "json", "safesearch": "0"}

    def do_request():
        return requests.get(url, params=params, headers=_HEADERS, timeout=TIMEOUT)

    response = _common.request_with_retry(do_request)
    response.raise_for_status()
    ct = response.headers.get("content-type", "")
    if "json" not in ct:
        raise RuntimeError(
            f"SearXNG instance at {base_url} did not return JSON "
            f"(content-type: {ct or 'unknown'}); JSON format may be disabled."
        )
    data = response.json()

    results = []
    for item in data.get("results", [])[:limit]:
        result = _common.make_result(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", ""),
            score=item.get("score"),
            published=item.get("publishedDate", "") or "",
        )
        _common.fill_identity(result, platform)
        results.append(result)
    return _common.make_envelope(query, platform, "searxng", results)


# ---------------------------------------------------------------------------
# Strategy 2: DuckDuckGo HTML via the user's real browser (CDP). Key-free,
# install-free; clears DDG's anti-bot wall by using the actual browser.
# ---------------------------------------------------------------------------

# Runs in the DuckDuckGo HTML results page. Decodes DDG's /l/?uddg= redirect
# links back to the real destination, drops ad rows, and dedupes by URL. Also
# reports DDG's anti-bot challenge so the caller can surface it instead of a
# silent empty list. Every field is guarded — DDG's markup shifts, partial rows
# still rank.
_DDG_JS = r"""
(() => {
  const bodyText = document.body?.innerText || '';
  const challenged = /complete the following challenge|bots use DuckDuckGo/i.test(bodyText);
  const decode = (href) => {
    try {
      const u = new URL(href, location.origin);
      if (u.pathname.startsWith('/l/')) {
        const t = u.searchParams.get('uddg');
        if (t) return decodeURIComponent(t);
      }
      return u.href;
    } catch (e) { return href || ''; }
  };
  const items = [];
  const seen = new Set();
  document.querySelectorAll('.result__body, .result, .results_links').forEach((b) => {
    if (b.querySelector('.badge--ad')) return;            // skip ads
    const a = b.querySelector('a.result__a');
    if (!a) return;
    let href = decode(a.getAttribute('href') || '');
    if (!href || /duckduckgo\.com\/y\.js|ad_domain=|ad_provider=/.test(href)) return;
    if (seen.has(href)) return;
    seen.add(href);
    const sn = b.querySelector('.result__snippet');
    items.push({
      title: (a.innerText || a.textContent || '').trim(),
      url: href,
      snippet: (sn ? (sn.innerText || sn.textContent || '') : '').trim().slice(0, 240),
    });
  });
  return { challenged, ready: items.length > 0 || challenged, items: items.slice(0, 50) };
})()
"""


def _search_ddg_cdp(query: str, limit: int, platform: str,
                    client: "CDPClient" = None, consent: bool = False) -> dict:
    """Search DuckDuckGo through the user's real browser and normalize results.

    DDG's HTML results render asynchronously, so we poll the extractor a few times
    until rows appear (or an anti-bot challenge is detected) rather than reading an
    empty body the instant the tab opens — that silent-empty race was a real bug.
    """
    if not consent:
        raise ConsentRequired(
            "Key-free web search falls back to DuckDuckGo via your real browser "
            "(no SearXNG instance configured). Ask the user for consent, then "
            "retry with consent=True. Or set TREND_SEARXNG_URL to a SearXNG "
            "instance to avoid the browser entirely."
        )

    ddg_url = "https://duckduckgo.com/html/?q=" + quote(query)
    owns_client = client is None
    client = client or CDPClient()
    raw = {}
    try:
        client.ensure_proxy()
        target_id = client.new_tab(ddg_url)
        client.scroll(target_id, 1)  # nudge lazy rows
        # Poll until results render or a challenge shows (DDG loads async).
        for _ in range(8):
            raw = client.eval(target_id, _DDG_JS) or {}
            if isinstance(raw, dict) and raw.get("ready"):
                break
            time.sleep(1.0)
    finally:
        if owns_client:
            client.__exit__(None, None, None)

    if isinstance(raw, dict) and raw.get("challenged"):
        # DDG is rate-limiting this session — surface it, don't pretend it's empty.
        envelope = _common.make_envelope(query, platform, "searxng:ddg", [])
        envelope["login_required"] = True
        envelope["reason"] = (
            "DuckDuckGo served an anti-bot challenge (rate limit). Wait a minute "
            "and retry, or configure a SearXNG instance via TREND_SEARXNG_URL."
        )
        return envelope

    rows = (raw or {}).get("items") if isinstance(raw, dict) else (raw or [])
    results = []
    for item in (rows or [])[:limit]:
        result = _common.make_result(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("snippet", ""),
        )
        _common.fill_identity(result, platform)
        results.append(result)
    return _common.make_envelope(query, platform, "searxng:ddg", results)


# ---------------------------------------------------------------------------
# Public entry point — matches the keyed-provider signature (query, api_key, ...)
# so the dispatcher can call it uniformly. api_key is unused (key-free).
# ---------------------------------------------------------------------------

def search(query: str, api_key=None, limit: int = 10, platform: str = "",
           client: "CDPClient" = None, consent: bool = False) -> dict:
    """Key-free web search. Prefer a configured SearXNG JSON instance, else DDG/CDP.

    If TREND_SEARXNG_URL is set we try its JSON API first; on any failure we fall
    through to DuckDuckGo via the browser. With no instance configured we go
    straight to the DDG/CDP path (which requires consent).
    """
    base_url = os.environ.get(SEARXNG_URL_ENV, "").strip()
    if base_url:
        try:
            return _search_searxng_json(base_url, query, limit, platform)
        except Exception as exc:
            print(f"[searxng] JSON instance unavailable ({exc}); "
                  f"falling back to DuckDuckGo via browser.", file=sys.stderr)

    return _search_ddg_cdp(query, limit, platform, client=client, consent=consent)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Key-free web search (SearXNG / DuckDuckGo)")
    parser.add_argument("--query", required=True, help="search query (site: targeting honored)")
    parser.add_argument("--platform", default="", help="platform tag for the envelope")
    parser.add_argument("--limit", type=int, default=10, help="max results")
    parser.add_argument("--output", default="", help="write JSON here instead of stdout")
    parser.add_argument("--consent", action="store_true",
                        help="consent to drive your real browser for the DuckDuckGo fallback")
    args = parser.parse_args(argv)

    try:
        envelope = search(args.query, limit=args.limit, platform=args.platform,
                          consent=args.consent)
    except ConsentRequired as exc:
        print(f"Consent required: {exc}", file=sys.stderr)
        return 3
    except CDPError as exc:
        print(f"Search unavailable: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
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
