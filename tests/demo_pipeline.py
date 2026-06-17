#!/usr/bin/env python3
"""Interactive end-to-end demo for the Trend-Aware Content Improver.

Walks one note (title + text + image) through the pipeline and prints
each stage's result. Division of labor mirrors the real skill:

- Deterministic stages run here as code:
    [0] image check       — validate the image (PNG header, dimensions)
    [1] topic pre-detect  — alias scan to choose which knowledge files to load
    [2] trend retrieval   — call retrieval/retrieve.py (online if a key is set,
                            else offline → V1), traction-ranked
    +   knowledge loading — read the platform + topic YAML
- Reasoning stages are performed by Claude executing the prompts under prompts/:
    [3] pattern extraction  ← prompts/extract_patterns.md
    [4] vibe critique       ← prompts/critique_content.md
    [5] rewrite             ← prompts/improve_content.md
    [6] account consistency ← prompts/account_consistency.md
    [7] risk audit          ← prompts/final_risk_audit.md
    [8] present             ← before/after vibe index + risks

This script collects the input, runs [0]-[2] + knowledge loading, writes a bundle
to outputs/demo_bundle.json, and prints the exact instruction to hand to Claude
Code so it can finish [3]-[8].

用法 / Usage:
    python3 tests/demo_pipeline.py                      # interactive prompts
    python3 tests/demo_pipeline.py --preset perfect-world   # bundled sample note
"""

import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
RETRIEVE_CLI = PROJECT_ROOT / "retrieval" / "retrieve.py"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
ACCOUNT_DIR = PROJECT_ROOT / "myaccount" / "platform_id"

# A deliberately flat, low-vibe note so the improvement is visible.
# platform=bilibili → real key-free trend retrieval (完美世界 lives on B站).
PRESETS = {
    "perfect-world": {
        "platform": "bilibili",
        "title": "完美世界动漫真的好看，推荐大家去看",
        "text": (
            "完美世界这部动漫挺好看的，画面不错，打斗也精彩，石昊很厉害。"
            "推荐给喜欢国漫的朋友，可以去看一下。"
        ),
        "image": str(PROJECT_ROOT / "tests" / "test1.png"),
    },
}

DIVIDER = "=" * 64


def check_image(path: str) -> dict:
    """Validate an image path. For PNG, read width/height from the IHDR chunk.

    Stdlib only — no Pillow dependency. Returns a small report dict; never raises
    on a bad image, so the demo keeps running and surfaces the problem instead.
    """
    report = {"path": path, "exists": False, "format": None, "width": None,
              "height": None, "bytes": None, "note": ""}
    p = Path(path)
    if not p.exists():
        report["note"] = "image not found"
        return report
    report["exists"] = True
    report["bytes"] = p.stat().st_size

    with open(p, "rb") as f:
        header = f.read(24)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        report["format"] = "PNG"
        # IHDR width/height are big-endian uint32 at byte offsets 16 and 20.
        if len(header) >= 24:
            report["width"], report["height"] = struct.unpack(">II", header[16:24])
    elif header.startswith(b"\xff\xd8"):
        report["format"] = "JPEG"
    else:
        report["format"] = "unknown"
        report["note"] = "not a PNG/JPEG; the skill reads it via the Read tool anyway"
    return report


def list_topic_aliases() -> dict:
    """Return {topic_slug: [aliases...]} for every topic YAML."""
    mapping = {}
    topics_dir = KNOWLEDGE_DIR / "topics"
    for path in sorted(topics_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mapping[data["topic"]] = data.get("aliases", [])
    return mapping


def pre_detect_topic(title: str, text: str) -> dict:
    """Alias-scan the note to pick which topic file to load. Claude finalizes it.

    This is only a deterministic *file selector* — the real topic decision (incl.
    the `general` + custom-label fallback) is made by prompts/detect_topic.md.
    """
    haystack = f"{title} {text}".lower()
    aliases = list_topic_aliases()
    for topic, alias_list in aliases.items():
        matched = [a for a in alias_list if a.lower() in haystack]
        if matched:
            return {"topic": topic, "matched": matched, "via": "alias"}
    return {"topic": "general", "matched": [], "via": "fallback"}


def run_retrieval(topic_display: str, platform: str, output_path: Path) -> dict:
    """Invoke the retrieval CLI exactly as the skill would. Always returns a dict.

    Online if a provider key is configured, otherwise a graceful offline envelope
    that signals V1 fallback. Failures degrade to an offline-shaped dict.
    """
    examples_path = output_path.with_name("reference_examples.json")
    cmd = [
        sys.executable, str(RETRIEVE_CLI),
        "--account-dir", str(ACCOUNT_DIR),
        "--topic", topic_display,
        "--platform", platform,
        "--output", str(output_path),
        "--save-examples", str(examples_path),
    ]
    print(f"  $ {' '.join(cmd[1:])}")
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False,
                   capture_output=True, text=True)
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    return {"mode": "offline", "results": [], "reason": "retrieval produced no file"}


