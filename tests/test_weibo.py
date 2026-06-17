#!/usr/bin/env python3
"""Tests for the Weibo native provider.

HTTP is faked with an injected session. These tests cover recursive card parsing,
HTML cleanup, structured engagement mapping, and strategy/dispatcher wiring.
"""

import os
import sys
import unittest
from unittest import mock

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import retrieve  # noqa: E402
import strategy  # noqa: E402
import weibo  # noqa: E402


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
    def __init__(self, response):
        self._response = response
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self._response


SAMPLE = {
    "ok": 1,
    "data": {
        "cards": [
            {
                "card_group": [
                    {
                        "mblog": {
                            "id": "A1",
                            "bid": "BID1",
                            "text": "<span>微博</span> 热点 &amp; 讨论",
                            "attitudes_count": 1200,
                            "comments_count": 88,
                            "reposts_count": 30,
                            "created_at": "Thu Jun 04 12:00:00 +0800 2026",
                            "user": {"screen_name": "新闻君"},
                        }
                    }
                ]
            },
            {
                "mblog": {
                    "id": "A2",
                    "text_raw": "第二条微博",
                    "scheme": "https://m.weibo.cn/status/A2",
                    "attitudes_count": 10,
                    "comments_count": 2,
                    "reposts_count": 1,
                    "created_at": "刚刚",
                    "user": {"screen_name": "用户A"},
                }
            },
        ]
    },
}


class TestWeiboProvider(unittest.TestCase):
    def test_normalizes_and_maps_engagement(self):
        session = FakeSession(FakeResponse(200, SAMPLE))
        env = weibo.search("热点", limit=5, platform="weibo", session=session)

        self.assertEqual(env["provider"], "weibo")
        self.assertEqual(env["mode"], "online")
        self.assertEqual(len(env["results"]), 2)
        first = env["results"][0]
        self.assertEqual(first["title"], "微博 热点 & 讨论")
        self.assertEqual(first["url"], "https://m.weibo.cn/detail/BID1")
        self.assertEqual(first["engagement"]["likes"], 1200)
        self.assertEqual(first["engagement"]["comments"], 88)
        self.assertEqual(first["engagement"]["shares"], 30)
        self.assertEqual(first["author"], "新闻君")
        self.assertIn("containerid", session.calls[0][1])

    def test_limit_caps_results(self):
        session = FakeSession(FakeResponse(200, SAMPLE))
        env = weibo.search("热点", limit=1, platform="weibo", session=session)
        self.assertEqual(len(env["results"]), 1)

    def test_non_ok_response_raises(self):
        session = FakeSession(FakeResponse(200, {"ok": 0, "msg": "blocked"}))
        with self.assertRaises(RuntimeError):
            weibo.search("热点", session=session)


class TestWeiboRouting(unittest.TestCase):
    def test_weibo_routes_via_cdp(self):
        # m.weibo.cn server-side search now hits Sina's anti-bot wall (HTTP 432),
        # so weibo is routed through CDP (the logged-in browser) like 小红书/知乎.
        self.assertEqual(strategy.native_provider("weibo"), "cdp")
        self.assertIn("cdp", retrieve.NATIVE_PROVIDERS)

    def test_auto_weibo_uses_cdp_with_consent(self):
        env = {"provider": "cdp:weibo", "results": [], "platform": "weibo",
               "mode": "online", "query": "热搜"}
        with mock.patch.object(retrieve.cdp_platforms, "search", return_value=env) as search:
            name, result = retrieve.dispatch("热搜", "weibo", "auto", {}, limit=3,
                                             consent=True)
        self.assertEqual(name, "cdp")
        search.assert_called_once_with("热搜", limit=3, platform="weibo", consent=True)

    def test_auto_weibo_requires_consent(self):
        # Without consent, the CDP route must raise ConsentRequired (never silent).
        from cdp_client import ConsentRequired
        with self.assertRaises(ConsentRequired):
            retrieve.dispatch("热搜", "weibo", "auto", {}, limit=3, consent=False)


if __name__ == "__main__":
    unittest.main()
