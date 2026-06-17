#!/usr/bin/env python3
"""Shared helpers for the retrieval layer.

Config loading (env vars or ~/.trend-improver/config.json), a small retry/backoff
wrapper for HTTP 429, and helpers that build the normalized result schema every
provider must emit.

检索层公共工具：配置加载（环境变量或 ~/.trend-improver/config.json）、
针对 429 的重试退避、以及统一结果 schema 的构造助手。
"""

import json
import os
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # PyYAML is in requirements; fallback keeps imports safe.
    yaml = None


# Where interactive --setup writes credentials. 0600, never committed.
CONFIG_PATH = Path.home() / ".trend-improver" / "config.json"

SKILL_ROOT = Path(__file__).resolve().parents[1]
MYACCOUNT_DIR = SKILL_ROOT / "myaccount"
PARA_CONFIG_PATH = MYACCOUNT_DIR / "para_config.yaml"
PARA_CONFIG_ENV = "TREND_PARA_CONFIG_PATH"
ACCOUNT_DIR_ENV = "TREND_ACCOUNT_DIR"
ACCOUNT_POSITIONING_NAME = "account_positioning.md"
REFERENCE_ACCOUNTS_NAME = "reference_accounts.md"
PARA_CONFIG_NAME = "para_config.yaml"

DEFAULT_PARA_CONFIG = {
    "retrieval": {
        "provider": "auto",
        "limit": 20,
        "crawl": True,
        "rank": True,
        "top": 8,
        "min_vibe": None,
        "examples_n": 5,
        "prefer_scored_examples": True,
        "reference_accounts": {
            "enabled": True,
            "path": "myaccount/reference_accounts.md",
            "min_results_before_fallback": 5,
        },
    },
    "real_vibe_score": {
        "formula": "log_normalized_per_day",
        "max_score": 100.0,
        "min_score": 0.0,
        "round_digits": 1,
        "baseline_per_day": 5000.0,
        "default_age_days": 30,
        "engagement_weights": {
            "likes": 1.0,
            "comments": 2.0,
            "saves": 3.0,
            "shares": 4.0,
            "views": 0.01,
        },
    },
    "source_links": {
        "enabled": True,
        "max_urls": 5,
        "max_chars_per_source": 12000,
        "timeout_seconds": 30,
        "require_source_grounding_for_urls": True,
    },
    "predicted_vibe_index": {
        "formula": "weighted_positive_mean_with_ai_penalty",
        "positive_dimensions": {
            "hook_strength": 1.0,
            "novelty": 1.0,
            "authenticity": 1.0,
            "shareability": 1.0,
            "saveability": 1.0,
            "platform_fit": 1.0,
        },
        "ai_smell": {
            "enabled": True,
            "penalty_divisor": 20.0,
        },
        "scale": 10.0,
        "round_digits": 0,
        "max_score": 100.0,
        "min_score": 0.0,
    },
    "account_consistency": {
        "formula": "weighted_mean_with_penalty_and_caps",
        "dimensions": {
            "target_audience_fit": 1.4,
            "domain_fit": 1.6,
            "content_pillar_fit": 1.2,
            "value_promise_fit": 1.2,
            "voice_style_fit": 1.3,
            "perspective_fit": 1.0,
            "reference_account_alignment": 0.8,
            "platform_format_fit": 0.7,
        },
        "penalties": {
            "off_domain_topic": 15,
            "wrong_audience": 12,
            "style_conflict": 10,
            "over_imitation": 10,
            "brand_risk": 15,
        },
        "caps": {
            "domain_fit_lte_4": 65,
            "target_audience_fit_lte_4": 70,
            "severe_brand_risk": 60,
        },
        "round_digits": 0,
        "max_score": 100.0,
        "min_score": 0.0,
    },
    "risk_audit": {
        "enabled": True,
        "require_user_confirmation_for": [
            "数据/比例/金额/价格/时间/排名",
            "亲身经历/案例/客户结果",
            "医学/法律/投资/教育升学等高风险判断",
            "功效承诺/收益承诺/绝对化表述",
            "原文没有提供、但改写中新出现的具体事实",
        ],
        "platform_sensitive_topics": {
            "common": [
                "医疗健康",
                "金融投资",
                "法律建议",
                "夸大功效",
                "搬运/洗稿",
                "引战/人身攻击",
                "未授权图片/素材",
            ],
            "weixin": ["标题党诱导分享", "医疗金融绝对化判断"],
            "zhihu": ["缺少来源的专业判断", "编造经历或案例"],
            "linkedin": ["夸大职业成就", "未证实商业数据"],
        },
    },
    "learning_report": {
        "items_per_account": 5,
        "limit_per_account": 20,
        "crawl": True,
        "rank": True,
    },
    "account_reference_samples": {
        "enabled": True,
        "items_per_account": 3,
        "limit_per_account": 20,
        "crawl": True,
        "rank": True,
        "use_as_style_guardrail": True,
    },
    "output": {
        "timestamp_format": "%Y%m%d-%H%M%S",
        "files": {
            "testcase": "testcase.md",
            "trends": "trends.json",
            "reference_examples": "reference_examples.json",
            "account_reference_examples": "account_reference_examples.json",
            "critique": "critique.json",
            "rewrite": "rewrite.md",
            "source_links": "source_links.json",
            "account_consistency": "account_consistency.json",
            "risk_audit": "risk_audit.json",
            "learning_raw": "learning_raw.json",
            "learning_report": "learning_report.md",
        },
    },
}

