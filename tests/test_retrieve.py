#!/usr/bin/env python3
"""Tests for the retrieve.py dispatcher.

Covers query building, auto provider selection, the no-key → offline fallback,
network-error → offline degradation, and that results get traction-ranked. All
provider calls and HTTP are mocked.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import _common  # noqa: E402
import retrieve  # noqa: E402


class TestBuildQuery(unittest.TestCase):
    def test_explicit_query_wins(self):
        self.assertEqual(retrieve.build_query("food", "xiaohongshu", "my query"), "my query")

    def test_composed_from_topic(self):
        # Base query is just the subject; targeting is applied later by strategy.
        q = retrieve.build_query("校园美食", "xiaohongshu", "")
        self.assertEqual(q, "校园美食")


class TestDispatch(unittest.TestCase):
    def test_auto_prefers_native_for_bilibili(self):
        # bilibili has a native key-free provider → no config needed.
        envelope = _common.make_envelope("完美世界", "bilibili", "bilibili", [])
        with mock.patch.object(retrieve.bilibili, "search", return_value=envelope) as bili:
            name, env = retrieve.dispatch("完美世界", "bilibili", "auto", {}, limit=5)
        self.assertEqual(name, "bilibili")
        bili.assert_called_once()
        # native provider is called positionally with the base query
        self.assertEqual(bili.call_args.args[0], "完美世界")

    def test_auto_twitter_uses_searxng_with_targeted_query(self):
        # twitter's native provider is the key-free searxng/DDG search; auto must
        # call it with a site:-targeted query and forward consent.
        envelope = _common.make_envelope("q", "twitter", "searxng:ddg", [])
        with mock.patch.object(retrieve.searxng, "search", return_value=envelope) as sx:
            name, env = retrieve.dispatch("AI agents", "twitter",
                                          "auto", {}, limit=5, consent=True)
        self.assertEqual(name, "searxng")
        targeted = sx.call_args.args[0]
        self.assertIn("site:twitter.com", targeted)
        self.assertIn("AI agents", targeted)
        self.assertEqual(sx.call_args.kwargs.get("consent"), True)

    def test_explicit_bilibili_provider(self):
        envelope = _common.make_envelope("q", "bilibili", "bilibili", [])
        with mock.patch.object(retrieve.bilibili, "search", return_value=envelope):
            name, env = retrieve.dispatch("q", "bilibili", "bilibili", {}, limit=5)
        self.assertEqual(name, "bilibili")

    def test_no_keyed_provider_returns_none(self):
        # A platform with no native provider and no key configured → (None, None).
        # (Use an unknown platform: twitter/linkedin now have the searxng native.)
        with mock.patch.dict(os.environ, {}, clear=True):
            name, env = retrieve.dispatch("q", "some-unknown-platform", "auto", {}, limit=5)
        self.assertIsNone(name)
        self.assertIsNone(env)


class TestResolveProvider(unittest.TestCase):
    def test_auto_picks_first_configured(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            name, module = retrieve.resolve_provider("auto", {"exa_api_key": "k"})
        self.assertEqual(name, "exa")
        self.assertIs(module, retrieve.exa)

    def test_auto_none_when_unconfigured(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            name, module = retrieve.resolve_provider("auto", {})
        self.assertIsNone(name)
        self.assertIsNone(module)

    def test_named_provider_requires_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            name, module = retrieve.resolve_provider("tavily", {})
        self.assertIsNone(module)


class TestEnrichAndRank(unittest.TestCase):
    def test_ranks_results_by_vibe_score(self):
        envelope = _common.make_envelope("q", "xiaohongshu", "tavily", [
            {"title": "low", "snippet": "点赞 10", "url": "", "score": None, "published": "100天前"},
            {"title": "high", "snippet": "收藏 5万", "url": "", "score": None, "published": "1天前"},
        ])
        ranked = retrieve.enrich_and_rank(envelope, crawl=False)
        self.assertEqual(ranked["ranked_by"], "vibe_score")
        # The high-saves, recent post should rank first.
        self.assertEqual(ranked["results"][0]["title"], "high")
        self.assertIn("vibe_score", ranked["results"][0])


class TestMainOfflineFallback(unittest.TestCase):
    def test_no_provider_writes_offline_envelope_and_exits_0(self):
        # An unknown platform has no native provider and no key → offline V1, exit 0.
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            rc = retrieve.main([
                "--provider", "auto", "--topic", "AI agents",
                "--platform", "some-unknown-platform", "--output", out,
            ])
            self.assertEqual(rc, 0)
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["mode"], "offline")
        self.assertEqual(data["results"], [])

    def test_twitter_without_consent_writes_consent_required_and_exits_0(self):
        # twitter's searxng/DDG fallback drives the browser → without consent it
        # must emit a consent_required envelope (NOT offline), exit 0.
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            rc = retrieve.main([
                "--provider", "auto", "--topic", "AI agents",
                "--platform", "twitter", "--output", out,
            ])
            self.assertEqual(rc, 0)
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["mode"], "consent_required")
        self.assertTrue(data["consent_required"])

    def test_network_error_degrades_to_offline(self):
        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        with mock.patch.dict(os.environ, {"TREND_TAVILY_API_KEY": "k"}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.tavily, "search", side_effect=boom), \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            rc = retrieve.main(["--provider", "tavily", "--query", "q", "--output", out])
            self.assertEqual(rc, 0)
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["mode"], "offline")

    def test_success_path_writes_ranked_results(self):
        envelope = _common.make_envelope("q", "xiaohongshu", "tavily", [
            {"title": "post", "snippet": "收藏 2万", "url": "", "score": None, "published": "2天前"},
        ])
        with mock.patch.dict(os.environ, {"TREND_TAVILY_API_KEY": "k"}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.tavily, "search", return_value=envelope), \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            rc = retrieve.main([
                "--provider", "tavily", "--topic", "校园美食",
                "--platform", "xiaohongshu", "--output", out,
            ])
            self.assertEqual(rc, 0)
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["mode"], "online")
        self.assertEqual(data["ranked_by"], "vibe_score")
        self.assertIsNotNone(data["results"][0]["vibe_score"])

    def test_no_rank_flag_skips_ranking(self):
        envelope = _common.make_envelope("q", "xiaohongshu", "tavily", [
            {"title": "post", "snippet": "收藏 2万", "url": "", "score": None, "published": "2天前"},
        ])
        with mock.patch.dict(os.environ, {"TREND_TAVILY_API_KEY": "k"}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.tavily, "search", return_value=envelope), \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            retrieve.main([
                "--provider", "tavily", "--query", "q",
                "--platform", "xiaohongshu", "--output", out, "--no-rank",
            ])
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertNotIn("ranked_by", data)
        self.assertNotIn("vibe_score", data["results"][0])

    def test_crawl4ai_requires_url(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}):
            rc = retrieve.main(["--provider", "crawl4ai", "--query", "q"])
        self.assertEqual(rc, 2)

    def test_cdp_platform_without_consent_writes_consent_required(self):
        # 小红书 is CDP-native; without --consent, main must NOT drive the browser.
        # It writes a consent_required envelope (exit 0) so SKILL.md can ask first.
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "CDPClient") as fake_client, \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            rc = retrieve.main([
                "--provider", "auto", "--topic", "校园美食",
                "--platform", "xiaohongshu", "--output", out,
            ])
            self.assertEqual(rc, 0)
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["mode"], "consent_required")
        self.assertTrue(data["consent_required"])
        self.assertEqual(data["platform_native"], "cdp")
        # The browser client must never have been constructed.
        fake_client.assert_not_called()

    def test_cdp_platform_with_consent_runs_search(self):
        env = _common.make_envelope("校园美食", "xiaohongshu", "cdp:xiaohongshu", [
            {"title": "宝藏食堂", "snippet": "", "url": "https://www.xiaohongshu.com/explore/a",
             "score": None, "published": "", "engagement": {"likes": 5000, "comments": None,
                                                             "saves": None, "shares": None}},
        ])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "search", return_value=env) as cdp, \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            rc = retrieve.main([
                "--provider", "auto", "--topic", "校园美食",
                "--platform", "xiaohongshu", "--consent", "--output", out,
            ])
            self.assertEqual(rc, 0)
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
        self.assertTrue(cdp.call_args.kwargs.get("consent"))
        self.assertEqual(data["mode"], "online")
        self.assertIsNotNone(data["results"][0]["vibe_score"])

    def test_para_config_controls_retrieval_defaults(self):
        env = _common.make_envelope("校园美食", "xiaohongshu", "cdp:xiaohongshu", [
            {"title": "一", "snippet": "", "url": "u1", "score": None, "published": "1天前",
             "engagement": {"likes": 30000, "comments": None, "saves": None, "shares": None}},
            {"title": "二", "snippet": "", "url": "u2", "score": None, "published": "1天前",
             "engagement": {"likes": 20000, "comments": None, "saves": None, "shares": None}},
            {"title": "三", "snippet": "", "url": "u3", "score": None, "published": "1天前",
             "engagement": {"likes": 10000, "comments": None, "saves": None, "shares": None}},
        ])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "search", return_value=env) as cdp, \
             tempfile.TemporaryDirectory() as tmp:
            para = os.path.join(tmp, "para_config.yaml")
            with open(para, "w", encoding="utf-8") as f:
                f.write(
                    "retrieval:\n"
                    "  provider: auto\n"
                    "  limit: 7\n"
                    "  crawl: false\n"
                    "  top: 2\n"
                    "  examples_n: 1\n"
                    "  reference_accounts:\n"
                    "    enabled: false\n"
                )
            out = os.path.join(tmp, "trends.json")
            ex = os.path.join(tmp, "ref.json")
            retrieve.main([
                "--para-config", para,
                "--topic", "校园美食", "--platform", "xiaohongshu",
                "--consent", "--output", out, "--save-examples", ex,
            ])
            with open(out, "r", encoding="utf-8") as f:
                trends = json.load(f)
            with open(ex, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        self.assertEqual(cdp.call_args.kwargs.get("limit"), 7)
        self.assertEqual(len(trends["results"]), 2)
        self.assertEqual(bundle["count"], 1)

    def test_save_examples_writes_top_scored(self):
        env = _common.make_envelope("校园美食", "xiaohongshu", "cdp:xiaohongshu", [
            {"title": "高赞", "snippet": "", "url": "u1", "score": None, "published": "1天前",
             "engagement": {"likes": 30000, "comments": None, "saves": None, "shares": None},
             "author": "美食博主A"},
            {"title": "中赞", "snippet": "", "url": "u2", "score": None, "published": "1天前",
             "engagement": {"likes": 500, "comments": None, "saves": None, "shares": None}},
        ])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "search", return_value=env), \
             tempfile.TemporaryDirectory() as tmp:
            para = os.path.join(tmp, "para_config.yaml")
            with open(para, "w", encoding="utf-8") as f:
                f.write("retrieval:\n  reference_accounts:\n    enabled: false\n")
            out = os.path.join(tmp, "trends.json")
            ex = os.path.join(tmp, "ref.json")
            retrieve.main([
                "--para-config", para,
                "--provider", "auto", "--topic", "校园美食", "--platform", "xiaohongshu",
                "--consent", "--top", "1", "--output", out, "--save-examples", ex,
            ])
            with open(ex, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        self.assertEqual(bundle["count"], 1)
        self.assertEqual(bundle["examples"][0]["title"], "高赞")  # highest vibe_score kept
        self.assertIn("vibe_score", bundle["examples"][0])
        self.assertEqual(bundle["examples"][0]["account"], "美食博主A")
        self.assertEqual(bundle["examples"][0]["author"], "美食博主A")
        self.assertEqual(bundle["examples"][0]["source_type"], "trend_search")
        self.assertEqual(bundle["examples"][0]["reference_role"], "trend_hotspot")

    def test_reference_accounts_are_searched_and_marked(self):
        env = _common.make_envelope("美食博主A 校园美食", "xiaohongshu", "cdp:xiaohongshu", [
            {"title": "账号高赞", "snippet": "", "url": "https://www.xiaohongshu.com/explore/a",
             "score": None, "published": "1天前",
             "engagement": {"likes": 30000, "comments": None, "saves": None, "shares": None}},
        ])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "search", return_value=env) as cdp, \
             tempfile.TemporaryDirectory() as tmp:
            ref_path = os.path.join(tmp, "reference_accounts.md")
            with open(ref_path, "w", encoding="utf-8") as f:
                f.write(
                    "| platform | account_name | homepage_url | learn_what | notes |\n"
                    "|---|---|---|---|---|\n"
                    "| xiaohongshu | 美食博主A | https://www.xiaohongshu.com/user/profile/a | hook | |\n"
                )
            out = os.path.join(tmp, "trends.json")
            ex = os.path.join(tmp, "ref.json")
            retrieve.main([
                "--provider", "auto", "--topic", "校园美食", "--platform", "xiaohongshu",
                "--consent", "--examples-n", "1", "--output", out, "--save-examples", ex,
                "--reference-accounts", ref_path,
            ])
            with open(out, "r", encoding="utf-8") as f:
                trends = json.load(f)
            with open(ex, "r", encoding="utf-8") as f:
                bundle = json.load(f)

        self.assertIn("美食博主A", cdp.call_args.args[0])
        self.assertEqual(trends["results"][0]["source_type"], "reference_account")
        self.assertEqual(bundle["examples"][0]["source_account"], "美食博主A")

    def test_account_dir_supplies_para_config_and_reference_accounts(self):
        env = _common.make_envelope("账号A 校园美食", "xiaohongshu", "cdp:xiaohongshu", [
            {"title": "账号样本", "snippet": "", "url": "https://www.xiaohongshu.com/explore/a",
             "score": None, "published": "1天前",
             "engagement": {"likes": 1000, "comments": None, "saves": None, "shares": None}},
        ])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "search", return_value=env) as cdp, \
             tempfile.TemporaryDirectory() as tmp:
            account_dir = os.path.join(tmp, "xiaohongshu_main")
            os.makedirs(account_dir)
            with open(os.path.join(account_dir, "para_config.yaml"), "w", encoding="utf-8") as f:
                f.write(
                    "retrieval:\n"
                    "  provider: auto\n"
                    "  limit: 9\n"
                    "  crawl: false\n"
                    "  reference_accounts:\n"
                    "    enabled: true\n"
                )
            with open(os.path.join(account_dir, "reference_accounts.md"), "w", encoding="utf-8") as f:
                f.write(
                    "| platform | account_name | homepage_url | learn_what | notes |\n"
                    "|---|---|---|---|---|\n"
                    "| xiaohongshu | 账号A | https://www.xiaohongshu.com/user/profile/a | style | |\n"
                )
            out = os.path.join(tmp, "trends.json")
            retrieve.main([
                "--account-dir", account_dir,
                "--topic", "校园美食", "--platform", "xiaohongshu",
                "--consent", "--output", out,
            ])
            with open(out, "r", encoding="utf-8") as f:
                trends = json.load(f)

        self.assertTrue(any("账号A" in call.args[0] for call in cdp.call_args_list))
        self.assertTrue(all(call.kwargs.get("limit") == 9 for call in cdp.call_args_list))
        self.assertEqual(trends["results"][0]["source_type"], "reference_account")
        self.assertEqual(trends["results"][0]["source_account"], "账号A")

    def test_examples_n_is_independent_from_top(self):
        env = _common.make_envelope("校园美食", "xiaohongshu", "cdp:xiaohongshu", [
            {"title": "一", "snippet": "", "url": "u1", "score": None, "published": "1天前",
             "engagement": {"likes": 30000, "comments": None, "saves": None, "shares": None}},
            {"title": "二", "snippet": "", "url": "u2", "score": None, "published": "1天前",
             "engagement": {"likes": 20000, "comments": None, "saves": None, "shares": None}},
            {"title": "三", "snippet": "", "url": "u3", "score": None, "published": "1天前",
             "engagement": {"likes": 10000, "comments": None, "saves": None, "shares": None}},
        ])
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             mock.patch.object(retrieve.cdp_platforms, "search", return_value=env), \
             tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "trends.json")
            ex = os.path.join(tmp, "ref.json")
            retrieve.main([
                "--provider", "auto", "--topic", "校园美食", "--platform", "xiaohongshu",
                "--consent", "--top", "3", "--examples-n", "2",
                "--output", out, "--save-examples", ex,
            ])
            with open(out, "r", encoding="utf-8") as f:
                trends = json.load(f)
            with open(ex, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        self.assertEqual(len(trends["results"]), 3)
        self.assertEqual(bundle["count"], 2)


if __name__ == "__main__":
    unittest.main()
