#!/usr/bin/env python3
"""Engagement extraction and traction-based vibe scoring.

Search providers return candidate posts (title / url / snippet). To decide which
posts are worth *learning* from, we extract real engagement signals (likes,
saves, comments, shares) and the post's age, then compute a traction-based
`vibe_score`. Its weights/formula live in the selected account para_config.yaml; defaults
use weighted engagement per day, log-normalized to 0-100. The skill ranks
results by this score and learns patterns from the top ones.

注意区分两个分数 / Two distinct scores:
- 本模块的 `vibe_score`：检索到的**真实帖子**的传播力（互动量 / 发布天数算出来的），
  用来挑选「值得学习」的高网感样本。
- prompts/critique_content.md 的 `vibe_index`：对**用户自己内容**的质量诊断（由 Claude 打分）。

Provider-returned structured metrics are preferred. Text extractors are a
fallback for generic search snippets or crawled pages.
"""

import math
import re
from datetime import datetime
from typing import Callable, Optional

try:
    from . import _common
except ImportError:  # run as a standalone script
    import _common


# Weighted engagement: saves and shares signal stronger intent ("收藏价值"/"传播力")
# than a like, so they count more. Tunable.
ENGAGEMENT_WEIGHTS = {
    "likes": 1.0,
    "comments": 2.0,
    "saves": 3.0,
    "shares": 4.0,
    # Views/play counts are much weaker than active intent, but they matter on
    # video/forum platforms when a listing exposes reach but not enough reactions.
    "views": 0.01,
}

# Weighted-engagement-per-day that maps to a vibe_score of ~100 (log scale).
VIBE_SCORE_BASELINE_PER_DAY = 5000.0

# Assumed age when a post's publish date can't be parsed — conservative so that
# unknown-age posts don't outrank posts with a known, recent date.
DEFAULT_AGE_DAYS = 30

# Chinese / shorthand magnitude units → multiplier.
_UNIT_MULT = {"": 1, "万": 1e4, "w": 1e4, "W": 1e4, "亿": 1e8, "k": 1e3, "K": 1e3}

# A number with optional thousands separators / decimal and optional magnitude unit.
# Two forms: TIGHT (no space before unit) for "number immediately before keyword",
# and the spaced form for "keyword then number" where "1.2 万" may have a space.
_NUM = r"[\d,]+(?:\.\d+)?"
_NUM_UNIT_TIGHT = _NUM + r"[万亿wWkK]?"
_NUM_UNIT = _NUM + r"\s*[万亿wWkK]?"


def parse_count(text: Optional[str]) -> Optional[int]:
    """Parse a human-readable count into an int.

    Handles "1234", "1,234", "1.2万", "1.2万+", "12k", "3.4w", "10+". Returns
    None when no number is present.
    """
    if text is None:
        return None
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*([万亿wWkK]?)", str(text))
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    return int(round(value * _UNIT_MULT.get(match.group(2), 1)))


def _find_metric(text: str, keywords: list) -> Optional[int]:
    """Find a count adjacent to any of the given keywords (number on either side).

    Two real-world layouts: a number *immediately* before the keyword ("1.2万赞",
    "3456收藏") or the keyword then a number ("收藏 3.5万", "点赞：1234", "likes 99").
    The before-pattern requires adjacency (no whitespace) so that in a
    "kw1 n1 kw2 n2" run we don't misattribute n1 to kw2.
    """
    for keyword in keywords:
        escaped = re.escape(keyword)
        # number immediately before keyword: "1.2万赞", "3456收藏" (tight, no space)
        before = re.search(r"(" + _NUM_UNIT_TIGHT + r")" + escaped, text)
        if before:
            value = parse_count(before.group(1))
            if value is not None:
                return value
        # keyword before number: "赞 1.2万", "点赞：1234", "likes 99"
        after = re.search(escaped + r"[:：\s]*(" + _NUM_UNIT + r")", text, re.IGNORECASE)
        if after:
            value = parse_count(after.group(1))
            if value is not None:
                return value
    return None


# Per-platform keyword maps. Longer / more specific keywords first.
_XIAOHONGSHU_KEYWORDS = {
    "likes": ["点赞", "赞", "likes", "like"],
    "saves": ["收藏", "saves", "save", "collect", "bookmark"],
    "comments": ["评论", "回复", "comments", "comment"],
    "shares": ["分享", "转发", "shares", "share"],
}