# Map provider name -> the config key / env var holding its API key.
# Env var wins over the config file. Env var name is TREND_<KEY>.
PROVIDER_KEYS = {
    "tavily": "tavily_api_key",
    "exa": "exa_api_key",
    "firecrawl": "firecrawl_api_key",
    "crawl4ai": None,  # local library, no API key required
}


def load_config() -> dict:
    """Load the credentials config file, or return {} if it doesn't exist."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base without mutating either input."""
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def resolve_account_dir(account_dir: Optional[str] = None) -> Optional[Path]:
    """Resolve a selected myaccount/{account_id} directory, if one is set."""
    raw = account_dir or os.environ.get(ACCOUNT_DIR_ENV, "")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = SKILL_ROOT / path
    return path


def account_file(filename: str, account_dir: Optional[str] = None) -> Path:
    """Return a config file path for the selected account or legacy root config."""
    selected = resolve_account_dir(account_dir)
    if selected is not None:
        return selected / filename
    return MYACCOUNT_DIR / filename


def load_para_config(path: Optional[str] = None, account_dir: Optional[str] = None) -> dict:
    """Load selected account para_config.yaml merged onto safe defaults."""
    path = path or ("" if account_dir else os.environ.get(PARA_CONFIG_ENV, ""))
    config_path = Path(path) if path else account_file(PARA_CONFIG_NAME, account_dir)
    if not config_path.is_absolute():
        config_path = SKILL_ROOT / config_path
    if not config_path.exists():
        return deepcopy(DEFAULT_PARA_CONFIG)
    if yaml is None:
        return deepcopy(DEFAULT_PARA_CONFIG)
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        loaded = {}
    return _deep_merge(DEFAULT_PARA_CONFIG, loaded)


