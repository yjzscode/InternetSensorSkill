#!/usr/bin/env python3
"""Tests for the knowledge library: every platform/topic YAML loads and has the
required keys, so the V1 offline pipeline always has well-formed rules to read.
"""

import os
import sys
import unittest

import yaml

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import strategy  # noqa: E402


KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge"
)
PLATFORMS_DIR = os.path.join(KNOWLEDGE_DIR, "platforms")
TOPICS_DIR = os.path.join(KNOWLEDGE_DIR, "topics")
MYACCOUNT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "myaccount"
)

PLATFORM_REQUIRED_KEYS = {
    "platform", "display_name", "language", "title_patterns",
    "emotion_levers", "structure", "formatting", "ai_smell_signals",
    "dos", "donts",
}
TOPIC_REQUIRED_KEYS = {
    "topic", "display_name", "aliases", "audience_intent",
    "typical_hooks", "saveability_cues", "credibility_cues", "ai_smell_signals",
}


def _yaml_files(directory):
    return [
        os.path.join(directory, name)
        for name in sorted(os.listdir(directory))
        if name.endswith(".yaml") or name.endswith(".yml")
    ]


class TestPlatformKnowledge(unittest.TestCase):
    def test_platform_files_exist(self):
        files = _yaml_files(PLATFORMS_DIR)
        self.assertTrue(files, "no platform YAML files found")
        # Core V1 platforms must be present.
        names = {os.path.splitext(os.path.basename(f))[0] for f in files}
        self.assertLessEqual(
            {"bilibili", "xiaohongshu", "zhihu", "weixin", "weibo",
             "douban", "hupu", "twitter", "linkedin"},
            names,
        )

    def test_platform_files_load_and_have_required_keys(self):
        for path in _yaml_files(PLATFORMS_DIR):
            with self.subTest(path=os.path.basename(path)):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self.assertIsInstance(data, dict)
                missing = PLATFORM_REQUIRED_KEYS - set(data)
                self.assertFalse(missing, f"missing keys: {missing}")
                # list-typed fields should be non-empty lists
                for key in ("title_patterns", "emotion_levers", "structure",
                            "ai_smell_signals", "dos", "donts"):
                    self.assertIsInstance(data[key], list)
                    self.assertTrue(data[key], f"{key} is empty")

    def test_platform_filename_matches_field(self):
        for path in _yaml_files(PLATFORMS_DIR):
            with self.subTest(path=os.path.basename(path)):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                stem = os.path.splitext(os.path.basename(path))[0]
                self.assertEqual(data["platform"], stem)

    def test_registered_platforms_have_v1_knowledge(self):
        files = _yaml_files(PLATFORMS_DIR)
        names = {os.path.splitext(os.path.basename(f))[0] for f in files}
        self.assertLessEqual(set(strategy.STRATEGIES), names)


class TestTopicKnowledge(unittest.TestCase):
    def test_topic_files_exist(self):
        files = _yaml_files(TOPICS_DIR)
        self.assertTrue(files, "no topic YAML files found")
        names = {os.path.splitext(os.path.basename(f))[0] for f in files}
        self.assertLessEqual(
            {"food", "travel", "study", "ai", "anime", "sports",
             "film", "digital", "social"},
            names,
        )

    def test_topic_files_load_and_have_required_keys(self):
        for path in _yaml_files(TOPICS_DIR):
            with self.subTest(path=os.path.basename(path)):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self.assertIsInstance(data, dict)
                missing = TOPIC_REQUIRED_KEYS - set(data)
                self.assertFalse(missing, f"missing keys: {missing}")
                self.assertIsInstance(data["aliases"], list)
                self.assertTrue(data["aliases"])

    def test_food_topic_covers_beef_noodles(self):
        # The canonical example relies on 'food' matching 牛肉面 / 校园美食.
        with open(os.path.join(TOPICS_DIR, "food.yaml"), "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        aliases = " ".join(data["aliases"])
        self.assertIn("校园美食", aliases)


class TestAccountKnowledge(unittest.TestCase):
    def test_account_subdirs_have_required_files(self):
        if not os.path.isdir(MYACCOUNT_DIR):
            self.skipTest("myaccount directory not present")
        required = {"account_positioning.md", "reference_accounts.md", "para_config.yaml"}
        account_dirs = []
        for name in sorted(os.listdir(MYACCOUNT_DIR)):
            path = os.path.join(MYACCOUNT_DIR, name)
            if os.path.isdir(path):
                account_dirs.append(path)
        if not account_dirs:
            return
        for path in account_dirs:
            with self.subTest(account_id=os.path.basename(path)):
                names = set(os.listdir(path))
                self.assertLessEqual(required, names)


if __name__ == "__main__":
    unittest.main()
