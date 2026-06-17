#!/usr/bin/env python3
"""Tests for the retrieval providers (tavily / exa / firecrawl) and shared helpers.

Covers what CONTRIBUTING requires of a new data-source collector:
- auth modes (key present / absent)
- rate-limit / retry behavior (mocked HTTP 429)
- output-format consistency with the normalized schema

All HTTP is mocked — no live API calls.
"""

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
import tavily  # noqa: E402
import exa  # noqa: E402
import firecrawl  # noqa: E402


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


REQUIRED_RESULT_KEYS = {"title", "url", "snippet", "score", "published"}
REQUIRED_ENVELOPE_KEYS = {"query", "platform", "provider", "mode", "results"}


class TestResultSchema(unittest.TestCase):
    def test_make_result_and_envelope_shape(self):
        result = _common.make_result(title="t", url="u", snippet="s", score=0.5, published="2026-01-01")
        self.assertEqual(set(result), REQUIRED_RESULT_KEYS)
        envelope = _common.make_envelope("q", "xiaohongshu", "tavily", [result])
        self.assertLessEqual(REQUIRED_ENVELOPE_KEYS, set(envelope))
        self.assertEqual(envelope["mode"], "online")

    def test_offline_envelope(self):
        envelope = _common.offline_envelope("q", "xiaohongshu", "no key")
        self.assertEqual(envelope["mode"], "offline")
        self.assertEqual(envelope["results"], [])
        self.assertIsNone(envelope["provider"])

    def test_infers_linkedin_pulse_author_from_url(self):
        url = "https://www.linkedin.com/pulse/i-built-ai-agent-viral-linkedin-posts-syed-hussain-ixlff"
        self.assertEqual(_common.infer_account_from_url(url, "linkedin"), "Syed Hussain")

    def test_fill_identity_mirrors_author_and_account(self):
        result = {"title": "t", "url": "https://x.com/example/status/1", "snippet": ""}
        _common.fill_identity(result, "twitter")
        self.assertEqual(result["account"], "@example")
        self.assertEqual(result["author"], "@example")


class TestRetryBackoff(unittest.TestCase):
    def test_retries_on_429_then_succeeds(self):
        responses = [FakeResponse(429, headers={}), FakeResponse(429), FakeResponse(200, {"ok": 1})]
        calls = {"n": 0}

        def do_request():
            r = responses[calls["n"]]
            calls["n"] += 1
            return r

        slept = []
        result = _common.request_with_retry(do_request, sleep=slept.append)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(len(slept), 2)  # slept before each retry

    def test_gives_up_after_max_retries(self):
        def do_request():
            return FakeResponse(429)

        slept = []
        result = _common.request_with_retry(do_request, max_retries=3, sleep=slept.append)
        self.assertEqual(result.status_code, 429)
        self.assertEqual(len(slept), 2)  # 3 attempts → 2 sleeps

    def test_honors_retry_after_header(self):
        responses = [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, {})]
        calls = {"n": 0}

        def do_request():
            r = responses[calls["n"]]
            calls["n"] += 1
            return r

        slept = []
        _common.request_with_retry(do_request, sleep=slept.append)
        self.assertEqual(slept, [7.0])


class TestApiKeyResolution(unittest.TestCase):
    def test_env_var_wins_over_config(self):
        with mock.patch.dict(os.environ, {"TREND_TAVILY_API_KEY": "from-env"}, clear=False):
            key = _common.get_api_key("tavily", {"tavily_api_key": "from-config"})
            self.assertEqual(key, "from-env")

    def test_falls_back_to_config(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            key = _common.get_api_key("exa", {"exa_api_key": "cfg"})
            self.assertEqual(key, "cfg")

    def test_none_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(_common.get_api_key("firecrawl", {}))

    def test_configured_providers_order(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            config = {"exa_api_key": "x", "firecrawl_api_key": "y"}
            self.assertEqual(_common.configured_providers(config), ["exa", "firecrawl"])


class TestParaConfig(unittest.TestCase):
    def test_load_para_config_deep_merges_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "para_config.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write("retrieval:\n  limit: 7\nreal_vibe_score:\n  baseline_per_day: 1000\n")
            config = _common.load_para_config(path)
        self.assertEqual(config["retrieval"]["limit"], 7)
        self.assertEqual(config["retrieval"]["top"], 8)  # default preserved
        self.assertEqual(config["real_vibe_score"]["baseline_per_day"], 1000)
        self.assertIn("likes", config["real_vibe_score"]["engagement_weights"])
        self.assertIn("account_consistency", config)
        self.assertIn("risk_audit", config)
        self.assertEqual(config["output"]["files"]["account_consistency"], "account_consistency.json")

    def test_load_para_config_from_account_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            account_dir = os.path.join(tmp, "xiaohongshu_main")
            os.makedirs(account_dir)
            with open(os.path.join(account_dir, "para_config.yaml"), "w", encoding="utf-8") as f:
                f.write("retrieval:\n  limit: 11\n")
            config = _common.load_para_config(account_dir=account_dir)
        self.assertEqual(config["retrieval"]["limit"], 11)
        self.assertEqual(config["retrieval"]["top"], 8)

    def test_missing_account_dir_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = _common.load_para_config(account_dir=os.path.join(tmp, "not-set"))
        self.assertEqual(config["retrieval"]["provider"], "auto")
        self.assertIn("output", config)
        self.assertIn("account_consistency", config)


class TestTavily(unittest.TestCase):
    def test_search_normalizes_results(self):
        payload = {"results": [
            {"title": "T1", "url": "http://a", "content": "snip", "score": 0.9, "published_date": "2026-01-01"},
        ]}
        with mock.patch.object(tavily.requests, "post", return_value=FakeResponse(200, payload)) as post:
            envelope = tavily.search("q", "key", limit=5, platform="xiaohongshu")
        post.assert_called_once()
        self.assertEqual(envelope["provider"], "tavily")
        self.assertEqual(len(envelope["results"]), 1)
        self.assertEqual(set(envelope["results"][0]), REQUIRED_RESULT_KEYS)
        self.assertEqual(envelope["results"][0]["snippet"], "snip")

    def test_main_returns_2_without_key(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(_common, "load_config", return_value={}):
            rc = tavily.main(["--query", "q"])
        self.assertEqual(rc, 2)


class TestExa(unittest.TestCase):
    def test_search_uses_api_key_header_and_normalizes(self):
        payload = {"results": [
            {"title": "E1", "url": "http://b", "text": "body", "score": 0.7, "publishedDate": "2026-02-02"},
        ]}
        with mock.patch.object(exa.requests, "post", return_value=FakeResponse(200, payload)) as post:
            envelope = exa.search("q", "secret", limit=3, platform="twitter")
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"]["x-api-key"], "secret")
        self.assertEqual(envelope["results"][0]["snippet"], "body")
        self.assertEqual(set(envelope["results"][0]), REQUIRED_RESULT_KEYS)


class TestFirecrawl(unittest.TestCase):
    def test_search_uses_bearer_and_metadata_fallback(self):
        payload = {"data": [
            {"metadata": {"title": "F1", "sourceURL": "http://c", "description": "desc"}},
        ]}
        with mock.patch.object(firecrawl.requests, "post", return_value=FakeResponse(200, payload)) as post:
            envelope = firecrawl.search("q", "tok", limit=2, platform="linkedin")
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(envelope["results"][0]["title"], "F1")
        self.assertEqual(envelope["results"][0]["url"], "http://c")
        self.assertEqual(set(envelope["results"][0]), REQUIRED_RESULT_KEYS)


if __name__ == "__main__":
    unittest.main()
