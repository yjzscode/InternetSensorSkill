#!/usr/bin/env python3
"""Tests for engagement extraction and traction-based vibe scoring.

Covers count parsing (1.2万 / 12k / 1,234), the Xiaohongshu extractor, relative
and absolute date parsing, the vibe_score formula, and ranking. No network — the
one fetch test injects a fake fetcher.
"""

import os
import sys
import unittest
from datetime import datetime

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import engagement  # noqa: E402


class TestParseCount(unittest.TestCase):
    def test_plain_and_separated(self):
        self.assertEqual(engagement.parse_count("1234"), 1234)
        self.assertEqual(engagement.parse_count("1,234"), 1234)

    def test_chinese_and_shorthand_units(self):
        self.assertEqual(engagement.parse_count("1.2万"), 12000)
        self.assertEqual(engagement.parse_count("3.4w"), 34000)
        self.assertEqual(engagement.parse_count("12k"), 12000)
        self.assertEqual(engagement.parse_count("1万+"), 10000)

    def test_no_number(self):
        self.assertIsNone(engagement.parse_count("赞"))
        self.assertIsNone(engagement.parse_count(None))


class TestXiaohongshuExtractor(unittest.TestCase):
    def test_extracts_all_four_metrics(self):
        text = "点赞 1.2万  收藏 3.5万  评论 800  分享 1200"
        metrics = engagement.extract_xiaohongshu(text)
        self.assertEqual(metrics["likes"], 12000)
        self.assertEqual(metrics["saves"], 35000)
        self.assertEqual(metrics["comments"], 800)
        self.assertEqual(metrics["shares"], 1200)

    def test_number_before_keyword(self):
        metrics = engagement.extract_xiaohongshu("1.2万赞 3456收藏")
        self.assertEqual(metrics["likes"], 12000)
        self.assertEqual(metrics["saves"], 3456)

    def test_missing_metric_is_none(self):
        metrics = engagement.extract_xiaohongshu("点赞 100")
        self.assertEqual(metrics["likes"], 100)
        self.assertIsNone(metrics["shares"])

    def test_dispatch_uses_registered_extractor(self):
        metrics = engagement.extract_engagement("收藏 999", platform="xiaohongshu")
        self.assertEqual(metrics["saves"], 999)

    def test_dispatch_falls_back_to_generic(self):
        # Unknown platform → generic extractor still finds keyword-adjacent counts.
        metrics = engagement.extract_engagement("likes 500 comments 20", platform="unknown")
        self.assertEqual(metrics["likes"], 500)
        self.assertEqual(metrics["comments"], 20)


class TestPublishedDays(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 4)

    def test_relative_chinese(self):
        self.assertEqual(engagement.parse_published_days("3天前", now=self.now), 3)
        self.assertEqual(engagement.parse_published_days("昨天", now=self.now), 1)
        self.assertEqual(engagement.parse_published_days("2周前", now=self.now), 14)
        self.assertEqual(engagement.parse_published_days("刚刚", now=self.now), 0)

    def test_absolute_date(self):
        self.assertEqual(engagement.parse_published_days("2026-05-25", now=self.now), 10)

    def test_chinese_absolute_date(self):
        self.assertEqual(engagement.parse_published_days("2026年6月1日", now=self.now), 3)
        self.assertEqual(engagement.parse_published_days("6月1日", now=self.now), 3)

    def test_weibo_style_date(self):
        self.assertEqual(
            engagement.parse_published_days("Thu Jun 04 12:00:00 +0800 2026", now=self.now),
            0,
        )

    def test_unparseable(self):
        self.assertIsNone(engagement.parse_published_days("no date here", now=self.now))