# Generic fallback for platforms without a dedicated extractor yet.
_GENERIC_KEYWORDS = {
    "likes": ["点赞", "赞", "likes", "like", "❤", "👍"],
    "saves": ["收藏", "saves", "save", "bookmark", "🔖"],
    "comments": ["评论", "回复", "comments", "comment", "replies", "💬"],
    "shares": ["分享", "转发", "shares", "share", "retweet", "rt", "🔁"],
    "views": ["浏览", "阅读", "播放", "views", "view", "reads", "read", "▶"],
}


def _extract_with_keywords(text: str, keyword_map: dict) -> dict:
    """Extract the four engagement fields from text using a keyword map."""
    return {field: _find_metric(text, kws) for field, kws in keyword_map.items()}


def extract_xiaohongshu(text: str) -> dict:
    """Extract engagement from Xiaohongshu post text/snippet (赞 / 收藏 / 评论 / 分享)."""
    return _extract_with_keywords(text, _XIAOHONGSHU_KEYWORDS)


def extract_generic(text: str) -> dict:
    """Best-effort engagement extraction for platforms without a dedicated extractor."""
    return _extract_with_keywords(text, _GENERIC_KEYWORDS)


# Platform → extractor. V1 ships Xiaohongshu; add others here as they're built.
# Roadmap order (per development plan): twitter, linkedin, zhihu, then more.
EXTRACTORS = {
    "xiaohongshu": extract_xiaohongshu,
}


def extract_engagement(text: str, platform: str = "") -> dict:
    """Dispatch to the platform's extractor, falling back to the generic one."""
    extractor = EXTRACTORS.get(platform, extract_generic)
    return extractor(text or "")


def parse_published_days(text: Optional[str], now: Optional[datetime] = None) -> Optional[int]:
    """Estimate how many days ago a post was published, from relative or absolute dates.

    Understands "刚刚 / X小时前 / 今天" (0), "昨天" (1), "前天" (2),
    "N天/周/个月/年前", Chinese absolute dates, ISO-ish dates, MM-DD dates,
    and Weibo/Twitter-style English timestamps.
    Returns None when nothing parseable is found. `now` is injectable for tests.
    """
    if not text:
        return None
    now = now or datetime.now()
    s = str(text)

    if any(token in s for token in ("刚刚", "分钟前", "小时前", "今天")):
        return 0
    if "昨天" in s:
        return 1
    if "前天" in s:
        return 2

    for pattern, mult in ((r"(\d+)\s*天前", 1), (r"(\d+)\s*周前", 7),
                          (r"(\d+)\s*个?月前", 30), (r"(\d+)\s*年前", 365)):
        m = re.search(pattern, s)
        if m:
            return int(m.group(1)) * mult

    full = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if full:
        try:
            published = datetime(int(full.group(1)), int(full.group(2)), int(full.group(3)))
            return max((now - published).days, 0)
        except ValueError:
            return None

    cn_full = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", s)
    if cn_full:
        try:
            published = datetime(int(cn_full.group(1)), int(cn_full.group(2)),
                                 int(cn_full.group(3)))
            return max((now - published).days, 0)
        except ValueError:
            return None

    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%a %b %d %H:%M:%S %Y"):
        try:
            published = datetime.strptime(s.strip(), fmt)
            published = published.replace(tzinfo=None)
            return max((now - published).days, 0)
        except ValueError:
            pass

    md = re.search(r"(?<!\d)(\d{1,2})[-/](\d{1,2})(?!\d)", s)
    if md:
        try:
            published = datetime(now.year, int(md.group(1)), int(md.group(2)))
            delta = (now - published).days
            return delta if delta >= 0 else delta + 365  # date is in the last year
        except ValueError:
            return None

    cn_md = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日?", s)
    if cn_md:
        try:
            published = datetime(now.year, int(cn_md.group(1)), int(cn_md.group(2)))
            delta = (now - published).days
            return delta if delta >= 0 else delta + 365
        except ValueError:
            return None

    return None


