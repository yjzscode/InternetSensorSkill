#!/usr/bin/env python3
"""Tests for user-provided source link extraction."""

import os
import sys
import unittest
from unittest import mock

_RETRIEVAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retrieval"
)
if _RETRIEVAL_DIR not in sys.path:
    sys.path.insert(0, _RETRIEVAL_DIR)

import source_links  # noqa: E402


class FakeResponse:
    def __init__(self, text="", content=b"", status_code=200, content_type="text/html"):
        self.text = text
        self.content = content or text.encode("utf-8")
        self.status_code = status_code
        self.headers = {"content-type": content_type}


class TestSourceLinks(unittest.TestCase):
    def test_extract_urls_trims_punctuation_and_dedupes(self):
        text = "论文见 https://example.com/a.pdf，项目页 https://example.com/a.pdf。另见 https://x.org/path)."
        self.assertEqual(source_links.extract_urls(text), [
            "https://example.com/a.pdf",
            "https://x.org/path",
        ])

    def test_fetch_webpage_extracts_clean_text(self):
        response = FakeResponse("<html><title>T</title><body><script>x</script>Abstract This is useful.</body></html>")
        record = source_links.fetch_source("https://example.com", fetcher=lambda url: response)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["kind"], "webpage")
        self.assertIn("Abstract This is useful", record["text_excerpt"])

    def test_fetch_pdf_uses_pdf_extractor(self):
        response = FakeResponse(content=b"%PDF", content_type="application/pdf")
        with mock.patch.object(source_links, "extract_pdf_text", return_value=(
            "Jano: Adaptive Diffusion Generation\n"
            "Abstract We propose early-stage convergence awareness for diffusion generation. "
            "1 Introduction Details."
        )):
            record = source_links.fetch_source("https://example.com/paper.pdf", fetcher=lambda url: response)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["kind"], "pdf")
        self.assertIn("early-stage convergence awareness", record["key_sections"]["abstract"])

    def test_collect_sources_reports_fetch_failure(self):
        response = FakeResponse(status_code=404)
        with mock.patch.object(source_links, "fetch_source",
                               return_value={"url": "https://example.com/missing.pdf", "status": "error"}):
            data = source_links.collect_sources("see https://example.com/missing.pdf")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["sources"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
