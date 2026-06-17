#!/usr/bin/env python3
"""Platform retrieval strategies.

Maps a target platform to *how* to find that platform's trending content:

- `native`   — a key-free provider that searches the platform directly and
               returns real, structured engagement (e.g. Bilibili). Strongest.
- `sites`    — domains to scope a general web search to (`site:` targeting), so
               Tavily/Exa/Firecrawl return posts *from that platform*, not the
               open web. This is what makes "post on platform X → learn from X's
               hits" actually target X.
- `query_suffix` — platform-idiomatic words that bias toward high-traction posts
               (爆款 / 热门 / viral …).

把「目标平台」映射到「如何检索该平台的热点」：原生免密钥源（如 B站）、site: 域名定向、
以及偏向爆款的查询后缀。这样「在哪个平台发，就检索哪个平台的爆款」才真正成立。
"""


# Per-platform strategy. `native` names a provider module (see retrieve.py); when
# present and chosen, it's preferred because it returns real structured metrics.
STRATEGIES = {
    "xiaohongshu": {
        # CDP drives the user's logged-in browser — the only way to read XHS's
        # JS-rendered, anti-scraped notes. site: is the fallback if CDP is down.
        "native": "cdp",
        "sites": ["xiaohongshu.com", "xhslink.com"],
        "query_suffix": "爆款 热门 高赞 笔记",
    },
    "bilibili": {
        "native": "bilibili",  # key-free REST API, structured engagement
        "sites": ["bilibili.com"],
        "query_suffix": "热门 高播放",
    },
    "zhihu": {
        "native": "cdp",  # JS-rendered; CDP reads 赞同/评论 from the user's session
        "sites": ["zhihu.com"],
        "query_suffix": "高赞 回答 热门",
    },
    "weixin": {
        "native": "cdp",  # 公众号 articles via the browser (Sogou gateway)
        "sites": ["mp.weixin.qq.com", "weixin.sogou.com"],
        "query_suffix": "公众号 热门 文章",
    },
    "weibo": {
        # m.weibo.cn server-side search now hits Sina's anti-bot wall (HTTP 432),
        # so the key-free path is dead. CDP reads the same JSON API from inside the
        # user's logged-in browser, where it still returns structured engagement.
        "native": "cdp",
        "sites": ["weibo.com", "m.weibo.cn"],
        "query_suffix": "热搜 热门 转发 评论",
    },
    "douban": {
        "native": "cdp",  # search pages are readable in-browser; ratings/comments visible
        "sites": ["douban.com"],
        "query_suffix": "热门 高分 讨论",
    },
    "hupu": {
        "native": "cdp",  # forum/search pages expose reply/light/view signals
        "sites": ["hupu.com", "bbs.hupu.com"],
        "query_suffix": "热帖 高亮 回复",
    },
    "twitter": {
        # No native key-free API; use the key-free SearXNG/DuckDuckGo provider,
        # scoped to twitter/x via site: targeting.
        "native": "searxng",
        "sites": ["twitter.com", "x.com"],
        "query_suffix": "viral thread",
    },
    "linkedin": {
        "native": "searxng",
        "sites": ["linkedin.com"],
        "query_suffix": "viral post",
    },
}

# Used when a platform has no registered strategy.
DEFAULT_STRATEGY = {"native": None, "sites": [], "query_suffix": "热门 爆款 viral trending"}


def get_strategy(platform: str) -> dict:
    """Return the strategy for a platform, or a sane default."""
    return STRATEGIES.get(platform, DEFAULT_STRATEGY)


def native_provider(platform: str) -> "str | None":
    """Return the native provider name for a platform, or None."""
    return get_strategy(platform).get("native")


def build_targeted_query(base_query: str, platform: str, use_sites: bool = True) -> str:
    """Shape a query for a specific platform: append idiomatic suffix + site: scope.

    Example: build_targeted_query("校园美食", "xiaohongshu")
             → "校园美食 爆款 热门 高赞 笔记 (site:xiaohongshu.com OR site:xhslink.com)"
    The site: clause is what targets the platform on general web-search providers.
    """
    strategy = get_strategy(platform)
    parts = [base_query.strip()] if base_query.strip() else []
    suffix = strategy.get("query_suffix", "")
    if suffix:
        parts.append(suffix)
    if use_sites and strategy.get("sites"):
        sites = strategy["sites"]
        if len(sites) == 1:
            # A single site needs no OR-group; some engines (DuckDuckGo) error on a
            # lone "(site:x)" parenthesized clause, so emit a bare "site:x".
            parts.append(f"site:{sites[0]}")
        else:
            site_clause = " OR ".join(f"site:{d}" for d in sites)
            parts.append(f"({site_clause})")
    return " ".join(parts)
