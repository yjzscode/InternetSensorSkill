#!/usr/bin/env python3
"""Tests for the Bilibili native provider and the platform strategy registry.

Bilibili is key-free and returns structured engagement, so these tests assert:
- the warmup/search flow normalizes results and maps engagement fields
- <em> keyword tags are stripped from titles
- a non-zero API `code` raises (so the dispatcher degrades to offline)
- the strategy registry targets queries to the right platform (site: scoping)

HTTP is mocked via an injected fake session — no live calls.
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
import strategy  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Stands in for a warmed-up requests.Session; returns a canned search response."""

    def __init__(self, response):
        self._response = response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self._response


SAMPLE = {
    "code": 0,
    "data": {"result": [
        {
            "title": '完美世界 <em class="keyword">石昊</em> 名场面',
            "arcurl": "https://www.bilibili.com/video/BV1",
            "description": "石昊大战",
            "play": 460000, "like": 12000, "favorites": 8000,
            "video_review": 300, "danmaku": 1500,
            "pubdate": 1748000000, "author": "UP主A",
        },
        {
            "title": "完美世界 第100集",
            "arcurl": "https://www.bilibili.com/video/BV2",
            "description": "", "play": 90000, "like": 1000, "favorites": 500,
            "video_review": None, "danmaku": 200,
            "pubdate": 1748100000, "author": "UP主B",
        },
    ]},
}

REQUIRED_RESULT_KEYS = {"title", "url", "snippet", "score", "published"}


class TestBilibiliProvider(unittest.TestCase):
    def test_normalizes_and_maps_engagement(self):
        session = FakeSession(FakeResponse(200, SAMPLE))
        envelope = bilibili.search("完美世界", limit=5, platform="bilibili", session=session)

        self.assertEqual(envelope["provider"], "bilibili")
        self.assertEqual(envelope["mode"], "online")
        self.assertEqual(len(envelope["results"]), 2)

        first = envelope["results"][0]
        self.assertLessEqual(REQUIRED_RESULT_KEYS, set(first))
        # <em> tags stripped from the title
        self.assertNotIn("<em", first["title"])
        self.assertIn("石昊", first["title"])
        # structured engagement mapped: like→likes, favorites→saves,
        # video_review→comments, play→score
        self.assertEqual(first["engagement"]["likes"], 12000)
        self.assertEqual(first["engagement"]["saves"], 8000)
        self.assertEqual(first["engagement"]["comments"], 300)
        self.assertEqual(first["engagement"]["views"], 460000)
        self.assertEqual(first["score"], 460000)
        self.assertEqual(first["published"], "2025-05-23")  # from pubdate

    def test_comments_fall_back_to_danmaku(self):
        session = FakeSession(FakeResponse(200, SAMPLE))
        envelope = bilibili.search("完美世界", platform="bilibili", session=session)
        # second item has video_review=None → comments should use danmaku (200)
        self.assertEqual(envelope["results"][1]["engagement"]["comments"], 200)

    def test_limit_caps_results(self):
        session = FakeSession(FakeResponse(200, SAMPLE))
        envelope = bilibili.search("完美世界", limit=1, platform="bilibili", session=session)
        self.assertEqual(len(envelope["results"]), 1)

    def test_nonzero_code_raises(self):
        session = FakeSession(FakeResponse(200, {"code": -412, "message": "risk control"}))
        with self.assertRaises(RuntimeError):
            bilibili.search("完美世界", platform="bilibili", session=session)

    def test_published_iso_handles_bad_pubdate(self):
        self.assertEqual(bilibili._published_iso(None), "")
        self.assertEqual(bilibili._published_iso("not-a-number"), "")


class TestStrategyRegistry(unittest.TestCase):
    def test_bilibili_is_native(self):
        self.assertEqual(strategy.native_provider("bilibili"), "bilibili")

    def test_twitter_linkedin_use_searxng_native(self):
        # twitter/linkedin have no platform-specific API, so they use the key-free
        # SearXNG/DuckDuckGo provider, scoped to the platform via site: targeting.
        for platform in ("twitter", "linkedin"):
            self.assertEqual(strategy.native_provider(platform), "searxng")

    def test_targeted_query_adds_site_scope(self):
        q = strategy.build_targeted_query("校园美食", "xiaohongshu")
        self.assertIn("校园美食", q)
        self.assertIn("site:xiaohongshu.com", q)
        self.assertIn("爆款", q)  # platform query_suffix applied

    def test_targeted_query_per_platform_sites(self):
        self.assertIn("site:twitter.com", strategy.build_targeted_query("AI", "twitter"))
        self.assertIn("site:zhihu.com", strategy.build_targeted_query("考研", "zhihu"))
        self.assertIn("site:linkedin.com", strategy.build_targeted_query("career", "linkedin"))

    def test_unknown_platform_uses_default(self):
        q = strategy.build_targeted_query("topic", "unknown-platform")
        self.assertIn("topic", q)
        # default has no sites → no site: clause
        self.assertNotIn("site:", q)

    def test_can_disable_site_scoping(self):
        q = strategy.build_targeted_query("x", "xiaohongshu", use_sites=False)
        self.assertNotIn("site:", q)


if __name__ == "__main__":
    unittest.main()