def load_knowledge(platform: str, topic: str) -> dict:
    """Load the platform YAML and (if not general) the topic YAML."""
    knowledge = {"platform_file": None, "topic_file": None,
                 "platform": None, "topic": None}
    platform_path = KNOWLEDGE_DIR / "platforms" / f"{platform}.yaml"
    if platform_path.exists():
        knowledge["platform_file"] = str(platform_path.relative_to(PROJECT_ROOT))
        knowledge["platform"] = yaml.safe_load(platform_path.read_text(encoding="utf-8"))
    topic_path = KNOWLEDGE_DIR / "topics" / f"{topic}.yaml"
    if topic != "general" and topic_path.exists():
        knowledge["topic_file"] = str(topic_path.relative_to(PROJECT_ROOT))
        knowledge["topic"] = yaml.safe_load(topic_path.read_text(encoding="utf-8"))
    return knowledge


def prompt_input(preset: str) -> dict:
    """Return the note dict, from a preset or interactive prompts."""
    if preset:
        if preset not in PRESETS:
            sys.exit(f"unknown preset '{preset}'. options: {', '.join(PRESETS)}")
        note = dict(PRESETS[preset])
        print(f"[preset: {preset}]")
        for key in ("platform", "title", "text", "image"):
            print(f"  {key}: {note[key]}")
        return note

    print("请依次输入这条笔记的内容（直接回车用默认值）：")
    platform = input("  平台 platform [xiaohongshu]: ").strip() or "xiaohongshu"
    title = input("  标题 title: ").strip()
    text = input("  正文 text: ").strip()
    image = input("  图片路径 image path: ").strip()
    return {"platform": platform, "title": title, "text": text, "image": image}


def section(num, name_zh, name_en):
    print(f"\n{DIVIDER}\n环节 {num} · {name_zh} / {name_en}\n{DIVIDER}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="End-to-end demo driver")
    parser.add_argument("--preset", default="", help=f"use a bundled note: {', '.join(PRESETS)}")
    parser.add_argument("--output-dir", default=str(OUTPUTS_DIR), help="where to write artifacts")
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    note = prompt_input(args.preset)
    platform = note["platform"]

    section(0, "图片检查", "Image check")
    image_check = check_image(note["image"])
    for k, v in image_check.items():
        print(f"  {k}: {v}")

    section(1, "主题预判（选知识文件）", "Topic pre-detection")
    topic_hint = pre_detect_topic(note["title"], note["text"])
    topic = topic_hint["topic"]
    print(f"  topic: {topic}  (matched: {topic_hint['matched'] or '—'}, via {topic_hint['via']})")
    if topic == "general":
        print("  → 无现成主题命中；Claude 将在 detect_topic 里给一个自定义标签（如「国漫/动漫推荐」）")

    section(2, "热点检索（按传播力排序）", "Trend retrieval")
    trends_path = out_dir / "trends.json"
    # Prefer the most specific matched alias (the subject, e.g. 完美世界) over a
    # generic one (动漫), so the query actually targets what the note is about.
    matched = sorted(topic_hint["matched"], key=len, reverse=True)
    topic_display = matched[0] if matched else (note["title"][:8] or platform)
    trends = run_retrieval(topic_display, platform, trends_path)
    print(f"  mode: {trends.get('mode')}  |  results: {len(trends.get('results', []))}")
    if trends.get("mode") == "offline":
        print("  → 离线，进入 V1（仅知识库）。这是正常路径。")

    knowledge = load_knowledge(platform, topic)
    print(f"\n  loaded knowledge: platform={knowledge['platform_file']} topic={knowledge['topic_file']}")

    bundle = {
        "platform": platform,
        "note": note,
        "image_check": image_check,
        "topic_hint": topic_hint,
        "trends_file": str(trends_path.relative_to(PROJECT_ROOT)) if trends_path.exists() else None,
        "trends_mode": trends.get("mode"),
        "knowledge": {"platform_file": knowledge["platform_file"],
                      "topic_file": knowledge["topic_file"]},
        "prompts": {
            "extract": "prompts/extract_patterns.md",
            "critique": "prompts/critique_content.md",
            "improve": "prompts/improve_content.md",
            "account_consistency": "prompts/account_consistency.md",
            "risk_audit": "prompts/final_risk_audit.md",
        },
    }
    bundle_path = out_dir / "demo_bundle.json"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    section("3-8", "推理阶段交给 Claude", "Hand off to Claude")
    print("  以下步骤由 Claude 执行对应 prompt 完成（本脚本不做 LLM 推理）：")
    print("    [3] 规律抽取  ← prompts/extract_patterns.md")
    print("    [4] 网感评分  ← prompts/critique_content.md")
    print("    [5] 内容优化  ← prompts/improve_content.md")
    print("    [6] 账号一致性 ← prompts/account_consistency.md")
    print("    [7] 发布风险审查 ← prompts/final_risk_audit.md")
    print("    [8] 呈现 原始 vs 优化 网感指数")
    print(f"\n  输入已打包：{bundle_path.relative_to(PROJECT_ROOT)}")
    print("\n  在 Claude Code 里执行：")
    print(f'    读取 outputs/demo_bundle.json 和图片 {note["image"]}，'
          f"按 SKILL.md 的 Step 3-8 完成网感诊断、重写、账号一致性和风险审查，逐环节输出结果。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
