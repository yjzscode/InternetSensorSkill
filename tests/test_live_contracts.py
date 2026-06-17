#!/usr/bin/env python3
"""Opt-in live contract tests for providers that mocks cannot protect.

These tests are skipped by default so CI and local unit runs stay offline. Enable
them manually when validating real platform contracts:

    TREND_LIVE_BILIBILI=1 .venv/bin/python -m unittest tests/test_live_contracts.py -v
    TREND_LIVE_CDP=1 TREND_LIVE_CDP_PLATFORM=douban \
      .venv/bin/python -m unittest tests/test_live_contracts.py -v

The CDP test requires explicit env opt-in because it may drive the user's real
logged-in browser via web-access.
"""

import os
import sys
import unittest

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import bilibili  # noqa: E402
import cdp_platforms  # noqa: E402
import searxng  # noqa: E402


class TestLiveProviderContracts(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("TREND_LIVE_BILIBILI") == "1",
                         "set TREND_LIVE_BILIBILI=1 to hit live Bilibili")
    def test_live_bilibili_contract(self):
        env = bilibili.search("完美世界", limit=3, platform="bilibili")
        self.assertEqual(env["mode"], "online")
        self.assertEqual(env["provider"], "bilibili")
        self.assertGreater(len(env["results"]), 0)
        first = env["results"][0]
        self.assertTrue(first.get("title"))
        self.assertIn("engagement", first)

    @unittest.skipUnless(os.environ.get("TREND_LIVE_CDP") == "1",
                         "set TREND_LIVE_CDP=1 to drive the real browser")
    def test_live_cdp_contract(self):
        platform = os.environ.get("TREND_LIVE_CDP_PLATFORM", "douban")
        query = os.environ.get("TREND_LIVE_CDP_QUERY", "电影")
        env = cdp_platforms.search(query, platform=platform, limit=3, consent=True)
        self.assertEqual(env["mode"], "online")
        self.assertEqual(env["provider"], f"cdp:{cdp_platforms.resolve_platform(platform)}")
        self.assertGreater(len(env["results"]), 0)
        first = env["results"][0]
        self.assertTrue(first.get("title"))
        self.assertIn("engagement", first)

    @unittest.skipUnless(os.environ.get("TREND_LIVE_SEARXNG") == "1",
                         "set TREND_LIVE_SEARXNG=1 to run key-free web search live")
    def test_live_searxng_contract(self):
        # Uses a SearXNG instance if TREND_SEARXNG_URL is set, else DuckDuckGo via
        # the user's browser (consent=True). Default platform: twitter.
        platform = os.environ.get("TREND_LIVE_SEARXNG_PLATFORM", "twitter")
        query = os.environ.get("TREND_LIVE_SEARXNG_QUERY", "AI agents")
        import strategy
        targeted = strategy.build_targeted_query(query, platform)
        env = searxng.search(targeted, platform=platform, limit=5, consent=True)
        self.assertEqual(env["mode"], "online")
        self.assertTrue(str(env["provider"]).startswith("searxng"))
        # A challenge/ratelimit is a valid live outcome — only assert structure.
        if not env.get("login_required"):
            self.assertGreater(len(env["results"]), 0)
            first = env["results"][0]
            self.assertTrue(first.get("title"))
            self.assertTrue(first.get("url"))


if __name__ == "__main__":
    unittest.main()
