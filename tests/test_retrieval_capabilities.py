#!/usr/bin/env python3
"""Capability tests for retrieval's real-search vs V1-fallback paths.

These tests classify the retrieval layer without making live network calls:
- Bilibili has a native key-free real provider with structured engagement.
- Keyed platforms route to real REST web-search providers using site: targeting.
- Unkeyed non-native platforms fall back to V1/offline.
- Registered providers must contain real external I/O, not static mocked returns.
"""

import inspect
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
import bilibili  # noqa: E402
import crawl4ai  # noqa: E402
import exa  # noqa: E402
import firecrawl  # noqa: E402
import retrieve  # noqa: E402
import strategy  # noqa: E402
import tavily  # noqa: E402
import weibo  # noqa: E402


# Platforms served by the key-free SearXNG/DuckDuckGo provider (no platform API,
# no API key — site:-scoped web search through the user's browser).
SEARXNG_PLATFORMS = ("twitter", "linkedin")

# Platforms served by the CDP provider (the user's logged-in browser).
# 微博 joined this group after m.weibo.cn started blocking server-side requests.
CDP_NATIVE_PLATFORMS = ("xiaohongshu", "zhihu", "weixin", "douban", "hupu", "weibo")


class TestRealTrendRetrievalRoutes(unittest.TestCase):
    def test_bilibili_can_retrieve_real_trends_without_key(self):
        self.assertEqual(strategy.native_provider("bilibili"), "bilibili")
        self.assertIn("bilibili", retrieve.NATIVE_PROVIDERS)

        envelope = _common.make_envelope("完美世界", "bilibili", "bilibili", [
            {
                "title": "真实 B站结果",
                "url": "https://www.bilibili.com/video/BV1",
                "snippet": "",
                "score": 460000,
                "published": "2026-05-01",
                "engagement": {
                    "likes": 12000,
                    "comments": 300,
                    "saves": 8000,
                    "shares": None,
                },
            },
        ])
        with mock.patch.object(retrieve.bilibili, "search", return_value=envelope) as search:
            name, result = retrieve.dispatch("完美世界", "bilibili", "auto", {}, limit=8)

        self.assertEqual(name, "bilibili")
        self.assertEqual(result["mode"], "online")
        search.assert_called_once_with("完美世界", limit=8, platform="bilibili")

    def test_weibo_routes_via_cdp_browser(self):
        # m.weibo.cn now blocks server-side requests (HTTP 432), so weibo is served
        # by the CDP provider (logged-in browser), which still returns engagement.
        self.assertEqual(strategy.native_provider("weibo"), "cdp")
        self.assertIn("cdp", retrieve.NATIVE_PROVIDERS)

        envelope = _common.make_envelope("热搜", "weibo", "cdp:weibo", [
            {
                "title": "真实微博结果",
                "url": "https://m.weibo.cn/detail/1",
                "snippet": "真实微博结果",
                "score": 1000,
                "published": "刚刚",
                "engagement": {
                    "likes": 1000,
                    "comments": 80,
                    "saves": None,
                    "shares": 50,
                },
            },
        ])
        with mock.patch.object(retrieve.cdp_platforms, "search", return_value=envelope) as search:
            name, result = retrieve.dispatch("热搜", "weibo", "auto", {}, limit=8,
                                             consent=True)

        self.assertEqual(name, "cdp")
        self.assertEqual(result["mode"], "online")
        search.assert_called_once_with("热搜", limit=8, platform="weibo", consent=True)

    def test_searxng_platforms_have_targeted_websearch_routes(self):
        # twitter/linkedin use the key-free searxng provider, scoped via site:.
        for platform in SEARXNG_PLATFORMS:
            with self.subTest(platform=platform):
                self.assertEqual(strategy.native_provider(platform), "searxng")
                query = strategy.build_targeted_query("topic", platform)
                sites = strategy.get_strategy(platform)["sites"]
                for site in sites:
                    self.assertIn(f"site:{site}", query)

                envelope = _common.make_envelope(query, platform, "searxng:ddg", [])
                with mock.patch.dict(os.environ, {}, clear=True), \
                     mock.patch.object(retrieve.searxng, "search", return_value=envelope) as search:
                    name, result = retrieve.dispatch(
                        "topic", platform, "auto", {}, limit=3, consent=True
                    )

                self.assertEqual(name, "searxng")
                self.assertEqual(result["mode"], "online")
                targeted = search.call_args.args[0]
                for site in sites:
                    self.assertIn(f"site:{site}", targeted)

    def test_searxng_platforms_require_consent_without_instance(self):
        # With no SearXNG instance configured, the DDG-via-browser fallback needs
        # consent, so dispatch must raise ConsentRequired (never silent-empty).
        from cdp_client import ConsentRequired
        for platform in SEARXNG_PLATFORMS:
            with self.subTest(platform=platform):
                with mock.patch.dict(os.environ, {}, clear=True), \
                     self.assertRaises(ConsentRequired):
                    retrieve.dispatch("topic", platform, "auto", {}, limit=3,
                                      consent=False)

    def test_cdp_platforms_route_to_browser_native(self):
        # 小红书/知乎/微信公众号 use the CDP provider (the user's logged-in browser),
        # not keyed web search. No API key needed for auto-selection.
        for platform in CDP_NATIVE_PLATFORMS:
            with self.subTest(platform=platform):
                self.assertEqual(strategy.native_provider(platform), "cdp")
                self.assertIn("cdp", retrieve.NATIVE_PROVIDERS)
                env = _common.make_envelope("topic", platform, f"cdp:{platform}", [])
                with mock.patch.dict(os.environ, {}, clear=True), \
                     mock.patch.object(retrieve.cdp_platforms, "search", return_value=env) as search:
                    name, result = retrieve.dispatch("topic", platform, "auto", {}, limit=3)
                self.assertEqual(name, "cdp")
                self.assertEqual(search.call_args.kwargs.get("platform"), platform)

    def test_main_writes_consent_required_for_searxng_platform(self):
        # linkedin uses the searxng/DDG fallback which drives the browser; with no
        # SearXNG instance and no consent, main must write a consent_required
        # envelope (NOT offline) and exit 0 so the skill knows to ask the user.
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}), \
             tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "trends.json")
            rc = retrieve.main([
                "--provider", "auto",
                "--topic", "career growth",
                "--platform", "linkedin",
                "--output", output,
            ])
            self.assertEqual(rc, 0)
            with open(output, encoding="utf-8") as f:
                data = json.load(f)

        self.assertEqual(data["mode"], "consent_required")
        self.assertTrue(data["consent_required"])
        self.assertEqual(data["results"], [])


