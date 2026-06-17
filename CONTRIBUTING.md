# Contributing to Trend-Aware Content Improver / 贡献指南

> English first, 中文在下方。

Thank you for improving this skill. This project is a trend-aware content
optimization skill: it diagnoses why content lacks platform-native "vibe" and
rewrites it using platform rules, topic knowledge, and optional live trend
retrieval.

感谢你改进这个 Skill。本项目是一个「网感增强引擎」：诊断内容为什么缺少平台网感，并结合
平台规则、主题知识库和可选的实时热点检索来优化内容。

---

## What To Contribute / 可以贡献什么

- **Platform knowledge**: add or improve `knowledge/platforms/*.yaml`.
- **Topic knowledge**: add or improve `knowledge/topics/*.yaml`.
- **Reasoning prompts**: refine `prompts/*.md` for topic detection, pattern
  extraction, critique, or rewrite.
- **Retrieval providers**: add real trend sources under `retrieval/`.
- **Engagement scoring**: improve extraction or ranking in
  `retrieval/engagement.py`.
- **Docs and examples**: update `README.md`, `INSTALL.md`, `ARCHITECTURE.md`,
  `SKILL.md`, and `examples/`.
- **Tests**: add `unittest` coverage under `tests/`.

---

## Project Shape / 项目结构

```text
SKILL.md            # Agent-facing entry point and six-step workflow
prompts/            # LLM reasoning instructions, written as Markdown
knowledge/          # Offline V1 platform/topic rules, written as YAML
retrieval/          # Deterministic Python CLIs for V2 trend retrieval
tests/              # unittest suite, mocked network by default
examples/           # Walkthrough examples
outputs/            # Runtime artifacts such as trends.json
```

The core design is **reasoning / knowledge / retrieval separation**:

- Prompts decide how to reason.
- YAML files hold editable platform and topic knowledge.
- Python code retrieves, normalizes, scores, and ranks trend samples.

---

## Development Setup / 开发环境

```bash
cd InternetSensorSkill
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run the full local test suite:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m compileall retrieval tests
```

For the deterministic demo pipeline:

```bash
.venv/bin/python tests/demo_pipeline.py --preset perfect-world
```

The demo runs image checks, topic pre-detection, retrieval, and knowledge
loading. The final reasoning steps are intentionally left for the agent to run
from `prompts/`.

---

## Coding Guidelines / 代码规范

- Match surrounding style. This project intentionally stays lightweight and uses
  the Python standard library where practical.
- Keep CLIs runnable directly with `if __name__ == "__main__":`.
- Keep provider output normalized through `_common.make_result()` and
  `_common.make_envelope()`.
- Prefer graceful fallback over hard failure. Retrieval problems should normally
  produce `mode: "offline"` so the V1 knowledge-base path still works.
- Do not add dependencies unless they clearly reduce complexity. If you add one,
  update `requirements.txt` and `INSTALL.md`.
- Keep prompts concise and operational. They should tell the agent what to
  output, not bury behavior in long essays.

---

## Adding Platform Or Topic Knowledge / 新增平台或主题

Platform YAML files must include the keys checked by
`tests/test_knowledge.py`:

```yaml
platform: xiaohongshu
display_name: 小红书 / RED
language: zh
title_patterns: []
emotion_levers: []
structure: []
formatting: {}
ai_smell_signals: []
dos: []
donts: []
```

Topic YAML files must include:

```yaml
topic: food
display_name: 美食 / 校园美食
aliases: []
audience_intent: []
typical_hooks: []
saveability_cues: []
credibility_cues: []
ai_smell_signals: []
```

After changing knowledge files, run:

```bash
.venv/bin/python -m unittest tests/test_knowledge.py -v
```

---

## Adding Retrieval Providers / 新增检索源

New providers should follow the existing pattern:

1. Add a module under `retrieval/<provider>.py`.
2. Expose a `search(...) -> dict` function.
3. Return normalized envelopes and results using `_common`.
4. Register the provider in `retrieval/retrieve.py` if it is selectable.
5. Register platform routing in `retrieval/strategy.py` when needed.
6. Add tests with mocked HTTP or fake clients.

Provider rules:

- **No live API calls in unit tests.** Mock HTTP with `unittest.mock` or injected
  fake sessions.
- **Handle auth clearly.** API keys come from environment variables or
  `~/.trend-improver/config.json`.
- **Handle rate limits.** Use `_common.request_with_retry()` for HTTP providers.
- **Preserve fallback.** Missing keys or transient provider failures should not
  break the whole skill.
- **Prefer structured engagement.** If the source gives likes, comments, saves,
  shares, dates, or play counts, attach them before ranking.

---

## Browser/CDP Safety / 浏览器与 CDP 安全边界

小红书、知乎、微信公众号使用 `retrieval/cdp_platforms.py` 驱动用户本机真实浏览器。
This can use the user's logged-in session, so it has a strict consent boundary.

- Never bypass `ConsentRequired`.
- Do not add `--consent` unless the user has explicitly agreed.
- If the browser is not logged in, surface `login_required` and ask the user to
  log in before retrying.
- If CDP is unavailable, fall back to keyed search or V1 offline behavior.

---

## Security / 安全

- Never commit API keys, cookies, browser profiles, personal data, or generated
  private outputs.
- Retrieval keys belong in environment variables or
  `~/.trend-improver/config.json` with mode `0600`.
- Do not hard-code credentials in tests, examples, docs, or fixtures.
- Treat CDP browser access as sensitive because it may use a real logged-in
  account.

---

## Documentation / 文档

Update docs when behavior changes:

- User-facing workflow or platform support: `README.md` and `SKILL.md`.
- Architecture, scoring, or provider routing: `ARCHITECTURE.md`.
- Setup, keys, or browser/CDP steps: `INSTALL.md`.
- New demo behavior: `examples/` or `tests/demo_pipeline.py`.

Keep bilingual docs practical. English and Chinese are welcome, but exactness
matters more than mirroring every sentence.

---

## Pull Request Checklist / PR 检查清单

Before handing off a change:

- Relevant tests pass.
- New behavior has focused tests.
- Docs are updated when user-facing behavior changes.
- No secrets or personal data are committed.
- Runtime artifacts in `outputs/` are not treated as source of truth.

---

# 中文补充

这个项目最好按「小步、可验证」的方式改：

- 改平台风格，优先改 `knowledge/platforms/*.yaml`。
- 改主题表达，优先改 `knowledge/topics/*.yaml`。
- 改推理方式，改 `prompts/*.md`。
- 改真实热点来源，改 `retrieval/` 并补测试。
- 改传播力排序，改 `retrieval/engagement.py` 并说明公式变化。

最重要的约束：检索失败不是崩溃，而是正常回退；CDP 浏览器检索必须先获得用户同意。
