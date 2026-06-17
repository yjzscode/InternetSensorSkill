#!/usr/bin/env python3
"""Tests for the CDP bridge and CDP-based platform providers.

No live browser or proxy: the CDPClient is faked, so these tests verify the
provider logic (URL building, JS dispatch, engagement mapping, schema) and the
strategy wiring — not the browser itself (that's the real smoke test).
"""

import os
import sys
import unittest

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import cdp_platforms  # noqa: E402
import strategy  # noqa: E402
import retrieve  # noqa: E402
from cdp_client import CDPError, ConsentRequired  # noqa: E402


class FakeCDPClient:
    """Stand-in for CDPClient: records the navigated URL, returns canned rows."""

    def __init__(self, rows, ready=True):
        self._rows = rows
        self._ready = ready
        self.navigated_url = None
        self.scrolled = 0
        self.closed = False

    def ensure_proxy(self, browser=""):
        if not self._ready:
            raise CDPError("browser not enabled")

    def new_tab(self, url="about:blank"):
        self.navigated_url = url
        return "target-1"

    def scroll(self, target_id, times=1):
        self.scrolled = times

    def eval(self, target_id, expression):
        return self._rows

    def __exit__(self, *a):
        self.closed = True
        return False


XHS_ROWS = [
    {"title": "宝藏牛肉面", "url": "https://www.xiaohongshu.com/explore/abc",
     "snippet": "", "likes": 12000, "comments": None, "saves": None, "shares": None,
     "published": ""},
    {"title": "校园美食", "url": "/explore/def", "snippet": "",
     "likes": 300, "comments": None, "saves": None, "shares": None, "published": ""},
]


class TestCDPPlatformProvider(unittest.TestCase):
    def test_xiaohongshu_search_normalizes(self):
        client = FakeCDPClient(XHS_ROWS)
        env = cdp_platforms.search("校园美食", platform="xiaohongshu", client=client,
                                   limit=5, consent=True)

        self.assertIn("xiaohongshu.com/search_result", client.navigated_url)
        self.assertIn("keyword=", client.navigated_url)
        self.assertEqual(env["provider"], "cdp:xiaohongshu")
        self.assertEqual(len(env["results"]), 2)
        first = env["results"][0]
        self.assertEqual(first["engagement"]["likes"], 12000)
        self.assertEqual(set(first) >= {"title", "url", "snippet", "score", "published", "engagement"}, True)

    def test_limit_caps_results(self):
        client = FakeCDPClient(XHS_ROWS)
        env = cdp_platforms.search("x", platform="xiaohongshu", client=client,
                                   limit=1, consent=True)
        self.assertEqual(len(env["results"]), 1)

    def test_zhihu_url_and_provider(self):
        rows = [{"title": "如何评价完美世界", "url": "https://www.zhihu.com/question/1",
                 "snippet": "", "likes": 5000, "comments": 200, "saves": None, "shares": None,
                 "published": "", "author": "国漫答主"}]
        client = FakeCDPClient(rows)
        env = cdp_platforms.search("完美世界", platform="zhihu", client=client, consent=True)
        self.assertIn("zhihu.com/search", client.navigated_url)
        self.assertEqual(env["provider"], "cdp:zhihu")
        self.assertEqual(env["results"][0]["engagement"]["comments"], 200)
        self.assertEqual(env["results"][0]["account"], "国漫答主")
        self.assertEqual(env["results"][0]["author"], "国漫答主")

    def test_weixin_uses_sogou_gateway(self):
        rows = [{"title": "完美世界深度解析", "url": "https://weixin.sogou.com/x",
                 "snippet": "解析", "account": "国漫君",
                 "likes": None, "comments": None, "saves": None, "shares": None, "published": ""}]
        client = FakeCDPClient(rows)
        env = cdp_platforms.search("完美世界", platform="weixin", client=client, consent=True)
        self.assertIn("weixin.sogou.com", client.navigated_url)
        self.assertEqual(env["results"][0]["account"], "国漫君")
        self.assertEqual(env["results"][0]["author"], "国漫君")

    def test_douban_url_score_and_volume(self):
        rows = [{"title": "电影长评", "url": "https://movie.douban.com/subject/1/",
                 "snippet": "评分 8.8 10万人评价", "score": 8.8,
                 "likes": None, "comments": 100000, "saves": None, "shares": None,
                 "views": None, "published": "2026-01-01", "author": "影评人A"}]
        client = FakeCDPClient(rows)
        env = cdp_platforms.search("影评", platform="douban", client=client, consent=True)
        self.assertIn("douban.com/search", client.navigated_url)
        self.assertEqual(env["provider"], "cdp:douban")
        self.assertEqual(env["results"][0]["score"], 8.8)
        self.assertEqual(env["results"][0]["engagement"]["comments"], 100000)
        self.assertEqual(env["results"][0]["account"], "影评人A")

    def test_hupu_url_and_forum_metrics(self):
        rows = [{"title": "理性讨论这场球", "url": "https://bbs.hupu.com/1.html",
                 "snippet": "120亮 300回复 2万浏览",
                 "likes": 120, "comments": 300, "saves": None, "shares": None,
                 "views": 20000, "published": "06-01", "account": "篮球老哥"}]
        client = FakeCDPClient(rows)
        env = cdp_platforms.search("篮球", platform="hupu", client=client, consent=True)
        self.assertIn("bbs.hupu.com/search", client.navigated_url)
        self.assertEqual(env["provider"], "cdp:hupu")
        self.assertEqual(env["results"][0]["engagement"]["likes"], 120)
        self.assertEqual(env["results"][0]["engagement"]["views"], 20000)
        self.assertEqual(env["results"][0]["author"], "篮球老哥")

    def test_aliases_resolve(self):
        self.assertEqual(cdp_platforms.resolve_platform("xhs"), "xiaohongshu")
        self.assertEqual(cdp_platforms.resolve_platform("wechat"), "weixin")
        self.assertEqual(cdp_platforms.resolve_platform("公众号"), "weixin")
        self.assertEqual(cdp_platforms.resolve_platform("豆瓣"), "douban")
        self.assertEqual(cdp_platforms.resolve_platform("虎扑"), "hupu")

    def test_unknown_platform_raises(self):
        client = FakeCDPClient([])
        with self.assertRaises(CDPError):
            cdp_platforms.search("x", platform="myspace", client=client, consent=True)

    def test_proxy_unavailable_raises(self):
        client = FakeCDPClient([], ready=False)
        with self.assertRaises(CDPError):
            cdp_platforms.search("x", platform="xiaohongshu", client=client, consent=True)

    def test_consent_required_without_consent(self):
        # The whole point of the gate: no consent → raise BEFORE touching the browser.
        client = FakeCDPClient(XHS_ROWS)
        with self.assertRaises(ConsentRequired):
            cdp_platforms.search("校园美食", platform="xiaohongshu", client=client)
        # The browser must not have been navigated.
        self.assertIsNone(client.navigated_url)

    def test_consent_checked_before_platform_for_known_platform(self):
        # A known CDP platform without consent raises ConsentRequired (not CDPError).
        client = FakeCDPClient(XHS_ROWS)
        with self.assertRaises(ConsentRequired):
            cdp_platforms.search("x", platform="zhihu", client=client)

    def test_login_wall_surfaces_signal(self):
        # Extractor reports {login_required: True, items: []} → envelope flags it.
        client = FakeCDPClient({"login_required": True, "items": []})
        env = cdp_platforms.search("校园美食", platform="xiaohongshu", client=client, consent=True)
        self.assertTrue(env.get("login_required"))
        self.assertIn("logged in", env.get("reason", ""))
        self.assertEqual(env["results"], [])

    def test_dict_return_shape_with_items(self):
        client = FakeCDPClient({"login_required": False, "items": XHS_ROWS})
        env = cdp_platforms.search("校园美食", platform="xiaohongshu", client=client, consent=True)
        self.assertNotIn("login_required", env)
        self.assertEqual(len(env["results"]), 2)


