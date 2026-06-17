#!/usr/bin/env python3
"""Unified trend retrieval dispatcher (V2 entry point).

Picks a provider (or auto-selects the first configured one), runs the query, and
writes a normalized envelope to outputs/trends.json. When no provider is
configured, it prints a clear notice and exits 0 so the SKILL.md pipeline falls
back to V1 (knowledge-base only) extraction.

统一检索调度器（V2 入口）。选择 provider（或 auto 选第一个已配置的），执行查询，
把归一化结果写入 outputs/trends.json。若没有可用 provider，则打印提示并以 0 退出，
让 SKILL.md 流程回退到 V1（仅知识库）。

用法 / Usage:
    # First-time setup — store API keys to ~/.trend-improver/config.json (0600)
    python3 retrieval/retrieve.py --setup

    # Auto-select provider, build query from topic + platform
    python3 retrieval/retrieve.py --provider auto \
        --topic 校园美食 --platform xiaohongshu \
        --limit 10 --output outputs/trends.json

    # Force a specific provider with an explicit query
    python3 retrieval/retrieve.py --provider tavily --query "小红书 校园美食 爆款"
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from . import (_common, engagement, strategy, bilibili, cdp_platforms,
                   weibo, tavily, exa, firecrawl, searxng, crawl4ai as crawl4ai_mod)
    from .cdp_client import ConsentRequired
except ImportError:  # run as a standalone script, not a package module
    import _common
    import engagement
    import strategy
    import bilibili
    import cdp_platforms
    import weibo
    import tavily
    import exa
    import firecrawl
    import searxng
    import crawl4ai as crawl4ai_mod
    from cdp_client import ConsentRequired


# Hosted, key-required providers. Name -> module exposing search(query, key, ...).
REST_PROVIDERS = {
    "tavily": tavily,
    "exa": exa,
    "firecrawl": firecrawl,
}

# Key-free native providers that search a platform directly and return real,
# structured engagement. Name -> module exposing search(query, ..., platform=...).
#   bilibili -> Bilibili REST API (no key)
#   weibo    -> m.weibo.cn search JSON (no key) — legacy; m.weibo.cn now 432s
#               server-side, so weibo is routed via cdp in strategy.py instead.
#   cdp      -> drives the user's logged-in browser via the web-access CDP proxy;
#               handles 小红书/知乎/微信公众号/豆瓣/虎扑/微博 (dispatches by platform)
#   searxng  -> key-free web search (SearXNG JSON if configured, else DuckDuckGo
#               via the browser); used for twitter/linkedin site:-targeted search
NATIVE_PROVIDERS = {
    "bilibili": bilibili,
    "weibo": weibo,
    "cdp": cdp_platforms,
    "searxng": searxng,
}


def build_query(topic: str, platform: str, query: str) -> str:
    """Compose the *base* (subject) search query — no targeting or suffixes.

    An explicit --query always wins. Otherwise the subject is just the topic.
    Platform-specific shaping (idiom suffix, site: scoping) is applied later by
    strategy, and only for keyed web-search providers — native providers like
    Bilibili search best on the bare subject (adding "热门/爆款" pollutes results).
    """
    if query:
        return query
    return topic.strip() or (platform or "trending")


def default_reference_accounts_path() -> Path:
    """Default per-skill reference account list."""
    return _common.account_file(_common.REFERENCE_ACCOUNTS_NAME)


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_skill_path(path: str) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_absolute():
        p = _skill_root() / p
    return str(p)


def _infer_account_dir_from_para_config(path: str) -> Optional[Path]:
    """Infer account dir when only --para-config myaccount/{id}/para_config.yaml is passed."""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = _skill_root() / p
    if p.name == _common.PARA_CONFIG_NAME and p.parent.name != "myaccount":
        return p.parent
    return None


def _resolve_reference_accounts_path(path: str, account_dir: Optional[Path]) -> str:
    """Resolve reference_accounts path, relative to account_dir when selected."""
    if account_dir is not None:
        if not path or path in {"myaccount/reference_accounts.md", "reference_accounts.md"}:
            return str(account_dir / _common.REFERENCE_ACCOUNTS_NAME)
        p = Path(path)
        return str(p if p.is_absolute() else account_dir / p)
    return _resolve_skill_path(path or "myaccount/reference_accounts.md")


def load_reference_accounts(path: str, platform: str) -> list:
    """Parse the simple Markdown table in reference_accounts.md."""
    if not path:
        default_path = default_reference_accounts_path()
        path = str(default_path) if default_path.exists() else ""
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        return []

    accounts = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped or "homepage_url" in stripped:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        row_platform, account_name, homepage_url = cells[:3]
        learn_what = cells[3] if len(cells) > 3 else ""
        notes = cells[4] if len(cells) > 4 else ""
        if not homepage_url:
            continue
        if not _platform_matches(row_platform, platform):
            continue
        inferred = _common.infer_account_from_url(homepage_url, platform).lstrip("@")
        name = account_name or inferred
        if not name:
            continue
        accounts.append({
            "platform": row_platform or platform,
            "account_name": name,
            "homepage_url": homepage_url,
            "learn_what": learn_what,
            "notes": notes,
        })
    return accounts


def _platform_matches(row_platform: str, target_platform: str) -> bool:
    row = (row_platform or "").strip().lower()
    target = (target_platform or "").strip().lower()
    if not target:
        return bool(row and row not in {"*", "all", "any"})
    if not row or row in {"*", "all", "any"}:
        return True
    try:
        row = cdp_platforms.resolve_platform(row)
        target = cdp_platforms.resolve_platform(target)
    except Exception:
        pass
    return row == target


def dispatch_with_reference_accounts(base_query: str, platform: str, requested: str,
                                     config: dict, limit: int, consent: bool,
                                     reference_accounts: list,
                                     min_reference_results: int = 5):
    """Search priority reference accounts first, then backfill with normal trends."""
    envelopes = []
    providers = []
    reference_count = 0

    for account in reference_accounts:
        account_name = account["account_name"]
        ref_query = " ".join([account_name, base_query]).strip()
        name, envelope = dispatch(ref_query, platform, requested, config, limit, consent)
        if envelope is None:
            continue
        _mark_reference_results(envelope.get("results", []), account, platform)
        reference_count += len(envelope.get("results", []))
        envelopes.append(envelope)
        if name:
            providers.append(name)

    if reference_count < min_reference_results:
        name, envelope = dispatch(base_query, platform, requested, config, limit, consent)
        if envelope is not None:
            envelopes.append(envelope)
            if name:
                providers.append(name)

    if not envelopes:
        return None, None

    merged = _merge_envelopes(base_query, platform, envelopes, providers)
    merged["reference_accounts_used"] = [
        {"account_name": a["account_name"], "homepage_url": a["homepage_url"]}
        for a in reference_accounts
    ]
    return (providers[0] if providers else None), merged


def _mark_reference_results(results: list, account: dict, platform: str) -> None:
    for result in results:
        result["source_type"] = "reference_account"
        result["source_account"] = account["account_name"]
        result["source_account_url"] = account["homepage_url"]
        _common.fill_identity(result, platform, fallback=account["account_name"])


def _merge_envelopes(base_query: str, platform: str, envelopes: list, providers: list) -> dict:
    seen = set()
    results = []
    for envelope in envelopes:
        for result in envelope.get("results", []):
            key = result.get("url") or f"{result.get('title', '')}|{result.get('snippet', '')}"
            if key in seen:
                continue
            seen.add(key)
            results.append(result)
    provider = "+".join(dict.fromkeys(providers)) if providers else None
    return _common.make_envelope(base_query, platform, provider, results)


def dispatch(base_query: str, platform: str, requested: str, config: dict,
             limit: int, consent: bool = False):
    """Run the right retrieval for this platform and return (provider_name, envelope).

    Priority (when --provider is 'auto'):
      1. The platform's NATIVE key-free provider (e.g. bilibili) — real structured
         engagement, no key. This is "search the platform you're posting to".
      2. The first configured keyed provider, with the query *targeted* to the
         platform via site: scoping (strategy.build_targeted_query).
      3. Nothing configured → return (None, None) so the caller goes offline (V1).

    An explicit --provider overrides auto-selection but still gets platform
    targeting for keyed providers.

    `consent` is forwarded to CDP providers, which refuse to drive the user's
    browser without it (raising ConsentRequired). bilibili needs no consent (no
    browser). ConsentRequired propagates to the caller so it can ask the user.
    """
    # Explicit native provider request (e.g. --provider bilibili / --provider cdp).
    if requested in NATIVE_PROVIDERS:
        module = NATIVE_PROVIDERS[requested]
        return requested, _call_native(module, requested, base_query, platform, limit, consent)

    # Auto: prefer the platform's native provider if it has one. CDP depends on the
    # user's browser being available; if it isn't, fall THROUGH to keyed search
    # rather than failing — auto should always degrade gracefully.
    if requested == "auto":
        native = strategy.native_provider(platform)
        if native and native in NATIVE_PROVIDERS:
            module = NATIVE_PROVIDERS[native]
            try:
                return native, _call_native(module, native, base_query, platform, limit, consent)
            except ConsentRequired:
                raise  # consent is the user's decision — never silently fall through
            except Exception as exc:
                if native == "bilibili":
                    raise  # bilibili has no fallback worth trying; surface it
                # CDP unavailable (browser not enabled, proxy down) → try keyed next.
                print(f"[auto] native '{native}' unavailable ({exc}); "
                      f"trying keyed search.", file=sys.stderr)

    # Fall back to a keyed REST provider with platform-targeted query.
    name, module = resolve_provider(requested, config)
    if module is None:
        return None, None
    targeted = strategy.build_targeted_query(base_query, platform)
    api_key = _common.get_api_key(name, config)
    return name, module.search(targeted, api_key, limit=limit, platform=platform)


def _call_native(module, name: str, base_query: str, platform: str, limit: int,
                 consent: bool):
    """Call a native provider, passing consent only to those that need it.

    - cdp:     drives the browser → needs consent.
    - searxng: key-free web search; gets the site:-targeted query (so twitter /
               linkedin results are scoped to the platform) and consent (its
               DuckDuckGo fallback drives the browser).
    - others (bilibili/weibo): bare subject query, no consent, no browser.
    """
    if name == "cdp":
        return module.search(base_query, limit=limit, platform=platform, consent=consent)
    if name == "searxng":
        targeted = strategy.build_targeted_query(base_query, platform)
        return module.search(targeted, limit=limit, platform=platform, consent=consent)
    return module.search(base_query, limit=limit, platform=platform)


def run_setup() -> int:
    """Interactively collect API keys and save them 0600. Blank input skips a key."""
    print("Trend-Aware Content Improver — retrieval setup")
    print("Enter API keys (leave blank to skip). Stored at ~/.trend-improver/config.json (0600).\n")

    config = _common.load_config()
    prompts = [
        ("tavily_api_key", "Tavily API key"),
        ("exa_api_key", "Exa API key"),
        ("firecrawl_api_key", "Firecrawl API key"),
    ]
    for config_key, label in prompts:
        existing = config.get(config_key)
        suffix = " [already set, blank keeps it]" if existing else ""
        value = getpass.getpass(f"{label}{suffix}: ").strip()
        if value:
            config[config_key] = value

    _common.save_config(config)
    configured = _common.configured_providers(config)
    print(f"\nSaved. Configured providers: {', '.join(configured) if configured else 'none'}")
    return 0


def resolve_provider(requested: str, config: dict):
    """Return (provider_name, module_or_None) for a request, or (None, None) offline.

    For 'auto', pick the first provider with a configured key. For a named REST
    provider, require its key. crawl4ai is handled by the caller (URL-based).
    """
    if requested == "auto":
        candidates = _common.configured_providers(config)
        if not candidates:
            return None, None
        name = candidates[0]
        return name, REST_PROVIDERS[name]

    if requested in REST_PROVIDERS:
        if not _common.get_api_key(requested, config):
            return None, None
        return requested, REST_PROVIDERS[requested]

    # crawl4ai is opt-in and URL-driven; not auto-selected.
    return requested, None


def write_output(envelope: dict, output: str) -> None:
    """Write the envelope to a file (creating parent dirs) or to stdout."""
    text = json.dumps(envelope, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text)


def enrich_and_rank(envelope: dict, crawl: bool = False, top_n: int = 0,
                    min_vibe: Optional[float] = None) -> dict:
    """Score each result by real traction and rank, so the skill learns from the best.

    For every result, extract engagement (likes/saves/comments/shares) + age and
    compute a vibe_score (engagement per day). When `crawl` is on, fetch each post
    page first so the metrics come from the live post, not just the search snippet.
    Then sort by vibe_score and keep the top traction posts.
    """
    platform = envelope.get("platform", "")
    for result in envelope.get("results", []):
        extra_text = ""
        if crawl and result.get("url"):
            extra_text = engagement.fetch_page_text(result["url"])
        engagement.enrich_result(result, platform=platform, extra_text=extra_text)

    envelope["results"] = engagement.rank_results(
        envelope.get("results", []),
        top_n=top_n or None,
        min_vibe=min_vibe,
    )
    envelope["ranked_by"] = "vibe_score"
    return envelope


def save_examples(envelope: dict, output: str, top_n: int = 5,
                  prefer_scored: bool = True) -> dict:
    """Persist the top-ranked posts as rewrite references.

    Keeps the fields the rewrite step studies — title, url, engagement, vibe_score,
    snippet. This is the "保存网感指数高的几个例子供参考改写" artifact.

    Prefer traction-scored winners (vibe_score not None). But some sources expose no
    engagement on their listing (e.g. Sogou's 微信公众号 search), so every result is
    unscored — there, fall back to the provider's own order (relevance) rather than
    saving nothing. `ranked_by` records which basis was actually used.
    """
    results = envelope.get("results", [])
    scored = [r for r in results if r.get("vibe_score") is not None]
    if prefer_scored and scored:
        examples, ranked_by = scored[:top_n], "vibe_score"
    else:
        # No traction signal available → keep provider order so references still exist.
        examples, ranked_by = results[:top_n], "relevance (no engagement on listing)"
    bundle = {
        "platform": envelope.get("platform", ""),
        "query": envelope.get("query", ""),
        "provider": envelope.get("provider"),
        "ranked_by": ranked_by,
        "count": len(examples),
        "examples": [
            _example_record(r, envelope.get("platform", ""))
            for r in examples
        ],
    }
    text = json.dumps(bundle, ensure_ascii=False, indent=2)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Saved {len(examples)} reference examples to {output} (ranked_by: {ranked_by})")
    return bundle


def _example_record(result: dict, platform: str) -> dict:
    """Build the saved reference example row with non-empty identity when possible."""
    row = dict(result)
    _common.fill_identity(row, platform, fallback=row.get("source_account", ""))
    identity = row.get("account") or row.get("author") or row.get("source_account") or ""
    # Keep the schema stable: both fields are always present and mirror each other
    # when a provider only exposes one side.
    return {
        "title": row.get("title", ""),
        "url": row.get("url", ""),
        "vibe_score": row.get("vibe_score"),
        "engagement": row.get("engagement", {}),
        "published": row.get("published", ""),
        "snippet": row.get("snippet", ""),
        "account": row.get("account") or identity,
        "author": row.get("author") or identity,
        "source_type": row.get("source_type") or "trend_search",
        "reference_role": "trend_hotspot",
        "source_account": row.get("source_account", ""),
        "source_account_url": row.get("source_account_url", ""),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Unified trend retrieval dispatcher")
    parser.add_argument("--account-dir", default="",
                        help="selected account directory, e.g. myaccount/xiaohongshu_main")
    parser.add_argument("--para-config", default="",
                        help="YAML parameter config (default: selected account para_config.yaml)")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["auto", "bilibili", "weibo", "cdp", "searxng", "tavily", "exa", "firecrawl", "crawl4ai"],
        help="retrieval provider (auto = native for the platform, else first keyed)",
    )
    parser.add_argument("--topic", default="", help="topic slug or display name")
    parser.add_argument("--platform", default="", help="target platform")
    parser.add_argument("--query", default="", help="explicit query (overrides topic/platform)")
    parser.add_argument("--url", action="append", help="URL to crawl (crawl4ai only, repeatable)")
    parser.add_argument("--limit", type=int, default=None, help="max results")
    parser.add_argument("--output", default="", help="write JSON here (e.g. outputs/trends.json)")
    parser.add_argument("--setup", action="store_true", help="store API keys interactively")
    parser.add_argument("--crawl", action="store_true", default=None,
                        help="fetch each result page to read real engagement (likes/saves/age)")
    parser.add_argument("--no-crawl", action="store_false", dest="crawl",
                        help="disable page crawling even if para_config enables it")
    parser.add_argument("--top", type=int, default=None,
                        help="keep only the top N results by vibe_score (0 = keep all)")
    parser.add_argument("--min-vibe", type=float, default=None,
                        help="drop results below this vibe_score")
    parser.add_argument("--no-rank", action="store_true", default=None,
                        help="skip engagement scoring/ranking; return raw provider order")
    parser.add_argument("--consent", action="store_true",
                        help="consent to drive your real logged-in browser (CDP platforms: "
                             "小红书/知乎/微信公众号). Without it, CDP retrieval is refused.")
    parser.add_argument("--save-examples", default="",
                        help="also write the top-ranked results to this file as rewrite references")
    parser.add_argument("--examples-n", type=int, default=None,
                        help="number of reference examples to save (0 = --top or 5)")
    parser.add_argument("--reference-accounts", default="",
                        help="Markdown table of priority account homepages; defaults to "
                             "selected account reference_accounts.md when present")
    args = parser.parse_args(argv)

    if args.setup:
        return run_setup()

    if args.account_dir:
        os.environ[_common.ACCOUNT_DIR_ENV] = args.account_dir
    if args.para_config:
        os.environ[_common.PARA_CONFIG_ENV] = args.para_config
    para_config = _common.load_para_config(args.para_config or None, args.account_dir or None)
    retrieval_config = para_config.get("retrieval", {})
    ref_config = retrieval_config.get("reference_accounts", {})
    args.provider = args.provider or retrieval_config.get("provider", "auto")
    args.limit = args.limit if args.limit is not None else int(retrieval_config.get("limit", 10))
    args.crawl = bool(retrieval_config.get("crawl", False)) if args.crawl is None else args.crawl
    args.top = args.top if args.top is not None else int(retrieval_config.get("top", 0) or 0)
    args.min_vibe = args.min_vibe if args.min_vibe is not None else retrieval_config.get("min_vibe")
    rank_enabled = bool(retrieval_config.get("rank", True))
    args.no_rank = (not rank_enabled) if args.no_rank is None else args.no_rank
    args.examples_n = args.examples_n if args.examples_n is not None else int(retrieval_config.get("examples_n", 0) or 0)
    reference_accounts_enabled = bool(ref_config.get("enabled", True))
    if not args.reference_accounts and reference_accounts_enabled:
        selected_account_dir = (
            _common.resolve_account_dir(args.account_dir or None)
            or _infer_account_dir_from_para_config(args.para_config)
        )
        args.reference_accounts = _resolve_reference_accounts_path(
            ref_config.get("path", "myaccount/reference_accounts.md"),
            selected_account_dir,
        )

    config = _common.load_config()
    query = build_query(args.topic, args.platform, args.query)

    # crawl4ai is URL-driven and handled separately from the keyed REST providers.
    if args.provider == "crawl4ai":
        if not args.url:
            print("crawl4ai requires at least one --url.", file=sys.stderr)
            return 2
        try:
            envelope = crawl4ai_mod.search(args.url, platform=args.platform)
        except RuntimeError as exc:
            # Library missing → treat as offline so the pipeline falls back to V1.
            print(f"{exc}\nFalling back to V1 (offline) mode.", file=sys.stderr)
            envelope = _common.offline_envelope(query, args.platform, str(exc))
            write_output(envelope, args.output)
            return 0
        if not args.no_rank:
            envelope = enrich_and_rank(envelope, crawl=args.crawl,
                                       top_n=args.top, min_vibe=args.min_vibe)
        write_output(envelope, args.output)
        return 0

    name, envelope = None, None
    try:
        reference_accounts = (
            load_reference_accounts(args.reference_accounts, args.platform)
            if reference_accounts_enabled
            else []
        )
        if reference_accounts:
            configured_min_refs = int(ref_config.get("min_results_before_fallback", 5) or 0)
            min_refs = args.examples_n if args.examples_n > 0 else (args.top or configured_min_refs)
            name, envelope = dispatch_with_reference_accounts(
                query, args.platform, args.provider, config, args.limit,
                consent=args.consent,
                reference_accounts=reference_accounts,
                min_reference_results=min_refs,
            )
        else:
            name, envelope = dispatch(query, args.platform, args.provider, config,
                                      args.limit, consent=args.consent)
    except ConsentRequired as exc:
        # CDP needs the user's go-ahead before touching their browser. Emit a
        # distinct consent_required envelope (NOT offline) so SKILL.md asks the
        # user, then retries with --consent. Exit 0: this is an expected branch.
        reason = str(exc)
        print(f"Consent required before retrieval: {reason}", file=sys.stderr)
        envelope = _common.offline_envelope(query, args.platform, reason)
        envelope["mode"] = "consent_required"
        envelope["consent_required"] = True
        envelope["platform_native"] = strategy.native_provider(args.platform)
        write_output(envelope, args.output)
        return 0
    except Exception as exc:  # network/HTTP/provider error → degrade to offline
        reason = f"{args.provider} retrieval failed: {exc}"
        print(f"{reason}\n→ Falling back to V1 (offline) mode.", file=sys.stderr)
        envelope = _common.offline_envelope(query, args.platform, reason)
        write_output(envelope, args.output)
        return 0

    if envelope is None:
        reason = (
            "No retrieval provider available for this platform. "
            "Bilibili works key-free; for other platforms run "
            "`python3 retrieval/retrieve.py --setup` to add a Tavily/Exa/Firecrawl key "
            "(or set TREND_TAVILY_API_KEY / TREND_EXA_API_KEY / TREND_FIRECRAWL_API_KEY). "
            "Falling back to V1 (offline) mode; the skill will use the knowledge base only."
        )
        print(f"{reason}", file=sys.stderr)
        envelope = _common.offline_envelope(query, args.platform, reason)
        write_output(envelope, args.output)
        return 0  # non-fatal: offline is a valid path

    if not args.no_rank:
        envelope = enrich_and_rank(envelope, crawl=args.crawl,
                                   top_n=args.top, min_vibe=args.min_vibe)
    write_output(envelope, args.output)

    # Optionally persist the top-ranked posts as concrete rewrite references — the
    # high-vibe_score examples the rewrite step should study and emulate.
    if args.save_examples:
        examples_n = args.examples_n if args.examples_n > 0 else (args.top or 5)
        prefer_scored = bool(retrieval_config.get("prefer_scored_examples", True))
        save_examples(envelope, args.save_examples, top_n=examples_n,
                      prefer_scored=prefer_scored)

    if args.output:
        top = envelope["results"][0].get("vibe_score") if envelope["results"] else None
        print(f"[{name}] wrote {len(envelope['results'])} results to {args.output} "
              f"(top vibe_score: {top})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
