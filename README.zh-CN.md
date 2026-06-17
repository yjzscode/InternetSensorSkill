# 📈 InternetSensorSkill（网感增强.skill）
### *实时爆款网感 × 长期账号定位*

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Compatible-green)](https://agentskills.io)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![Codex](https://img.shields.io/badge/Codex-Skill-black)](https://github.com/openai/codex)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-teal)](https://github.com)
[![Hermes](https://img.shields.io/badge/Hermes-Best%20Effort-orange)](https://github.com)
[![License](https://img.shields.io/badge/License-Personal%20Use-lightgrey)](#许可)

> English README: [README.md](README.md)

大多数写作 Agent 会改写文案，但很少能同时做到：实时抓取相似爆款、理解你的长期账号定位，并把你想学习的大博主沉淀成可复用的选题引擎。

### InternetSensorSkill solves this.

**InternetSensorSkill 把三条链路合在一起：实时相似爆款检索、长期账号定位对齐、参考大博主学习报告，从而形成“选题学习 -> 文案改写 -> 账号一致性审查”的闭环。**

一次运行里，它可以：

- 抓取并排序目标平台上的实时相似爆款样本。
- 把爆款网感与账号人设、受众、语气、领域边界结合起来。
- 周期性学习你指定的大博主，总结他们的高赞选题、标题句式和笔记结构，再反哺选题和文案产出。

`InternetSensorSkill` 是源码仓库目录。安装到 Agent 宿主后，skill 名称是：

```text
trend-aware-content-improver
```

This is still a demo version - please file issues if you find bugs.

[更新亮点](#更新亮点) · [快速开始](#快速开始) · [使用方法](#使用方法) · [Demo](#demo) · [核心能力](#核心能力) · [支持平台](#支持平台) · [项目结构](#项目结构) · [许可](#许可)

---

## 更新亮点

### 1. 从 prompt 改写升级为完整内容流水线

大多数 AI 写作工具是：

```text
输入内容 -> prompt 改写 -> 输出文案
```

这个 skill 的流程更像一个内容运营助手：

```text
输入内容
-> 账号定位
-> 主题识别
-> 用户来源链接读取
-> 热点/参考账号检索
-> 爆款规律抽取
-> 原文网感评分
-> 改写
-> 账号一致性评分
-> 事实/发布风险审查
-> 结构化产物保存
```

### 2. 实时相似爆款，而不是泛泛写作建议

skill 会在目标平台内检索相似的高表现内容，并用真实或可得的互动数据排序。它不是泛泛地说“标题更吸引人一点”，而是基于平台当下正在跑出来的内容规律来改写。

### 3. 爆款规律必须和账号定位结合

爆款样本有价值，但照搬别人的人设会伤害长期账号。skill 会读取 `myaccount/{account_id}/account_positioning.md`，把账号定位作为改写和账号一致性评分的硬约束。

### 4. 两类参考样本分离

流水线现在区分：

| 参考类型 | 文件 | 作用 |
|---|---|---|
| 热点/爆款样本 | `reference_examples.json` | 学标题钩子、结构、平台表达 |
| 账号风格样本 | `account_reference_examples.json` | 守住人设、语气、节奏和账号定位 |

如果两者冲突，优先级是：

```text
用户来源事实 > 账号定位 > 账号风格样本 > 热点网感技巧
```

### 5. 参考大博主学习报告，形成选题闭环

`learning-report` 模式会学习 `myaccount/{account_id}/reference_accounts.md` 里列出的账号，总结他们最近的高赞选题、标题句式、笔记结构，以及哪些适合/不适合你的账号。这样参考账号不只是临时灵感，而会变成可复用的选题引擎。

### 6. 来源链接事实 grounding

如果原文包含 URL、论文 PDF、项目页或网页，skill 会先通过 `retrieval/source_links.py` 读取来源。后续改写必须使用来源里能支持的事实，而不是凭原文猜测。

### 7. 更多 Agent 宿主适配

这个 skill 主要围绕 Claude Code 开发，然后适配到 Codex、OpenClaw 和 Hermes 风格的 AgentSkills 宿主。

| 宿主 | 状态 |
|---|---|
| Claude Code | 主要运行环境 |
| Codex | 已通过小红书全 pipeline 测试 |
| OpenClaw | 支持安装器和 AgentSkills 目录结构 |
| Hermes | 支持显式传入 skills 目录的保守适配 |

---

## 快速开始

### 安装

都 2026 了，有 Agent 就让 Agent 自己安装。打开 Claude Code / Codex / OpenClaw / Hermes，把这句话交给它：

```text
帮我安装这个 skill：<你的 GitHub 仓库地址>
安装后 skill 名称使用 trend-aware-content-improver
```

安装后可以这样触发：

```text
帮我给这条小红书笔记增强网感：...
```

或更显式地：

```text
请使用 trend-aware-content-improver skill，平台是小红书，帮我优化以下内容：...
```

Codex 里也可以写：

```text
请使用 $trend-aware-content-improver skill ...
```

Claude Code 可以使用：

```text
/trend-aware-content-improver
```

> Slash command 是否可用由宿主决定。Codex/OpenClaw/Hermes 更推荐自然语言触发或显式提到 skill 名称。

<details>
<summary>想手动安装？点开看路径。</summary>

```bash
git clone <你的 GitHub 仓库地址> InternetSensorSkill
cd InternetSensorSkill

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Claude Code
.venv/bin/python tools/install_skill.py claude --force

# Codex
.venv/bin/python tools/install_skill.py codex --force

# OpenClaw
.venv/bin/python tools/install_skill.py openclaw --force

# Hermes：如果自动识别不符合你的安装方式，可以显式传入 skills 目录
HERMES_SKILLS_DIR="$HOME/.hermes/skills" \
  .venv/bin/python tools/install_skill.py hermes --force
```

| 宿主 | 安装后的 skill 路径 |
|---|---|
| Claude Code | `~/.claude/skills/trend-aware-content-improver` |
| Codex | `~/.codex/skills/trend-aware-content-improver` |
| OpenClaw | `~/.openclaw/workspace/skills/trend-aware-content-improver` |
| Hermes | `~/.hermes/skills/trend-aware-content-improver` 或自定义 `HERMES_SKILLS_DIR` |

源码目录可以继续叫 `InternetSensorSkill`。安装到宿主后，目录名应为 `trend-aware-content-improver`。

</details>

依赖安装、搜索 key、CDP 浏览器设置和 live test 见 [INSTALL.md](INSTALL.md)。

---

## 使用方法

### 主改写流程

最少只需要：

```text
平台：xiaohongshu / bilibili / zhihu / weixin / weibo / douban / hupu / twitter / linkedin
内容：一段待优化文字
```

推荐输入：

```text
平台：小红书
原始标题：知晓过去，加速未来——Jano diffusion加速算法
原始正文：和球友快乐干饭快乐打球顺便开组会的工作，已经发表在 CVPR 2026 Findings...
来源链接：https://openaccess.thecvf.com/content/CVPR2026F/papers/...
图片或素材：可选，本地路径或说明
```

如果内容里包含 URL，skill 会先读取它们，并把抽取结果写入 `source_links.json`。如果读取失败，最终结果必须说明，不会假装读过链接。

### 触发方式

| 命令 / 意图 | 说明 |
|---|---|
| `/trend-aware-content-improver` | 主改写流程，取决于宿主是否支持 slash command |
| `帮我优化这条小红书/知乎/微博/...` | 自然语言触发 |
| `请使用 $trend-aware-content-improver skill ...` | Codex 风格显式触发 |
| `/trend-aware-content-improver learning-report xiaohongshu 5` | 生成参考账号学习报告 |
| `生成小红书参考账号学习报告，每个账号抓 5 条` | 自然语言触发学习报告 |

### 输出

每次主流程会写出结构化产物：

```text
outputs/{platform}/{specific_topic}/
```

`specific_topic` 由 agent 自动生成：

```text
YYYYMMDD-HHMMSS-topic-slug
```

示例：

```text
outputs/xiaohongshu/20260617-145010-skill-tool-promo/
outputs/zhihu/20260617-142100-skill-promo/
```

| 文件 | 内容 |
|---|---|
| `testcase.md` | 本次输入、平台、主题、来源链接、素材路径 |
| `source_links.json` | URL/PDF/网页抽取结果 |
| `trends.json` | 热点检索结果，含真实或可得的 `vibe_score` |
| `reference_examples.json` | 热点参考样本，`reference_role = trend_hotspot` |
| `account_reference_examples.json` | 账号风格样本，`reference_role = account_style` |
| `critique.json` | 原文 7 维度网感评分和问题清单 |
| `rewrite.md` | 改写版本、改动说明、前后网感指数 |
| `account_consistency.json` | 改写后账号一致性评分 |
| `risk_audit.json` | 必须确认事实和平台发布风险 |

学习报告模式会写到：

```text
outputs/{platform}/YYYYMMDD-HHMMSS-learning-report/
```

| 文件 | 内容 |
|---|---|
| `learning_raw.json` | 参考账号抓取原始结果、互动量和 `vibe_score` |
| `learning_report.md` | 高赞选题、标题句式、内容结构、适合/不适合学习 |

---

## Demo

这里展示当前版本生成的两个产物：一个是带账号定位的小红书改写，一个是没有账号定位配置时的知乎改写。

### 小红书：结合账号人设的工具推广

示例目录：

```text
outputs/xiaohongshu/20260617-145010-skill-tool-promo/
```

输入来自 [`testcase.md`](outputs/xiaohongshu/20260617-145010-skill-tool-promo/testcase.md)：

```text
平台：xiaohongshu
账号：xiaohongshu_FromMath2Mad_example

原文：
实时爆款网感 x 长期账号定位，网感增强.skill成为最好用的个人博主运营助手？
这个skill可以实时抓取相似爆款、理解你的长期账号定位，并把你想学习的大博主沉淀成
可复用的选题引擎，推荐大家都试试，说不定涨粉速度就此起飞了！
```

输出节选自 [`rewrite.md`](outputs/xiaohongshu/20260617-145010-skill-tool-promo/rewrite.md)：

```text
原始网感指数：34
优化后网感指数：86

标题：
📍读了俩月文献，我把"怎么发小红书"也做成了一个工具

正文：
🧪 说出来有点好笑，我一个天天泡实验室的人，居然被"小红书怎么发才有人看"卡了好久
😮‍💨 选题靠灵感、文案像写论文，发出去自己都划走

🤖 后来干脆用 AI 写了个小工具（.skill），把我自己摸索的那套流程固化下来：
　• 🔍 实时去扒同主题正在爆的笔记，看它们的钩子和结构长什么样
　• 🎯 记住我账号的长期定位，不会为了蹭热点把我变成另一个人
　• 📚 把我想学的大博主沉淀成一个"选题引擎"，下次没灵感直接调
......
```

这个 demo 展示了：

- 实时热点样本和参考账号风格样本会被分开标注。
- 改写会服从选中的账号定位：AI 科研女博主、真诚活人感、每句 emoji 开头、避免推销腔。
- 删除“涨粉速度就此起飞”这类无法证明的效果承诺，并写出账号一致性和风险审查产物。

账号一致性评分见 [`account_consistency.json`](outputs/xiaohongshu/20260617-145010-skill-tool-promo/account_consistency.json)：`82`。

### 知乎：没有账号配置时仍可完整改写

示例目录：

```text
outputs/zhihu/20260617-142100-skill-promo/
```

输入来自 [`testcase.md`](outputs/zhihu/20260617-142100-skill-promo/testcase.md)：

```text
平台：zhihu
主题：工具推广 / 个人博主运营 / AI skill

原始标题：
实时爆款网感 x 长期账号定位，网感增强.skill成为最好用的个人博主运营助手？

原始正文：
这个skill可以实时抓取相似爆款、理解你的长期账号定位，并把你想学习的大博主沉淀成
可复用的选题引擎，推荐大家都试试，说不定涨粉速度就此起飞了！
```

输出节选自 [`rewrite.md`](outputs/zhihu/20260617-142100-skill-promo/rewrite.md)：

```text
标题选项：
个人博主最耗时的不是写内容，是「定选题」——我用一个 skill 把这步自动化了

正文：
先说结论：个人博主做不起来，多数时候不是不会写，而是
不知道该写什么、对标谁、平台现在吃哪一套。

我把这几步做成了一个能自己跑的 skill（网感增强 .skill），分享一下它实际帮我解决的三件事。

一、实时抓目标平台的相似爆款，而不是凭感觉...
二、把账号定位变成一条硬约束，而不是一句口号...
三、把你想学的大博主，沉淀成可对照的选题参考...

边界说一句：它不替你产出事实，价格、数据、亲身经历这类需要你自己核实的内容...
它只会留占位提醒；它也不保证涨粉。...
```

这个 demo 展示了：

- 即使没有账号定位配置，skill 也会正常跑完整 pipeline。
- 把偏推销的表达改成更适合知乎的解释型结构。
- 对事实、数据、效果承诺和产品可用性保留用户确认提醒。

更多生成结果：

- 读取论文 PDF 后生成的小红书科研笔记（用户可以提供参考url/pdf/fig）：

```text
outputs/xiaohongshu/20260616-194748-jano-diffusion-cvpr2026/
```

- 参考账号学习报告生成：

```text
outputs/xiaohongshu/20260616-184807-learning-report/
```

报告见 [`learning_report.md`](outputs/xiaohongshu/20260616-184807-learning-report/learning_report.md)。

---

## 核心能力

### 1. 多账号同时运营

每个账号一个独立文件夹：

```text
myaccount/{account_id}/
  account_positioning.md
  reference_accounts.md
  para_config.yaml
```

当存在多个账号文件夹时，skill 会先询问“这次要用哪个账号做？”。选定后，该文件夹会成为 `selected_account_dir`，账号定位、参考账号和参数 YAML 都从这里读取。旧版根目录 `myaccount/*.md` 结构仍然兼容。

如果没有设置 `myaccount/`，或目录为空，pipeline 仍会正常跑完：账号定位不可用、优先参考账号不可用，参数使用代码内置默认值。

### 2. 账号定位守门

配置文件：

```text
myaccount/{account_id}/account_positioning.md
```

可写入：

- 目标推送群体。
- 领域边界。
- 内容支柱。
- 风格语气。
- 价值主张。
- 不能碰的硬约束。

主流程 Step 0 会读取它；Step 5 改写时会优先遵守；Step 6 只评价“改写后内容”的账号一致性。

### 3. 参考账号优先检索

配置文件：

```text
myaccount/{account_id}/reference_accounts.md
```

支持写目标平台的大博主主页或账号 URL。主流程中有两个用途：

- Step 2：优先搜索这些账号与当前主题相关的内容，样本不足再回退到普通爆款检索。
- Step 2.5：额外抓取每个参考账号约 3 条内容，作为账号风格参考。它们可以和本次主题无关，主要用于守住人设、语气和节奏。

对应输出：

```text
reference_examples.json          # 热点参考，reference_role = trend_hotspot
account_reference_examples.json  # 账号风格参考，reference_role = account_style
```

### 4. 来源链接事实 grounding

脚本：

```text
retrieval/source_links.py
```

配置：

```yaml
source_links:
  enabled: true
  max_urls: 5
  max_chars_per_source: 12000
  timeout_seconds: 30
  require_source_grounding_for_urls: true
```

如果原文包含论文 PDF、网页或项目链接，skill 会先读取它们。后续改写必须优先使用来源里能支持的事实；读取失败时，只能基于原文保守改写，并在 `risk_audit.json` 中说明。

### 5. 真实热点检索与传播力评分

入口：

```text
retrieval/retrieve.py
```

配置：

```text
myaccount/{account_id}/para_config.yaml
```

相关字段：

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

真实帖子的 `vibe_score` 用来挑参考样本；它不是用户原文的质量分。用户原文的预测网感指数由 `predicted_vibe_index` 控制。

### 6. 7 维度网感诊断

Prompt：

```text
prompts/critique_content.md
```

评分维度：

- `hook_strength`
- `novelty`
- `authenticity`
- `shareability`
- `saveability`
- `platform_fit`
- `ai_smell`

公式配置：

```yaml
predicted_vibe_index:
  formula: weighted_positive_mean_with_ai_penalty
```

### 7. 账号一致性评分

Prompt：

```text
prompts/account_consistency.md
```

配置：

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

它只评价改写后内容，避免“为了增强网感，把账号定位改没了”。

### 8. 事实风险与平台发布风险

Prompt：

```text
prompts/final_risk_audit.md
```

配置：

```yaml
risk_audit:
  enabled: true
  require_user_confirmation_for:
    - 数据/比例/金额/价格/时间/排名
    - 亲身经历/案例/客户结果
    - 医学/法律/投资/教育升学等高风险判断
    - 功效承诺/收益承诺/绝对化表述
```

输出文件：

```text
risk_audit.json
```

这一步不做法律判断，只做发布前风险提醒，并输出“必须用户确认”的事实列表。

---

## 高阶玩法

### 1. 自定义所有常用参数

集中配置文件：

```text
myaccount/{account_id}/para_config.yaml
```

你可以调整：

- Web/search 检索数量、保存数量、是否抓取页面。
- 热点参考样本数量。
- 每个参考账号抓几条。
- learning report 每个账号抓几条。
- 真实 `vibe_score` 公式和互动权重。
- 用户原文预测网感指数公式。
- 账号一致性评分权重、惩罚和 caps。
- 输出文件名。

命令行显式传入的参数优先级高于 YAML。

### 2. 周期性生成竞品账号学习报告

先填写：

```text
myaccount/{account_id}/reference_accounts.md
```

然后在宿主中触发：

```text
/trend-aware-content-improver learning-report xiaohongshu 5
```

或自然语言：

```text
生成小红书参考账号学习报告，每个账号抓 5 条
```

输出：

```text
outputs/xiaohongshu/YYYYMMDD-HHMMSS-learning-report/
```

它会抓取参考账号近期内容和真实或可得的 `vibe_score`，再总结：

- 最近高赞选题。
- 常用标题句式。
- 内容结构。
- 用户高频问题。
- 适合你学习的部分。
- 不适合你账号定位的部分。

### 3. 为平台和主题扩展知识库

平台规则：

```text
knowledge/platforms/{platform}.yaml
```

主题规则：

```text
knowledge/topics/{topic}.yaml
```

新增平台检索策略：

```text
retrieval/strategy.py
```

新增原生检索源可参考：

```text
retrieval/bilibili.py
retrieval/cdp_platforms.py
```

---

## 支持平台

### 社交平台

| 平台 | V1 离线规则 | V2 真实检索策略 | 说明 |
|---|---:|---|---|
| Bilibili | yes | 原生免密钥 REST | 可直接拿播放、点赞、收藏等结构化互动 |
| Xiaohongshu | yes | CDP 真实浏览器 | 需要用户明确同意，使用本机登录态搜索和读取 |
| Zhihu | yes | CDP 真实浏览器 | 需要用户明确同意 |
| Weixin Official Account | yes | CDP 真实浏览器 / 搜狗入口 | 需要用户明确同意 |
| Weibo | yes | CDP 真实浏览器 | m.weibo.cn 服务端搜索容易触发反爬，当前策略走浏览器 |
| Douban | yes | CDP 真实浏览器 | 需要用户明确同意 |
| Hupu | yes | CDP 真实浏览器 | 需要用户明确同意 |
| Twitter / X | yes | SearXNG / DuckDuckGo + `site:` 定向 | 自建 SearXNG 可免浏览器；否则可能走浏览器回退 |
| LinkedIn | yes | SearXNG / DuckDuckGo + `site:` 定向 | 同上 |

CDP 平台会驱动用户本机真实浏览器，可能使用登录态，存在平台检测风险。因此 skill 里要求先征得用户同意；未同意时会回退到 V1 规则库，并写出 `consent_required` 状态。

### Agent 框架

| Agent host | 适配状态 | 说明 |
|---|---|---|
| Claude Code | primary | 主要开发和日常使用环境，支持 slash command 和 AgentSkills 目录 |
| Codex | tested | 已安装到 `~/.codex/skills/trend-aware-content-improver`，并在小红书 JANO 示例上通过全 pipeline 测试 |
| OpenClaw | installer support | 提供安装路径适配和 AgentSkills 文件结构，建议在目标环境再做一次真实平台检索测试 |
| Hermes | conservative support | 支持显式传入 skills 目录安装；不同 Hermes 分发的 skill discovery 规则可能不同 |
| Other AgentSkills hosts | best effort | 只要能读取 `SKILL.md`、运行 Python 和写入 outputs，就可以按同一流程执行 |

已验证重点：

- Claude Code：作为主要运行框架迭代。
- Codex：已验证小红书主流程，包含 PDF 读取、结构化输出、改写、账号一致性和风险审查。
- 小红书真实热点/参考账号检索：需要用户显式授权浏览器；未授权时会结构化降级。

---

## 项目结构

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
    # 可以在这里添加本地账号文件夹，安装时不是必需项

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

## 测试

安装依赖后运行：

```bash
.venv/bin/python -m compileall retrieval/
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

这些单元测试默认 mock HTTP，不会打真实平台。

真实检索测试需要手动开启：

```bash
TREND_LIVE_BILIBILI=1 .venv/bin/python -m unittest tests/test_live_contracts.py -v

TREND_LIVE_CDP=1 TREND_LIVE_CDP_PLATFORM=xiaohongshu \
  .venv/bin/python -m unittest tests/test_live_contracts.py -v
```

---

## 安全与隐私

- 不要提交 `.env`、`config.json`、`~/.trend-improver/config.json` 或任何 API key。
- CDP 检索会使用你本机浏览器和可能存在的登录态；使用前必须明确同意。
- 社交平台可能检测自动化行为，真实账号有风控风险。
- 本 skill 的风险审查只做发布风险提醒，不构成法律、医学、投资或合规建议。
- 对论文、价格、排名、医学/法律/投资判断等具体事实，发布前仍需用户确认。

---

## Acknowledge

`skills/web-access/` 的浏览器联网能力参考并集成自 [eze-is/web-access](https://github.com/eze-is/web-access) 的思路与代码结构。它提供了 CDP 真实浏览器连接、动态页面读取和登录态场景下的网页访问能力，是本项目小红书、知乎、微信公众号、豆瓣、虎扑、微博等平台真实检索能力的重要基础。

感谢 AgentSkills 社区对于 skill 结构、安装方式和跨 agent 可移植性的探索。

---

## 许可

本项目采用个人使用友好的 source-available 许可说明：

- 允许个人学习、研究、自用和非商业项目使用。
- 允许在个人账号、本地 agent、内部实验环境中安装和修改。
- 禁止未经授权将本项目或其主要功能直接打包为商业产品、SaaS、付费插件、模板市场商品、课程配套售卖物或代运营工具出售。
- 禁止去除署名后重新发布为自己的同类产品。
- 如需商业集成、二次分发、团队部署或产品化使用，请先获得作者授权。

正式授权边界以根目录 [LICENSE](LICENSE) 文件为准，其中包含英文主文本和中文参考翻译。
