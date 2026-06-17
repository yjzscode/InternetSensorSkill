#!/usr/bin/env python3
"""Collect reference-account posts for the learning-report workflow.

The script reads the selected account's reference_accounts.md, searches each account on its
platform through the existing retrieval dispatcher, ranks results by real
vibe_score, and writes a raw JSON bundle for prompts/learning_report.md.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from . import _common, retrieve
    from .cdp_client import ConsentRequired
except ImportError:  # run as a standalone script, not a package module
    import _common
    import retrieve
    from cdp_client import ConsentRequired


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _slug(text: str, default: str = "learning-report") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text or "").strip("-").lower()
    return slug[:80] or default


def _timestamp(config: dict) -> str:
    fmt = _common.deep_get(config, "output.timestamp_format", "%Y%m%d-%H%M%S")
    return datetime.now().strftime(fmt)


def default_output_dir(platform: str, config: dict) -> Path:
    label = "learning-report"
    return PROJECT_ROOT / "outputs" / (platform or "all-platforms") / f"{_timestamp(config)}-{label}"


def _normalize(text: str) -> str:
    return re.sub(r"[\s@_\-·.]+", "", (text or "").lower())


def _account_match_confidence(result: dict, account: dict, platform: str) -> str:
    name = account.get("account_name", "")
    homepage = account.get("homepage_url", "")
    expected = [name, _common.infer_account_from_url(homepage, platform)]
    expected_norm = [_normalize(v) for v in expected if v]

    identity_fields = [
        result.get("account", ""),
        result.get("author", ""),
        result.get("source_account", ""),
    ]
    for field in identity_fields:
        field_norm = _normalize(field)
        if field_norm and any(e and (e in field_norm or field_norm in e) for e in expected_norm):
            return "identity_match"

    inferred = _common.infer_account_from_url(result.get("url", ""), platform)
    inferred_norm = _normalize(inferred)
    if inferred_norm and any(e and (e in inferred_norm or inferred_norm in e) for e in expected_norm):
        return "url_handle_match"

    # Search listings sometimes omit author metadata but include the account name
    # in title/snippet. Keep these only as low-confidence candidates.
    searchable = _normalize(" ".join([result.get("title", ""), result.get("snippet", "")]))
    if searchable and any(e and e in searchable for e in expected_norm):
        return "text_match_low_confidence"
    return ""


def _record(result: dict, account: dict, platform: str, confidence: str) -> dict:
    row = dict(result)
    _common.fill_identity(row, platform, fallback=account.get("account_name", ""))
    return {
        "title": row.get("title", ""),
        "url": row.get("url", ""),
        "account": row.get("account", ""),
        "author": row.get("author", ""),
        "published": row.get("published", ""),
        "snippet": row.get("snippet", ""),
        "engagement": row.get("engagement", {}),
        "vibe_score": row.get("vibe_score"),
        "source_account": account.get("account_name", ""),
        "source_account_url": account.get("homepage_url", ""),
        "source_type": "account_reference",
        "reference_role": "account_style",
        "match_confidence": confidence,
    }


def _account_query(account: dict, platform: str) -> str:
    name = account.get("account_name", "")
    homepage = account.get("homepage_url", "")
    learn_what = account.get("learn_what", "")
    platform = (platform or account.get("platform", "")).lower()
    if platform == "linkedin" and homepage:
        return f"{name} {homepage} posts"
    if platform in {"twitter", "x"} and homepage:
        return f"{name} {homepage}"
    if platform == "weixin":
        return name
    if platform == "douban" and learn_what:
        return learn_what
    return name


def collect_account(account: dict, config: dict, provider: str, platform: str,
                    limit: int, items_n: int, consent: bool) -> dict:
    account_platform = platform or account.get("platform", "")
    query = _account_query(account, account_platform)
    status = "ok"
    reason = ""
    envelope = None
    try:
        _, envelope = retrieve.dispatch(
            query,
            account_platform,
            provider,
            _common.load_config(),
            limit=limit,
            consent=consent,
        )
    except ConsentRequired as exc:
        status = "consent_required"
        reason = str(exc)
    except Exception as exc:
        status = "error"
        reason = str(exc)

    if envelope is None:
        return {
            "account": account,
            "status": status,
            "reason": reason,
            "collected_count": 0,
            "items": [],
        }

    learning_cfg = config.get("learning_report", {})
    should_rank = bool(learning_cfg.get("rank", True))
    if should_rank:
        envelope = retrieve.enrich_and_rank(
            envelope,
            crawl=bool(learning_cfg.get("crawl", True)),
            top_n=0,
            min_vibe=_common.deep_get(config, "retrieval.min_vibe"),
        )

    matched = []
    low_confidence = []
    for result in envelope.get("results", []):
        _common.fill_identity(result, account_platform)
        confidence = _account_match_confidence(result, account, account_platform)
        if confidence in {"identity_match", "url_handle_match"}:
            matched.append(_record(result, account, account_platform, confidence))
        elif confidence:
            low_confidence.append(_record(result, account, account_platform, confidence))

    selected = matched[:items_n]
    candidate_items = low_confidence[:items_n]
    if not selected:
        status = "no_account_matched_results"
        reason = "Search returned results, but none could be tied back to the account identity."

    return {
        "account": account,
        "status": status,
        "reason": reason,
        "query": query,
        "provider": envelope.get("provider"),
        "ranked_by": envelope.get("ranked_by", "provider_order"),
        "raw_result_count": len(envelope.get("results", [])),
        "collected_count": len(selected),
        "items": selected,
        "candidate_items": candidate_items,
    }


def collect_report(platform: str, accounts_path: str, config: dict, provider: str,
                   limit: int, items_n: int, consent: bool) -> dict:
    accounts = retrieve.load_reference_accounts(accounts_path, platform)
    account_reports = [
        collect_account(a, config, provider, platform, limit, items_n, consent)
        for a in accounts
    ]
    items = [item for account in account_reports for item in account.get("items", [])]
    scored = [item for item in items if item.get("vibe_score") is not None]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "platform": platform,
        "accounts_path": accounts_path,
        "provider": provider,
        "items_per_account": items_n,
        "accounts_count": len(accounts),
        "collected_items_count": len(items),
        "highest_vibe_score": max([i["vibe_score"] for i in scored], default=None),
        "accounts": account_reports,
    }


def account_reference_examples_bundle(report: dict) -> dict:
    """Flatten collect_report() into the rewrite-friendly examples schema."""
    examples = []
    for account_report in report.get("accounts", []):
        account = account_report.get("account", {})
        for item in account_report.get("items", []):
            row = dict(item)
            row["source_type"] = "account_reference"
            row["reference_role"] = "account_style"
            row["source_account"] = row.get("source_account") or account.get("account_name", "")
            row["source_account_url"] = row.get("source_account_url") or account.get("homepage_url", "")
            examples.append(row)
    return {
        "platform": report.get("platform", ""),
        "source": report.get("accounts_path", "reference_accounts.md"),
        "source_type": "account_reference",
        "reference_role": "account_style",
        "ranked_by": "account_identity_then_vibe_score",
        "accounts_count": report.get("accounts_count", 0),
        "count": len(examples),
        "examples": examples,
        "accounts": report.get("accounts", []),
    }


def write_json(data: dict, output: str) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect reference-account data")
    parser.add_argument("--account-dir", default="",
                        help="selected account directory, e.g. myaccount/xiaohongshu_main")
    parser.add_argument("--para-config", default="", help="YAML parameter config")
    parser.add_argument("--platform", default="", help="platform to report on; blank = active rows on all platforms")
    parser.add_argument("--reference-accounts", default="", help="Markdown table of reference account homepages")
    parser.add_argument("--provider", default=None, help="retrieval provider; default from para_config.retrieval.provider")
    parser.add_argument("--items-per-account", type=int, default=None, help="items to keep per account")
    parser.add_argument("--limit-per-account", type=int, default=None, help="search limit per account")
    parser.add_argument("--output-dir", default="", help="directory for learning_raw.json")
    parser.add_argument("--output", default="", help="write raw JSON here; overrides output-dir filename")
    parser.add_argument("--purpose", choices=["learning_report", "account_reference_examples"],
                        default="learning_report",
                        help="output schema: learning report raw data or rewrite-friendly account examples")
    parser.add_argument("--consent", action="store_true", help="consent to use browser-backed providers")
    args = parser.parse_args(argv)

    if args.account_dir:
        os.environ[_common.ACCOUNT_DIR_ENV] = args.account_dir
    if args.para_config:
        os.environ[_common.PARA_CONFIG_ENV] = args.para_config
    config = _common.load_para_config(args.para_config or None, args.account_dir or None)
    retrieval_cfg = config.get("retrieval", {})
    learning_cfg = config.get("learning_report", {})
    account_samples_cfg = config.get("account_reference_samples", {})
    ref_cfg = retrieval_cfg.get("reference_accounts", {})

    provider = args.provider or retrieval_cfg.get("provider", "auto")
    if args.purpose == "account_reference_examples":
        default_items = int(account_samples_cfg.get("items_per_account", 3))
        default_limit = int(account_samples_cfg.get("limit_per_account", 20))
    else:
        default_items = int(learning_cfg.get("items_per_account", 5))
        default_limit = int(learning_cfg.get("limit_per_account", 20))
    items_n = args.items_per_account if args.items_per_account is not None else default_items
    limit = args.limit_per_account if args.limit_per_account is not None else default_limit

    if args.reference_accounts:
        accounts_path = retrieve._resolve_skill_path(args.reference_accounts)
    else:
        selected_account_dir = (
            _common.resolve_account_dir(args.account_dir or None)
            or retrieve._infer_account_dir_from_para_config(args.para_config)
        )
        accounts_path = retrieve._resolve_reference_accounts_path(
            ref_cfg.get("path", "myaccount/reference_accounts.md"),
            selected_account_dir,
        )

    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(args.platform, config)
    output_files = _common.deep_get(config, "output.files", {})
    if args.purpose == "account_reference_examples":
        output_name = output_files.get("account_reference_examples", "account_reference_examples.json")
    else:
        output_name = output_files.get("learning_raw", "learning_raw.json")
    output_path = Path(args.output) if args.output else output_dir / output_name

    effective_config = dict(config)
    if args.purpose == "account_reference_examples":
        effective_config["learning_report"] = {
            **config.get("learning_report", {}),
            **account_samples_cfg,
        }
    report = collect_report(args.platform, accounts_path, effective_config, provider, limit, items_n, args.consent)
    report["output_dir"] = str(output_path.parent)
    report["output_file"] = str(output_path)
    payload = account_reference_examples_bundle(report) if args.purpose == "account_reference_examples" else report
    write_json(payload, str(output_path))
    print(f"Wrote {args.purpose} data: {output_path} ({report['collected_items_count']} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