class TestNoMockedOnlyProviders(unittest.TestCase):
    def test_registered_rest_providers_use_real_http_apis(self):
        providers = {
            "tavily": tavily,
            "exa": exa,
            "firecrawl": firecrawl,
        }
        for name, module in providers.items():
            with self.subTest(provider=name):
                source = inspect.getsource(module.search)
                self.assertTrue(module.API_URL.startswith("https://"))
                self.assertIn("requests.post", source)
                self.assertIn("raise_for_status", source)
                self.assertNotIn("mock", source.lower())

    def test_bilibili_provider_uses_real_native_api(self):
        source = inspect.getsource(bilibili.search)
        self.assertTrue(bilibili.SEARCH_URL.startswith("https://api.bilibili.com/"))
        self.assertIn("session.get", source)
        self.assertIn("raise_for_status", source)
        self.assertIn("engagement", source)
        self.assertNotIn("mock", source.lower())

    def test_weibo_provider_uses_real_native_api(self):
        source = inspect.getsource(weibo.search)
        self.assertTrue(weibo.API_URL.startswith("https://m.weibo.cn/"))
        self.assertIn("session.get", source)
        self.assertIn("raise_for_status", source)
        self.assertIn("engagement", source)
        self.assertNotIn("mock", source.lower())

    def test_crawl4ai_provider_uses_real_crawler_library(self):
        source = inspect.getsource(crawl4ai._crawl)
        self.assertIn("AsyncWebCrawler", source)
        self.assertIn("crawler.arun", source)
        self.assertNotIn("mock", source.lower())


if __name__ == "__main__":
    unittest.main()
