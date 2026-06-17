"""Trend retrieval layer (V2) for Trend-Aware Content Improver.

This package holds the only real code in the project: thin clients that hit
search/crawl providers and normalize their responses into one schema. Reasoning
lives in `prompts/`; this layer is just the network boundary, invoked as a CLI
(`python3 retrieval/retrieve.py ...`) so any agent runtime (Claude Code today,
openclaw later) can shell out to it identically.

本包是项目中唯一的实际代码：调用检索/爬取服务并把结果归一化为统一 schema。
推理逻辑在 prompts/ 中，本层只负责联网，作为独立 CLI 被调用。
"""