def weighted_engagement(metrics: dict) -> float:
    """Sum the engagement metrics with their weights (missing fields count as 0)."""
    weights = _common.deep_get(
        _common.load_para_config(),
        "real_vibe_score.engagement_weights",
        ENGAGEMENT_WEIGHTS,
    )
    return sum(float(weights.get(field, 0)) * (metrics.get(field) or 0)
               for field in weights)


def compute_vibe_score(metrics: dict, published_days: Optional[int]) -> Optional[float]:
    """Traction-based vibe score (0-100) from engagement and age.

    vibe_score = log-normalized( weighted_engagement / days_since_published ).
    Returns None when there's no engagement signal at all (so it sinks in ranking).
    """
    total = weighted_engagement(metrics or {})
    if total <= 0:
        return None
    config = _common.load_para_config().get("real_vibe_score", {})
    default_age_days = int(config.get("default_age_days", DEFAULT_AGE_DAYS))
    baseline = float(config.get("baseline_per_day", VIBE_SCORE_BASELINE_PER_DAY))
    max_score = float(config.get("max_score", 100.0))
    min_score = float(config.get("min_score", 0.0))
    round_digits = int(config.get("round_digits", 1))
    formula = config.get("formula", "log_normalized_per_day")
    days = default_age_days if published_days is None else max(published_days, 1)
    per_day = total / days
    if formula == "linear_per_day":
        score = max_score * per_day / baseline if baseline > 0 else max_score
    else:
        score = (
            max_score * math.log10(per_day + 1) / math.log10(baseline + 1)
            if baseline > 0
            else max_score
        )
    return round(min(max_score, max(min_score, score)), round_digits)


def strip_html(html: str) -> str:
    """Crude tag/entity strip so engagement keywords survive — stdlib only."""
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def fetch_page_text(url: str, fetcher: Optional[Callable] = None, timeout: int = 20) -> str:
    """Fetch a URL and return stripped text. Best-effort: returns "" on any failure.

    `fetcher` is injectable for tests; defaults to requests.get. Network errors are
    swallowed so engagement enrichment degrades to snippet-only rather than crashing.
    """
    if fetcher is None:
        try:
            import requests
        except ImportError:
            return ""
        fetcher = lambda u: requests.get(u, timeout=timeout)  # noqa: E731
    try:
        response = fetcher(url)
        html = getattr(response, "text", "") or ""
    except Exception:
        return ""
    return strip_html(html)


def _has_metrics(metrics: Optional[dict]) -> bool:
    """True if the dict carries at least one non-empty engagement number."""
    if not metrics:
        return False
    return any(v for v in metrics.values())


def enrich_result(result: dict, platform: str = "", extra_text: str = "",
                  now: Optional[datetime] = None) -> dict:
    """Attach engagement, published_days, and vibe_score to a normalized result.

    Structured metrics already on the result (e.g. from the Bilibili provider,
    which returns real play/like/favorites) take precedence — we do NOT overwrite
    them with text extraction. Only when no usable metrics are present do we fall
    back to scraping keywords out of the title/snippet/crawled page text.
    """
    existing = result.get("engagement")
    if _has_metrics(existing):
        metrics = {field: existing.get(field) for field in ENGAGEMENT_WEIGHTS}
    else:
        text = " ".join(filter(None, [
            result.get("title", ""), result.get("snippet", ""),
            extra_text, result.get("published", ""),
        ]))
        metrics = extract_engagement(text, platform)

    # Prefer an absolute publish date the provider gave us; else parse from text.
    age_text = " ".join(filter(None, [
        result.get("published", ""), extra_text, result.get("snippet", ""),
    ]))
    published_days = parse_published_days(age_text, now=now)

    result["engagement"] = metrics
    result["published_days"] = published_days
    result["vibe_score"] = compute_vibe_score(metrics, published_days)
    return result


def rank_results(results: list, top_n: Optional[int] = None,
                 min_vibe: Optional[float] = None) -> list:
    """Sort results by vibe_score (desc); scored posts first, then optional filters."""
    def sort_key(result):
        score = result.get("vibe_score")
        return (score is not None, score or 0.0)

    ranked = sorted(results, key=sort_key, reverse=True)
    if min_vibe is not None:
        ranked = [r for r in ranked if (r.get("vibe_score") or 0) >= min_vibe]
    if top_n:
        ranked = ranked[:top_n]
    return ranked