def deep_get(data: dict, path: str, default=None):
    """Read dotted-path config values."""
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def save_config(config: dict) -> None:
    """Write the config file to ~/.trend-improver/config.json with mode 0600."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    # Restrict to owner read/write only — these are secrets.
    os.chmod(CONFIG_PATH, 0o600)


def get_api_key(provider: str, config: Optional[dict] = None) -> Optional[str]:
    """Resolve a provider's API key from env var first, then the config file.

    Env var name is TREND_<CONFIG_KEY_UPPER>, e.g. TREND_TAVILY_API_KEY.
    Returns None when no key is configured (the offline / V1 path).
    """
    config_key = PROVIDER_KEYS.get(provider)
    if config_key is None:
        return None  # crawl4ai or unknown provider — no key concept

    env_name = "TREND_" + config_key.upper()
    env_value = os.environ.get(env_name)
    if env_value:
        return env_value

    if config is None:
        config = load_config()
    value = config.get(config_key)
    return value or None


def configured_providers(config: Optional[dict] = None) -> list:
    """Return provider names that currently have a usable key, in preference order.

    Used by --provider auto. crawl4ai is excluded from auto-selection because it
    needs a locally installed library rather than a key; request it explicitly.
    """
    if config is None:
        config = load_config()
    order = ["tavily", "exa", "firecrawl"]
    return [p for p in order if get_api_key(p, config)]


def request_with_retry(
    do_request: Callable,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> "object":
    """Call do_request(); retry with exponential backoff on HTTP 429.

    do_request must return a `requests.Response`. On status 429 we honor the
    Retry-After header if present, else back off backoff_base * 2**attempt
    seconds. Other status codes are returned to the caller as-is. The `sleep`
    arg is injectable so tests don't actually wait.
    """
    last_response = None
    for attempt in range(max_retries):
        response = do_request()
        last_response = response
        if getattr(response, "status_code", None) != 429:
            return response

        if attempt == max_retries - 1:
            break  # out of retries — return the 429 below

        retry_after = response.headers.get("Retry-After") if hasattr(response, "headers") else None
        if retry_after:
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = backoff_base * (2 ** attempt)
        else:
            delay = backoff_base * (2 ** attempt)
        sleep(delay)

    return last_response


def make_result(
    title: str = "",
    url: str = "",
    snippet: str = "",
    score: Optional[float] = None,
    published: str = "",
) -> dict:
    """Build one normalized result item. All providers map their fields here."""
    return {
        "title": title or "",
        "url": url or "",
        "snippet": snippet or "",
        "score": score,
        "published": published or "",
    }


def infer_account_from_url(url: str, platform: str = "") -> str:
    """Best-effort public account/handle inference from a result URL.

    This is only a fallback for providers/search pages that do not expose author
    metadata. Prefer real `account` / `author` fields when providers return them.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return ""

    host = (parsed.netloc or "").lower()
    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        return ""

    p = (platform or "").lower()
    first = parts[0]
    second = parts[1] if len(parts) > 1 else ""

    if p in {"twitter", "x"} or "twitter.com" in host or host == "x.com":
        if first.lower() not in {"i", "home", "search", "intent", "share", "hashtag"}:
            return "@" + first
    if p == "linkedin" or "linkedin.com" in host:
        if first in {"in", "company", "school", "showcase"} and second:
            return second
        if first == "posts" and second:
            return second.split("_")[0]
        if first == "pulse" and second:
            tokens = [t for t in second.split("-") if t]
            if len(tokens) >= 3 and re.fullmatch(r"[a-z0-9]{4,10}", tokens[-1], re.I):
                tokens = tokens[:-1]
            if len(tokens) >= 2:
                return " ".join(tokens[-2:]).title()
    if p == "bilibili" or "bilibili.com" in host:
        if first == "space" and second:
            return second
    if p == "zhihu" or "zhihu.com" in host:
        if first in {"people", "org", "column"} and second:
            return second
    if p == "weibo" or "weibo" in host:
        if first in {"u", "profile"} and second:
            return second
        if first and first not in {"detail", "status", "search"}:
            return first
    if p == "douban" or "douban.com" in host:
        if first == "people" and second:
            return second
        if first == "group" and second:
            return second
    if p == "xiaohongshu" or "xiaohongshu.com" in host:
        if first == "user" and second == "profile" and len(parts) > 2:
            return parts[2]
    if p == "hupu" or "hupu.com" in host:
        if first in {"user", "profile"} and second:
            return second
    return ""


def infer_account_from_text(text: str) -> str:
    """Best-effort author extraction from snippets/titles."""
    if not text:
        return ""
    patterns = [
        r"(?:作者|博主|账号|公众号|UP主|发布者|来自)[:：\s]+([^\s，,。｜|·\-—]{2,32})",
        r"by\s+([A-Za-z0-9_.@\- ]{2,40})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def fill_identity(result: dict, platform: str = "", fallback: str = "") -> dict:
    """Populate `account` and `author` consistently, without overwriting real data."""
    account = (result.get("account") or "").strip()
    author = (result.get("author") or "").strip()
    source_account = (result.get("source_account") or "").strip()
    inferred = (
        account
        or author
        or source_account
        or infer_account_from_text(" ".join([
            str(result.get("title", "")),
            str(result.get("snippet", "")),
        ]))
        or infer_account_from_url(result.get("url", ""), platform)
        or fallback
    )
    if inferred:
        result.setdefault("account", inferred)
        result.setdefault("author", inferred)
        if not result.get("account"):
            result["account"] = inferred
        if not result.get("author"):
            result["author"] = inferred
    return result


def make_envelope(query: str, platform: str, provider: str, results: list) -> dict:
    """Build the top-level normalized response written to outputs/trends.json."""
    return {
        "query": query,
        "platform": platform,
        "provider": provider,
        "mode": "online",
        "results": results,
    }


def offline_envelope(query: str, platform: str, reason: str) -> dict:
    """Envelope returned when no provider is configured — signals V1 fallback."""
    return {
        "query": query,
        "platform": platform,
        "provider": None,
        "mode": "offline",
        "reason": reason,
        "results": [],
    }