class TestVibeScore(unittest.TestCase):
    def test_more_engagement_scores_higher(self):
        low = engagement.compute_vibe_score({"likes": 100}, published_days=10)
        high = engagement.compute_vibe_score({"likes": 100000}, published_days=10)
        self.assertIsNotNone(low)
        self.assertIsNotNone(high)
        self.assertGreater(high, low)

    def test_newer_post_scores_higher_for_same_engagement(self):
        old = engagement.compute_vibe_score({"saves": 10000}, published_days=100)
        new = engagement.compute_vibe_score({"saves": 10000}, published_days=2)
        self.assertGreater(new, old)

    def test_saves_weighted_more_than_likes(self):
        likes = engagement.compute_vibe_score({"likes": 1000}, published_days=5)
        saves = engagement.compute_vibe_score({"saves": 1000}, published_days=5)
        self.assertGreater(saves, likes)

    def test_score_uses_configured_weights(self):
        config = engagement._common.DEFAULT_PARA_CONFIG.copy()
        config = {
            **engagement._common.DEFAULT_PARA_CONFIG,
            "real_vibe_score": {
                **engagement._common.DEFAULT_PARA_CONFIG["real_vibe_score"],
                "engagement_weights": {
                    "likes": 1.0,
                    "saves": 0.1,
                },
            },
        }
        with unittest.mock.patch.object(engagement._common, "load_para_config", return_value=config):
            likes = engagement.compute_vibe_score({"likes": 1000}, published_days=5)
            saves = engagement.compute_vibe_score({"saves": 1000}, published_days=5)
        self.assertGreater(likes, saves)

    def test_views_are_weak_but_counted(self):
        views = engagement.compute_vibe_score({"views": 100000}, published_days=10)
        likes = engagement.compute_vibe_score({"likes": 100000}, published_days=10)
        self.assertIsNotNone(views)
        self.assertLess(views, likes)

    def test_zero_engagement_is_none(self):
        self.assertIsNone(engagement.compute_vibe_score({}, published_days=5))
        self.assertIsNone(engagement.compute_vibe_score({"likes": 0}, published_days=5))

    def test_score_bounded_0_100(self):
        score = engagement.compute_vibe_score({"shares": 10_000_000}, published_days=1)
        self.assertLessEqual(score, 100.0)
        self.assertGreaterEqual(score, 0.0)


class TestEnrichAndRank(unittest.TestCase):
    def test_enrich_attaches_fields(self):
        result = {"title": "宝藏牛肉面", "snippet": "点赞 1万 收藏 2万", "url": "", "published": "3天前"}
        engagement.enrich_result(result, platform="xiaohongshu", now=datetime(2026, 6, 4))
        self.assertEqual(result["engagement"]["likes"], 10000)
        self.assertEqual(result["published_days"], 3)
        self.assertIsNotNone(result["vibe_score"])

    def test_rank_orders_by_vibe_score_desc_with_none_last(self):
        results = [
            {"vibe_score": 10.0},
            {"vibe_score": None},
            {"vibe_score": 80.0},
        ]
        ranked = engagement.rank_results(results)
        self.assertEqual([r["vibe_score"] for r in ranked], [80.0, 10.0, None])

    def test_rank_top_n_and_min_vibe(self):
        results = [{"vibe_score": s} for s in (90.0, 50.0, 20.0, None)]
        top2 = engagement.rank_results(results, top_n=2)
        self.assertEqual([r["vibe_score"] for r in top2], [90.0, 50.0])
        filtered = engagement.rank_results(results, min_vibe=40.0)
        self.assertEqual([r["vibe_score"] for r in filtered], [90.0, 50.0])


class TestFetchPageText(unittest.TestCase):
    def test_strips_html(self):
        html = "<html><body><h1>赞 100</h1><script>x()</script></body></html>"
        text = engagement.fetch_page_text("http://x", fetcher=lambda u: type("R", (), {"text": html})())
        self.assertIn("赞 100", text)
        self.assertNotIn("<h1>", text)
        self.assertNotIn("x()", text)

    def test_network_error_returns_empty(self):
        def boom(url):
            raise RuntimeError("network down")

        self.assertEqual(engagement.fetch_page_text("http://x", fetcher=boom), "")


if __name__ == "__main__":
    unittest.main()
