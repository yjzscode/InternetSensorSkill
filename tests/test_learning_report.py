#!/usr/bin/env python3
"""Tests for retrieval/learning_report.py."""

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
import learning_report  # noqa: E402


def _write_accounts(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "| platform | account_name | homepage_url | learn_what | notes |\n"
            "|---|---|---|---|---|\n"
            "| bilibili | 影视飓风 | https://space.bilibili.com/946974 | video structure | |\n"
        )


class TestLearningReport(unittest.TestCase):
    def test_collect_report_keeps_account_matched_items(self):
        envelope = _common.make_envelope("影视飓风", "bilibili", "bilibili", [
            {
                "title": "影视飓风的新视频",
                "url": "https://www.bilibili.com/video/BV1",
                "snippet": "",
                "score": None,
                "published": "2026-06-01",
                "author": "影视飓风",
                "engagement": {"likes": 10000, "comments": 300, "saves": 800, "shares": 100},
            },
            {
                "title": "普通搬运",
                "url": "https://www.bilibili.com/video/BV2",
                "snippet": "",
                "score": None,
                "published": "2026-06-01",
                "author": "别的账号",
                "engagement": {"likes": 99999, "comments": 0, "saves": 0, "shares": 0},
            },
        ])
        config = _common.load_para_config("")
        config["learning_report"]["crawl"] = False

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(learning_report.retrieve, "dispatch", return_value=("bilibili", envelope)), \
             mock.patch.object(learning_report._common, "load_config", return_value={}):
            accounts_path = os.path.join(tmp, "reference_accounts.md")
            _write_accounts(accounts_path)
            report = learning_report.collect_report(
                "bilibili", accounts_path, config, "auto", limit=5, items_n=2, consent=False
            )

        self.assertEqual(report["accounts_count"], 1)
        self.assertEqual(report["collected_items_count"], 1)
        item = report["accounts"][0]["items"][0]
        self.assertEqual(item["author"], "影视飓风")
        self.assertEqual(item["match_confidence"], "identity_match")
        self.assertIsNotNone(item["vibe_score"])

    def test_main_writes_learning_raw_json(self):
        envelope = _common.make_envelope("影视飓风", "bilibili", "bilibili", [
            {
                "title": "影视飓风的新视频",
                "url": "https://www.bilibili.com/video/BV1",
                "snippet": "",
                "score": None,
                "published": "2026-06-01",
                "author": "影视飓风",
                "engagement": {"likes": 1000, "comments": 10, "saves": 20, "shares": 5},
            },
        ])

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(learning_report.retrieve, "dispatch", return_value=("bilibili", envelope)), \
             mock.patch.object(learning_report._common, "load_config", return_value={}):
            accounts_path = os.path.join(tmp, "reference_accounts.md")
            _write_accounts(accounts_path)
            para = os.path.join(tmp, "para_config.yaml")
            with open(para, "w", encoding="utf-8") as f:
                f.write("learning_report:\n  crawl: false\n  items_per_account: 1\n  limit_per_account: 3\n")
            out_dir = os.path.join(tmp, "out")
            rc = learning_report.main([
                "--para-config", para,
                "--platform", "bilibili",
                "--reference-accounts", accounts_path,
                "--output-dir", out_dir,
            ])
            self.assertEqual(rc, 0)
            raw_path = os.path.join(out_dir, "learning_raw.json")
            with open(raw_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        self.assertEqual(data["platform"], "bilibili")
        self.assertEqual(data["collected_items_count"], 1)
        self.assertEqual(data["accounts"][0]["items"][0]["source_account"], "影视飓风")

    def test_account_reference_examples_purpose_writes_flat_examples(self):
        envelope = _common.make_envelope("影视飓风", "bilibili", "bilibili", [
            {
                "title": "风格样本",
                "url": "https://www.bilibili.com/video/BV3",
                "snippet": "真实口吻",
                "score": None,
                "published": "2026-06-01",
                "author": "影视飓风",
                "engagement": {"likes": 1000, "comments": 10, "saves": 20, "shares": 5},
            },
        ])

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(learning_report.retrieve, "dispatch", return_value=("bilibili", envelope)), \
             mock.patch.object(learning_report._common, "load_config", return_value={}):
            accounts_path = os.path.join(tmp, "reference_accounts.md")
            _write_accounts(accounts_path)
            para = os.path.join(tmp, "para_config.yaml")
            with open(para, "w", encoding="utf-8") as f:
                f.write(
                    "account_reference_samples:\n"
                    "  crawl: false\n"
                    "  items_per_account: 1\n"
                    "  limit_per_account: 3\n"
                )
            out_dir = os.path.join(tmp, "out")
            rc = learning_report.main([
                "--para-config", para,
                "--platform", "bilibili",
                "--reference-accounts", accounts_path,
                "--output-dir", out_dir,
                "--purpose", "account_reference_examples",
            ])
            self.assertEqual(rc, 0)
            raw_path = os.path.join(out_dir, "account_reference_examples.json")
            with open(raw_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        self.assertEqual(data["source_type"], "account_reference")
        self.assertEqual(data["reference_role"], "account_style")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["examples"][0]["source_type"], "account_reference")
        self.assertEqual(data["examples"][0]["reference_role"], "account_style")
        self.assertEqual(data["examples"][0]["source_account"], "影视飓风")


if __name__ == "__main__":
    unittest.main()