class TestStrategyCDPWiring(unittest.TestCase):
    def test_cdp_platforms_have_native_cdp(self):
        for p in ("xiaohongshu", "zhihu", "weixin", "douban", "hupu"):
            self.assertEqual(strategy.native_provider(p), "cdp")

    def test_bilibili_still_native_bilibili(self):
        self.assertEqual(strategy.native_provider("bilibili"), "bilibili")

    def test_cdp_registered_in_dispatcher(self):
        self.assertIn("cdp", retrieve.NATIVE_PROVIDERS)
        self.assertIs(retrieve.NATIVE_PROVIDERS["cdp"], cdp_platforms)


class TestDispatchCDP(unittest.TestCase):
    def test_auto_routes_xiaohongshu_to_cdp_with_consent(self):
        from unittest import mock
        env = {"provider": "cdp:xiaohongshu", "results": [], "platform": "xiaohongshu",
               "mode": "online", "query": "校园美食"}
        with mock.patch.object(cdp_platforms, "search", return_value=env) as cdp_search:
            name, result = retrieve.dispatch("校园美食", "xiaohongshu", "auto", {},
                                             limit=5, consent=True)
        self.assertEqual(name, "cdp")
        cdp_search.assert_called_once()
        # platform + consent must be forwarded so cdp_platforms can run
        self.assertEqual(cdp_search.call_args.kwargs.get("platform"), "xiaohongshu")
        self.assertTrue(cdp_search.call_args.kwargs.get("consent"))

    def test_auto_without_consent_propagates_consent_required(self):
        from unittest import mock
        # Real cdp_platforms.search (no mock) raises ConsentRequired before any
        # browser call; dispatch must let it propagate, NOT fall through to keyed.
        with mock.patch.dict(os.environ, {"TREND_TAVILY_API_KEY": "k"}, clear=True), \
             mock.patch.object(retrieve.tavily, "search") as tav:
            with self.assertRaises(ConsentRequired):
                retrieve.dispatch("校园美食", "xiaohongshu", "auto",
                                  {"tavily_api_key": "k"}, limit=5, consent=False)
        tav.assert_not_called()  # must not silently fall through to keyed search

    def test_auto_falls_through_to_keyed_when_cdp_unavailable(self):
        from unittest import mock
        keyed_env = {"provider": "tavily", "results": [], "platform": "xiaohongshu",
                     "mode": "online", "query": "q"}
        with mock.patch.dict(os.environ, {"TREND_TAVILY_API_KEY": "k"}, clear=True), \
             mock.patch.object(cdp_platforms, "search", side_effect=CDPError("no browser")), \
             mock.patch.object(retrieve.tavily, "search", return_value=keyed_env) as tav:
            name, result = retrieve.dispatch("校园美食", "xiaohongshu", "auto",
                                             {"tavily_api_key": "k"}, limit=5, consent=True)
        # CDP failed (not a consent issue) → fell through to keyed site:-targeted tavily
        self.assertEqual(name, "tavily")
        self.assertIn("site:xiaohongshu.com", tav.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
