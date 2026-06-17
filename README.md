# 📈 InternetSensorSkill
### *"Where real-time virality meets long-term account positioning."*

## Introduction

<p align="center">
  <video src="https://github.com/yjzscode/InternetSensorSkill/raw/main/Screen-2026-06-17-155458.mp4" controls muted loop style="width:100%; height:auto; max-width:960px;"></video>
</p>

<details>
  <summary>🎬 Click for Demo Video </summary>
  <br>
  
  [https://github.com/yjzscode/InternetSensorSkill/raw/main/Screen-2026-06-17-155458.mp4](https://github.com/yjzscode/InternetSensorSkill/raw/main/Screen-2026-06-17-155458.mp4)

</details>

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Compatible-green)](https://agentskills.io)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![Codex](https://img.shields.io/badge/Codex-Skill-black)](https://github.com/openai/codex)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-teal)](https://github.com)
[![Hermes](https://img.shields.io/badge/Hermes-Best%20Effort-orange)](https://github.com)
[![License](https://img.shields.io/badge/License-Personal%20Use-lightgrey)](#license)

> 中文文档: [README.zh-CN.md](README.zh-CN.md)

Most writing agents can rewrite. Few can learn what is going viral right now, understand your long-term account positioning, and turn reference creators into a reusable topic engine.

### InternetSensorSkill solves this.

**InternetSensorSkill combines three loops: real-time similar viral-post retrieval, long-term account-positioning alignment, and reference-creator learning reports that turn great creators into topic and writing inspiration.**

In one run, it can:

- Fetch and rank real-time similar viral examples from the target platform.
- Blend those viral patterns with your account persona, audience, tone, and domain boundaries.
- Periodically study reference creators, summarize their high-performing topics and note structures, and feed that learning back into content ideation and rewriting.

`InternetSensorSkill` is the source repository. When installed into an agent host, the skill name is:

```text
trend-aware-content-improver
```

This is still a demo version - please file issues if you find bugs.

[What's New](#whats-new) · [Quick Start](#quick-start) · [Usage](#usage) · [Demo](#demo) · [Core Capabilities](#core-capabilities) · [Supported Platforms](#supported-platforms) · [Layout](#layout) · [License](#license)

---

## What's New

### 1. From prompt rewriting to a full content pipeline

Most AI writing tools do:

```text
input -> prompt rewrite -> output
```

This skill runs a more inspectable workflow:

```text
input
-> account positioning
-> topic detection
-> source-link grounding
-> trend/reference-account retrieval
-> pattern extraction
-> vibe critique
-> rewrite
-> account-consistency scoring
-> fact/platform-risk audit
-> structured outputs
```

### 2. Real-time similar viral examples, not generic writing advice

The skill searches the target platform for similar high-performing posts and ranks them by real or available traction signals. The result is not a generic "make it catchier" rewrite; it is grounded in what is currently working on that platform.

### 3. Viral patterns are blended with account positioning

Viral examples are useful, but copying their persona can damage your long-term account. The skill reads `myaccount/{account_id}/account_positioning.md` and uses it as a guardrail during rewrite and account-consistency scoring.

### 4. Two kinds of references

The pipeline separates:

| Reference type | File | Role |
|---|---|---|
| Hot/viral examples | `reference_examples.json` | Learn hooks, structure, platform phrasing |
| Account-style examples | `account_reference_examples.json` | Keep persona, tone, rhythm, and account positioning |

If the two conflict, the priority is:

```text
source facts > account positioning > account-style examples > hotspot tricks
```

### 5. Reference-creator learning report closes the loop

`learning-report` mode studies the creators you list in `myaccount/{account_id}/reference_accounts.md`, summarizes their high-performing topics, title patterns, note structures, and what is or is not worth learning for your account. This turns reference accounts into a repeatable topic engine instead of one-off inspiration.

### 6. Source-link grounding

If the original post contains a URL, paper PDF, project page, or article, the skill reads it first through `retrieval/source_links.py`. Rewrites must use extracted facts instead of inventing details.

### 7. More agent hosts

The skill was developed mainly around Claude Code, then adapted for Codex, OpenClaw, and Hermes-style AgentSkills hosts.

| Host | Status |
|---|---|
| Claude Code | Primary runtime |
| Codex | Full Xiaohongshu pipeline tested |
| OpenClaw | Installer and AgentSkills layout supported |
| Hermes | Best-effort support with explicit skills directory |

---

## Quick Start

### Install

It's 2026. You have an agent. Let it install the skill for you:

```text
Install the trend-aware-content-improver skill for me:
<your GitHub repo URL>
```

The agent should detect the current host's skills directory, copy or clone the repo, and register the `SKILL.md` entrypoint. Once installed, invoke it by skill name or natural language:

```text
Use the trend-aware-content-improver skill to improve this Xiaohongshu post: ...
```

Codex users can be explicit:

```text
Please use the $trend-aware-content-improver skill ...
```

Claude Code can also use:

```text
/trend-aware-content-improver
```

> Slash-command behavior is host-specific. Codex/OpenClaw/Hermes may prefer natural-language invocation or explicit skill-name invocation.

<details>
<summary>Want to install it yourself? Click for paths.</summary>

```bash
git clone <your GitHub repo URL> InternetSensorSkill
cd InternetSensorSkill

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Claude Code
.venv/bin/python tools/install_skill.py claude --force

# Codex
.venv/bin/python tools/install_skill.py codex --force

# OpenClaw
.venv/bin/python tools/install_skill.py openclaw --force

# Hermes: pass an explicit skills directory if auto-detection does not fit your install
HERMES_SKILLS_DIR="$HOME/.hermes/skills" \
  .venv/bin/python tools/install_skill.py hermes --force
```

| Host | Installed skill path |
|---|---|
| Claude Code | `~/.claude/skills/trend-aware-content-improver` |
| Codex | `~/.codex/skills/trend-aware-content-improver` |
| OpenClaw | `~/.openclaw/workspace/skills/trend-aware-content-improver` |
| Hermes | `~/.hermes/skills/trend-aware-content-improver` or custom `HERMES_SKILLS_DIR` |

The source checkout can stay named `InternetSensorSkill`; the installed skill directory should be named `trend-aware-content-improver`.

</details>

For dependency setup, hosted-search keys, CDP browser setup, and live tests, see [INSTALL.md](INSTALL.md).

---

## Usage

### Main rewrite pipeline

Minimum input:

```text
platform: xiaohongshu / bilibili / zhihu / weixin / weibo / douban / hupu / twitter / linkedin
content: the draft you want to improve
```

Recommended input:

```text
platform: Xiaohongshu
original title: JANO diffusion acceleration algorithm
original body: Our work has been accepted to CVPR 2026 Findings...
source link: https://openaccess.thecvf.com/content/CVPR2026F/papers/...
materials: optional local image paths or notes
```

If the post contains URLs, the skill reads them first and writes extraction results to `source_links.json`. If reading fails, the final answer must say so; it should not pretend the link was read.

### Commands

| Command / intent | Description |
|---|---|
| `/trend-aware-content-improver` | Main rewrite pipeline, when slash commands are available |
| `Improve this Xiaohongshu/Zhihu/Weibo post` | Natural-language trigger |
| `Please use the $trend-aware-content-improver skill ...` | Explicit Codex-style invocation |
| `/trend-aware-content-improver learning-report xiaohongshu 5` | Generate a reference-account learning report |
| `Generate a Xiaohongshu reference-account learning report, 5 posts per account` | Natural-language learning-report trigger |

### Output

Each main run writes a structured bundle:

```text
outputs/{platform}/{specific_topic}/
```

`specific_topic` is generated by the agent:

```text
YYYYMMDD-HHMMSS-topic-slug
```

Examples:

```text
outputs/xiaohongshu/20260617-145010-skill-tool-promo/
outputs/zhihu/20260617-142100-skill-promo/
```

| File | Content |
|---|---|
| `testcase.md` | Input, platform, topic, source links, material paths |
| `source_links.json` | URL/PDF/webpage extraction results |
| `trends.json` | Trend retrieval results with real or available `vibe_score` |
| `reference_examples.json` | Hotspot examples, `reference_role = trend_hotspot` |
| `account_reference_examples.json` | Account-style examples, `reference_role = account_style` |
| `critique.json` | 7-dimension critique of the original content |
| `rewrite.md` | Rewritten post, explanation, before/after vibe index |
| `account_consistency.json` | Account-consistency score after rewrite |
| `risk_audit.json` | Facts requiring confirmation and platform-publishing risks |

Learning-report runs write:

```text
outputs/{platform}/YYYYMMDD-HHMMSS-learning-report/
```

| File | Content |
|---|---|
| `learning_raw.json` | Raw reference-account items, engagement, and `vibe_score` |
| `learning_report.md` | High-performing topics, title patterns, structures, what to learn/avoid |

---

## Demo

The current demo highlights two generated bundles: one Xiaohongshu rewrite with account positioning, and one Zhihu rewrite with no account positioning configured.

### Xiaohongshu: account-aware tool promotion

Demo bundle:

```text
outputs/xiaohongshu/20260617-145010-skill-tool-promo/
```

Input from [`testcase.md`](outputs/xiaohongshu/20260617-145010-skill-tool-promo/testcase.md):

```text
Platform: xiaohongshu
Account: xiaohongshu_FromMath2Mad_example

Original:
实时爆款网感 x 长期账号定位，网感增强.skill成为最好用的个人博主运营助手？
这个skill可以实时抓取相似爆款、理解你的长期账号定位，并把你想学习的大博主沉淀成
可复用的选题引擎，推荐大家都试试，说不定涨粉速度就此起飞了！
```

Output excerpt from [`rewrite.md`](outputs/xiaohongshu/20260617-145010-skill-tool-promo/rewrite.md):

```text
Original vibe index: 34
Improved vibe index: 86

Title:
📍读了俩月文献，我把"怎么发小红书"也做成了一个工具

Body:
🧪 说出来有点好笑，我一个天天泡实验室的人，居然被"小红书怎么发才有人看"卡了好久
😮‍💨 选题靠灵感、文案像写论文，发出去自己都划走

🤖 后来干脆用 AI 写了个小工具（.skill），把我自己摸索的那套流程固化下来：
　• 🔍 实时去扒同主题正在爆的笔记，看它们的钩子和结构长什么样
　• 🎯 记住我账号的长期定位，不会为了蹭热点把我变成另一个人
　• 📚 把我想学的大博主沉淀成一个"选题引擎"，下次没灵感直接调
......
```

What this demo shows:

- Real-time hotspot retrieval is separated from reference-account style examples.
- The rewrite follows the selected account profile: AI research creator, sincere human voice, emoji-led short lines, no hard-sell tone.
- The pipeline removes the unsupported growth promise and records account-consistency and risk-audit outputs.

Account-consistency result from [`account_consistency.json`](outputs/xiaohongshu/20260617-145010-skill-tool-promo/account_consistency.json): `82`.

### Zhihu: idea explanation without account config

Demo bundle:

```text
outputs/zhihu/20260617-142100-skill-promo/
```

Input from [`testcase.md`](outputs/zhihu/20260617-142100-skill-promo/testcase.md):

```text
Platform: zhihu
Topic: 工具推广 / 个人博主运营 / AI skill

Original title:
实时爆款网感 x 长期账号定位，网感增强.skill成为最好用的个人博主运营助手？

Original body:
这个skill可以实时抓取相似爆款、理解你的长期账号定位，并把你想学习的大博主沉淀成
可复用的选题引擎，推荐大家都试试，说不定涨粉速度就此起飞了！
```

Output excerpt from [`rewrite.md`](outputs/zhihu/20260617-142100-skill-promo/rewrite.md):

```text
Title option:
个人博主最耗时的不是写内容，是「定选题」——我用一个 skill 把这步自动化了

Body:
先说结论：个人博主做不起来，多数时候不是不会写，而是
不知道该写什么、对标谁、平台现在吃哪一套。

我把这几步做成了一个能自己跑的 skill（网感增强 .skill），分享一下它实际帮我解决的三件事。

一、实时抓目标平台的相似爆款，而不是凭感觉...
二、把账号定位变成一条硬约束，而不是一句口号...
三、把你想学的大博主，沉淀成可对照的选题参考...

边界说一句：它不替你产出事实，价格、数据、亲身经历这类需要你自己核实的内容...
它只会留占位提醒；它也不保证涨粉。...
```

What this demo shows:

- The skill remains usable when account positioning is empty or unavailable.
- The rewrite changes a salesy claim into a more Zhihu-native explanation.
- It keeps placeholders for facts, metrics, and product availability that the author must confirm.

More generated examples:

- PDF-grounded Xiaohongshu paper rewrite (The user can provide reference URL/PDF/figures):

```text
outputs/xiaohongshu/20260616-194748-jano-diffusion-cvpr2026/
```

- Reference-account learning report:

```text
outputs/xiaohongshu/20260616-184807-learning-report/
```

Report file: [`learning_report.md`](outputs/xiaohongshu/20260616-184807-learning-report/learning_report.md)

---

## Core Capabilities

### 1. Multi-account operation

Each account profile lives in its own folder:

```text
myaccount/{account_id}/
  account_positioning.md
  reference_accounts.md
  para_config.yaml
```

When multiple account folders exist, the skill first asks which account to use. The selected folder becomes `selected_account_dir`, and all positioning, reference accounts, and YAML parameters come from that folder. The legacy root-level `myaccount/*.md` layout is still supported for old installs.

If `myaccount/` is missing or empty, the pipeline still runs normally with no account positioning, no priority reference accounts, and built-in default parameters.

### 2. Account positioning guardrail

Configuration file:

```text
myaccount/{account_id}/account_positioning.md
```

Use it to define:

- Target audience.
- Domain boundaries.
- Content pillars.
- Voice and tone.
- Value proposition.
- Hard constraints.

The main pipeline reads it in Step 0, follows it during rewriting, and scores account consistency after rewriting.

### 3. Priority reference-account retrieval

Configuration file:

```text
myaccount/{account_id}/reference_accounts.md
```

Use it to list accounts or homepage URLs you want to learn from. The main pipeline uses it in two ways:

- Step 2: search these accounts first for topic-relevant content; backfill with general viral retrieval if there are not enough samples.
- Step 2.5: fetch about 3 recent/representative posts from each account as style references. They do not need to match the current topic; they keep persona and tone aligned.

Outputs:

```text
reference_examples.json          # trend reference, reference_role = trend_hotspot
account_reference_examples.json  # account style reference, reference_role = account_style
```

### 4. Source-link grounding

Script:

```text
retrieval/source_links.py
```

Configuration:

```yaml
source_links:
  enabled: true
  max_urls: 5
  max_chars_per_source: 12000
  timeout_seconds: 30
  require_source_grounding_for_urls: true
```

If the draft includes a paper PDF, webpage, or project link, the skill extracts it first. Rewrites must prefer facts supported by these sources. If extraction fails, the rewrite should stay conservative and the risk audit should mention the failure.

### 5. Real trend retrieval and traction scoring

Entry point:

```text
retrieval/retrieve.py
```

Configuration:

```text
myaccount/{account_id}/para_config.yaml
```

Relevant fields:

```yaml
retrieval:
  provider: auto
  limit: 30
  crawl: true
  rank: true
  top: 8
  examples_n: 5
  reference_accounts:
    enabled: true
    min_results_before_fallback: 5

real_vibe_score:
  formula: log_normalized_per_day
  engagement_weights:
    likes: 1.0
    comments: 2.0
    saves: 3.0
    shares: 4.0
    views: 0.01
```

`vibe_score` ranks real retrieved posts. It is not the score for the user's draft. The draft's predicted score is controlled by `predicted_vibe_index`.

### 6. Seven-dimension vibe critique

Prompt:

```text
prompts/critique_content.md
```

Dimensions:

- `hook_strength`
- `novelty`
- `authenticity`
- `shareability`
- `saveability`
- `platform_fit`
- `ai_smell`

Formula configuration:

```yaml
predicted_vibe_index:
  formula: weighted_positive_mean_with_ai_penalty
```

### 7. Account-consistency scoring

Prompt:

```text
prompts/account_consistency.md
```

Configuration:

```yaml
account_consistency:
  formula: weighted_mean_with_penalty_and_caps
  dimensions:
    target_audience_fit: 1.4
    domain_fit: 1.6
    content_pillar_fit: 1.2
    value_promise_fit: 1.2
    voice_style_fit: 1.3
    perspective_fit: 1.0
    reference_account_alignment: 0.8
    platform_format_fit: 0.7
```

It scores only the rewritten content, so a more viral rewrite does not quietly drift away from the account's positioning.

### 8. Fact and platform-risk audit

Prompt:

```text
prompts/final_risk_audit.md
```

Configuration:

```yaml
risk_audit:
  enabled: true
  require_user_confirmation_for:
    - data/percentages/amounts/prices/times/rankings
    - personal experiences/cases/customer outcomes
    - medical/legal/investment/education high-risk judgments
    - efficacy or income promises
```

Output:

```text
risk_audit.json
```

This is a publishing-risk reminder, not legal advice. It lists facts that must be confirmed by the user.

---

## Advanced Usage

### 1. Customize common parameters

Central configuration file:

```text
myaccount/{account_id}/para_config.yaml
```

You can adjust:

- Web/search retrieval size and saved example count.
- Whether to crawl result pages.
- Hotspot reference sample count.
- Account-style sample count per reference account.
- Learning-report sample count per account.
- Real `vibe_score` formula and engagement weights.
- Predicted vibe-index formula for the user's draft.
- Account-consistency weights, penalties, and caps.
- Output filenames.

Explicit CLI flags override YAML values.

### 2. Generate periodic reference-account learning reports

First fill:

```text
myaccount/{account_id}/reference_accounts.md
```

Then invoke:

```text
/trend-aware-content-improver learning-report xiaohongshu 5
```

Or use natural language:

```text
Generate a Xiaohongshu reference-account learning report, 5 posts per account.
```

Output:

```text
outputs/xiaohongshu/YYYYMMDD-HHMMSS-learning-report/
```

It crawls recent reference-account content, calculates real or available `vibe_score`, and summarizes:

- High-performing recent topics.
- Common title patterns.
- Content structures.
- User questions or demand signals.
- What your account should learn.
- What would conflict with your positioning.

### 3. Extend platform and topic knowledge

Platform rules:

```text
knowledge/platforms/{platform}.yaml
```

Topic rules:

```text
knowledge/topics/{topic}.yaml
```

Retrieval strategy registry:

```text
retrieval/strategy.py
```

Native retrieval examples:

```text
retrieval/bilibili.py
retrieval/cdp_platforms.py
```

---

## Supported Platforms

### Social platforms

| Platform | Offline V1 rules | Live V2 retrieval | Notes |
|---|---:|---|---|
| Bilibili | yes | Key-free native REST | Structured views/likes/favorites available |
| Xiaohongshu | yes | CDP real browser | Requires explicit consent; uses local browser login state |
| Zhihu | yes | CDP real browser | Requires explicit consent |
| Weixin Official Account | yes | CDP real browser / Sogou gateway | Requires explicit consent |
| Weibo | yes | CDP real browser | Server-side m.weibo.cn search often hits anti-bot walls |
| Douban | yes | CDP real browser | Requires explicit consent |
| Hupu | yes | CDP real browser | Requires explicit consent |
| Twitter / X | yes | SearXNG / DuckDuckGo + `site:` targeting | Self-hosted SearXNG can avoid browser fallback |
| LinkedIn | yes | SearXNG / DuckDuckGo + `site:` targeting | Same as above |

CDP retrieval drives the user's real local browser and may use existing login state. It can carry platform-detection risk, so the skill asks for explicit consent first. Without consent, it falls back to the offline V1 knowledge base and writes a structured `consent_required` state.

### Agent hosts

| Agent host | Status | Notes |
|---|---|---|
| Claude Code | primary | Main development/runtime environment; slash command supported |
| Codex | tested | Installed to `~/.codex/skills/trend-aware-content-improver`; full Xiaohongshu pipeline tested |
| OpenClaw | installer support | AgentSkills layout and installer path supported; live retrieval should be tested in target environment |
| Hermes | conservative support | Supports explicit skills directory; discovery rules may differ by distribution |
| Other AgentSkills hosts | best effort | Should work if the host can read `SKILL.md`, run Python, and write outputs |

Verified focus:

- Claude Code: primary iteration environment.
- Codex: Xiaohongshu main pipeline tested, including PDF reading, structured outputs, rewrite, account consistency, and risk audit.
- Xiaohongshu live hotspot/reference-account retrieval: requires explicit browser consent; otherwise structured fallback is expected.

---

## Layout

```text
InternetSensorSkill/
  SKILL.md
  README_opensource.md
  README_opensource.zh-CN.md
  INSTALL.md
  ARCHITECTURE.md
  requirements.txt

  agents/
    openai.yaml

  myaccount/
    platform_id/
      account_positioning.md
      reference_accounts.md
      para_config.yaml
    # local account folders can be added here and are not required for install

  prompts/
    detect_topic.md
    extract_patterns.md
    critique_content.md
    improve_content.md
    account_consistency.md
    final_risk_audit.md
    learning_report.md

  knowledge/
    platforms/
    topics/

  retrieval/
    retrieve.py
    source_links.py
    learning_report.py
    strategy.py
    engagement.py
    bilibili.py
    weibo.py
    cdp_platforms.py
    searxng.py
    tavily.py
    exa.py
    firecrawl.py
    crawl4ai.py

  skills/
    web-access/

  outputs/
    .gitkeep
    xiaohongshu/
      20260617-145010-skill-tool-promo/
      20260616-194748-jano-diffusion-cvpr2026/
      20260616-184807-learning-report/
    zhihu/
      20260617-142100-skill-promo/

  tests/
  tools/
```

---

## Testing

After installing dependencies:

```bash
.venv/bin/python -m compileall retrieval/
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Unit tests mock HTTP by default and do not hit real platforms.

Live retrieval tests are opt-in:

```bash
TREND_LIVE_BILIBILI=1 .venv/bin/python -m unittest tests/test_live_contracts.py -v

TREND_LIVE_CDP=1 TREND_LIVE_CDP_PLATFORM=xiaohongshu \
  .venv/bin/python -m unittest tests/test_live_contracts.py -v
```

---

## Safety and Privacy

- Do not commit `.env`, `config.json`, `~/.trend-improver/config.json`, or any API key.
- CDP retrieval uses your local browser and may use existing login state. Consent is required.
- Social platforms may detect automation. Real accounts can face rate-limit or risk controls.
- The risk audit is a publishing-risk reminder, not legal, medical, investment, or compliance advice.
- Facts about papers, prices, rankings, medical/legal/investment claims, and other concrete claims still need user confirmation before publishing.

---

## Acknowledge

The browser-access capability under `skills/web-access/` references and integrates ideas and code structure from [eze-is/web-access](https://github.com/eze-is/web-access). It provides CDP-based real-browser access, dynamic page reading, and login-state-aware browsing, which are important foundations for live retrieval on Xiaohongshu, Zhihu, Weixin, Douban, Hupu, and Weibo.

Thanks to the AgentSkills community for exploring portable skill structure, installation flows, and cross-agent interoperability.

---

## License

This project uses a personal-use-friendly source-available license statement:

- Personal learning, research, self-use, and non-commercial projects are allowed.
- Local installation and modification for personal accounts, local agents, and internal experiments are allowed.
- You may not directly package this project or its core functionality into a commercial product, SaaS, paid plugin, template-marketplace item, course bundle, or agency tool without permission.
- You may not remove attribution and republish it as your own similar product.
- For commercial integration, redistribution, team deployment, or productized use, please obtain authorization first.

See the standalone [LICENSE](LICENSE) file for the controlling license text and the Chinese reference translation.
