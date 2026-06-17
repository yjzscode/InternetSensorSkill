---
name: trend-aware-content-improver
description: "Diagnose why content lacks vibe and rewrite it using account positioning, priority reference accounts, and current platform trends. Also supports a learning-report mode for reference-account learning reports. | 结合账号定位、优先模仿账号和当前平台热点趋势诊断并优化内容；支持 learning-report 模式生成竞品账号学习报告。"
allowed-tools: Read Write Edit Bash
metadata:
  compatibility: "AgentSkills-compatible hosts with Python 3.9+ and shell access; installable for Claude Code, OpenClaw, Codex, and path-configurable Hermes."
  argument-hint: "[platform] [content]"
  version: "1.0.0"
  user-invocable: true
---

> **Language / 语言**: This skill supports both English and Chinese. Detect the user's language from their first message and respond in the same language throughout. 本 Skill 支持中英文，按用户语言全程回复。

# 网感增强引擎 / Trend-Aware Content Improver（AgentSkills 版）

把一段内容诊断为「为什么没有网感」，再结合账号定位、优先模仿账号与目标平台的当前趋势重写它。
不是「帮你写内容」，而是「帮你诊断内容为什么没有网感，并根据账号定位与当前趋势优化」。
也可以用 `/trend-aware-content-improver learning-report` 或“生成参考账号学习报告 / 竞品账号学习报告”
周期性总结 `myaccount/{account_id}/reference_accounts.md` 中参考账号的近期高表现内容。

---

## 触发条件 / Trigger

当用户出现以下意图时启动：
- `/trend-aware-content-improver`
- "帮我优化一下这条小红书 / 推文 / 帖子"
- "这段文案没有网感，帮我改改"
- "improve this post for {platform}"
- 给出「平台 + 一段内容」，希望提升传播力 / 收藏价值
- `/trend-aware-content-improver learning-report`
- "生成参考账号学习报告 / 竞品账号学习报告"

需要的输入：
1. **平台**（bilibili / xiaohongshu / zhihu / weixin / weibo / douban /
   hupu / twitter / linkedin）
2. **内容**（一段待优化的文字）

若用户没说平台，先问一句平台是哪个，再开始。
若用户触发 `/trend-aware-content-improver learning-report` 或自然语言学习报告意图，需要平台；可选参数是每个账号抓取的内容数 `n`。

---

## 工具使用规则 / Tool usage

本 Skill 可运行在支持 `SKILL.md` 的 AgentSkills 宿主中。推理由 `prompts/` 下的 Markdown 驱动（由你执行），
联网检索由 `retrieval/` 下的 Python CLI 完成。

下文用 `${SKILL_DIR}` 指代安装后的 skill 根目录。Claude Code 可用 `${CLAUDE_SKILL_DIR}` 映射；
OpenClaw / Codex / Hermes 若没有自动设置该变量，就把 `${SKILL_DIR}` 替换为安装目录的绝对路径。
源码仓库目录可以继续叫 `InternetSensorSkill`，但安装到宿主时目录名应为 `trend-aware-content-improver`。

| 任务 Task | 工具 Tool |
|-----------|-----------|
| 读取平台规则库 Read platform rules | `Read` → `${SKILL_DIR}/knowledge/platforms/{platform}.yaml` |
| 读取主题框架 Read topic framing | `Read` → `${SKILL_DIR}/knowledge/topics/{topic}.yaml` |
| 枚举账号配置 Discover account profiles | `Read/Bash` → `${SKILL_DIR}/myaccount/*/` |
| 读取账号定位 Read account positioning | `Read` → `${selected_account_dir}/account_positioning.md` |
| 读取模仿账号 Read reference accounts | `Read` → `${selected_account_dir}/reference_accounts.md` |
| 读取参数配置 Read parameter config | `Read` → `${selected_account_dir}/para_config.yaml` |
| 读取推理 Prompt Read reasoning prompt | `Read` → `${SKILL_DIR}/prompts/*.md` |
| 用户来源链接抓取 Source link extraction | `Bash` → `python3 ${SKILL_DIR}/retrieval/source_links.py ...` |
| 热点检索（V2）Trend retrieval | `Bash` → `python3 ${SKILL_DIR}/retrieval/retrieve.py ...` |
| 账号参考样本/学习报告抓取 Account sample / learning report collection | `Bash` → `python3 ${SKILL_DIR}/retrieval/learning_report.py ...` |
| 检索首次配置 Retrieval setup | `Bash` → `python3 ${SKILL_DIR}/retrieval/retrieve.py --setup` |
| 写出中间结果 Write intermediate results | `Write` → `${SKILL_DIR}/outputs/{platform}/{specific_topic}/...` |

**基础目录 / Base directory**：默认相对安装后的 skill 根目录（`./outputs/`、`./knowledge/`）。
OpenClaw 默认安装到 `~/.openclaw/workspace/skills/trend-aware-content-improver/`；
Codex 默认安装到 `${CODEX_HOME:-~/.codex}/skills/trend-aware-content-improver/`；
Hermes 若无法自动识别目录，按 `INSTALL.md` 显式传入 skills 目录。检索 `--output` 指向该目录下的 `outputs/`。

---

## 主流程 / Pipeline

先执行账号配置读取，再按顺序执行八步。每步读取对应 prompt 作为推理指引，把结构化结果传给下一步。

### Step 0：账号配置读取 / Account Context

- 先扫描 `${SKILL_DIR}/myaccount/` 下的一级子文件夹。凡是包含 `account_positioning.md`、`reference_accounts.md` 或 `para_config.yaml` 任一文件的子文件夹，都视为一个可选账号配置，`account_id` 等于文件夹名，例如 `xiaohongshu_FromMath2Mad_example`。
- 若只有一个账号配置，直接选择它，设：
  - `selected_account_dir = ${SKILL_DIR}/myaccount/{account_id}`
  - `selected_account_id = {account_id}`
- 若有多个账号配置，且用户没有明确指定账号，必须先询问“这次要用哪个账号做？”，列出 `account_id` 和可从定位文件第一行/一句话定位中提炼出的简短说明。用户选择后再继续。
- 若没有子文件夹账号配置，但旧版根目录文件 `${SKILL_DIR}/myaccount/account_positioning.md`、`${SKILL_DIR}/myaccount/reference_accounts.md` 或 `${SKILL_DIR}/myaccount/para_config.yaml` 存在，则兼容旧结构：
  - `selected_account_dir = ${SKILL_DIR}/myaccount`
  - `selected_account_id = legacy`
- 若 `${SKILL_DIR}/myaccount/` 不存在，或既没有账号子文件夹也没有旧版根目录配置，则不要询问用户、不要中断流程，直接设：
  - `selected_account_dir = ${SKILL_DIR}/myaccount`（该目录可以不存在）
  - `selected_account_id = none`
  - `account_positioning: unavailable`
  - `reference_accounts: unavailable`
  - `para_config = code_defaults`
- 后续所有账号相关读取和命令都使用 `selected_account_dir`；不要混用其他账号文件夹。
- 读取 `${selected_account_dir}/account_positioning.md`；若文件不存在，标记为 `account_positioning: unavailable`，继续流程。
- 若文件已经填写，把它提炼成 `account_positioning`：目标人群、领域边界、风格语气、价值主张、内容形式偏好、硬约束。
- 若文件仍是空模板或信息不足，标记为 `account_positioning: unavailable`，不要中断流程，也不要强行追问。
- 读取 `${selected_account_dir}/reference_accounts.md`；若文件不存在，标记为 `reference_accounts: unavailable`，继续流程。
- 若文件里有与目标平台匹配、且带 `homepage_url` 的账号，提炼成 `reference_accounts`；否则标记为 `reference_accounts: unavailable`。
- 读取 `${selected_account_dir}/para_config.yaml`，作为 `para_config`；若文件缺失或字段为空，使用代码内置默认值。
- 从 `para_config.output.files` 读取输出文件名，组成 `output_files`；若字段缺失，默认使用 `testcase.md`、`trends.json`、`reference_examples.json`、`account_reference_examples.json`、`critique.json`、`rewrite.md`、`source_links.json`、`account_consistency.json`、`risk_audit.json`、`learning_raw.json`、`learning_report.md`。
- 后续热点样本只用于学习表达策略；若爆款套路与账号定位冲突，以账号定位为准。

### Step 1：主题识别 / Topic Detection

- 读取 `${SKILL_DIR}/prompts/detect_topic.md`
- 对照 `${SKILL_DIR}/knowledge/topics/*.yaml` 的 `topic` 与 `aliases`
- 输出 `topic` / `topic_display` / `confidence`
- 生成本次运行目录：
  - `specific_topic` 必须是 `timestamp-topic` 格式，例如 `20260615-173012-anime-perfect-world`。
  - `timestamp` 用本机当前时间 `YYYYMMDD-HHMMSS`。
  - `specific_topic_label` 由 agent 根据原文自行抽取为简短 kebab-case slug；优先用英文/拼音安全字符，避免空格和路径特殊字符。
  - `output_dir = ${SKILL_DIR}/outputs/{platform}/{specific_topic}`，先创建该目录。
- 保存输入到 `${output_dir}/${output_files.testcase}`，文件形状参考 `outputs/xiaohongshu/testcase.md`：平台、主题、原始标题/正文/图片或其他素材路径。

### Step 1.5：用户来源链接读取 / Source Link Grounding

如果用户原文里包含 URL、论文 PDF、网页、项目页等来源链接，先读取这些链接，作为后续改写的**事实依据**。
这一步不同于 Step 2 的爆款检索：来源链接回答“这条内容真实在说什么”，爆款检索只回答“平台上怎么表达更有网感”。

```bash
python3 ${SKILL_DIR}/retrieval/source_links.py \
  --content-file "${output_dir}/${output_files.testcase}" \
  --output "${output_dir}/${output_files.source_links}" \
  --max-urls "{para_config.source_links.max_urls}" \
  --max-chars "{para_config.source_links.max_chars_per_source}" \
  --timeout "{para_config.source_links.timeout_seconds}"
```

- 若 `${output_dir}/${output_files.source_links}` 中有 `status: ok` 的来源，后续 Step 4/5/7 必须优先使用这些来源里的标题、摘要、方法、结论、数据和限制。
- 若用户给了 URL 但抓取失败，必须在最终结果里说明“链接未能读取/抽取”，不要假装读过链接。
- 若 `para_config.source_links.require_source_grounding_for_urls: true`，且用户给了 URL 但没有任何 `status: ok` 的来源，不要根据链接内容编造细节；只能基于原文保守改写，并把链接读取失败列入风险审查。
- 用 `Read` 读 `${output_dir}/${output_files.source_links}`，把它作为 `source_links` 传给后续 prompts。

### Step 2：热点检索 / Trend Retrieval（V2，可选）

按**目标平台**检索该平台的爆款笔记，用真实传播数据排序，挑出网感指数最高的几条供 Step 3/5 学习与参考改写。
热点样本主要用于学习“选题、钩子、结构、平台当下表达”，不代表账号定位或人设。
若 `reference_accounts` 可用，先搜索或抓取这些账号的相关内容；样本不足时再回退到普通爆款检索。

平台分两类，检索方式不同：

- **B站 bilibili**：原生免密钥接口，直接拿真实互动量 —— 无需登录、无需确认，直接检索。
- **小红书 / 知乎 / 微信公众号 / 豆瓣 / 虎扑 / 微博**：内容常被 JS 渲染或反爬挡住（微博的 m.weibo.cn 服务端请求现已被新浪反爬墙拦截，返回 432），需要驱动**用户本机真实浏览器**（CDP）去搜。
  这会用到用户的登录态、存在账号风险，**因此必须先征得用户同意**。
- **Twitter / LinkedIn 等**：无原生接口，走**免密钥**的 SearXNG / DuckDuckGo 检索 + `site:` 定向。
  若设了 `TREND_SEARXNG_URL`（自建 SearXNG 实例）走其 JSON 接口，无需浏览器；否则回退到「用真实浏览器跑 DuckDuckGo」，**这一回退同样需要用户同意**。

#### 2a. 判断是否需要征求同意

先看该平台的检索方式（可查 `retrieval/strategy.py` 的 `native`）：
- `native: bilibili` → **不需要确认**，直接执行 2c。
- `native: cdp`（小红书/知乎/微信公众号/豆瓣/虎扑/微博）→ 走 2b 的**同意流程**。
- `native: searxng`（Twitter/LinkedIn）→ 若已设 `TREND_SEARXNG_URL` 用自建实例，**无需确认**；
  否则走 DuckDuckGo 浏览器回退，需走 2b 的**同意流程**。

也可以先跑一次（不带 `--consent`）探测：CDP 平台（含微博）与未配置实例的 Twitter/LinkedIn
会返回 `mode: "consent_required"`，这是在告诉你「需要先问用户」，**绝不要**自作主张加 `--consent`。

```bash
python3 ${SKILL_DIR}/retrieval/retrieve.py \
  --account-dir "${selected_account_dir}" \
  --topic "{topic_display}" --platform "{platform}" \
  --output "${output_dir}/${output_files.trends}"
```

#### 2b. 征求同意（仅 CDP 平台）

当检索方式是 CDP，**先明确询问用户**，例如：

```
要检索「{platform}」上的真实爆款笔记，我需要驱动你本机已登录的浏览器去搜索。
这会用到你的登录态，存在一定账号风险（自动化可能被平台检测）。
是否同意？
  • 同意 → 我会打开浏览器检索真实爆款，按真实传播数据排序后参考改写
  • 不同意 → 我会回退到 V1 规则库来改写（不联网、不碰浏览器）
```

- **用户同意** → 进入 2c，命令加上 `--consent`。
  - 检索结果若返回 `login_required: true`，说明浏览器**未登录该平台**：
    提示用户「请先在浏览器登录 {platform}，登录后告诉我，我再检索」，登录后重试。
- **用户拒绝** → **不要**加 `--consent`，直接告诉用户「好的，我将使用 V1 规则库来改写」，
  跳过检索，Step 3 完全基于知识库。

#### 2c. 执行检索

若 Step 0 有 `reference_accounts`：

1. 优先使用与目标平台匹配的账号 URL。
2. 对账号主页 URL，先用账号名/handle + `topic_display` 搜索该账号相关内容；对具体帖子/文章 URL，可尝试直接抓取。
3. CDP / DuckDuckGo 浏览器回退仍然沿用 2b 的同意流程；不要因为账号在白名单里就跳过同意。
4. 如果优先账号检索拿到的可用样本少于 `--examples-n`，再执行普通爆款检索补足。
5. 合并结果时按 URL 去重，优先保留模仿账号样本，并在 `trends.json` / `reference_examples.json` 中保留 `account`、`author`、`url`、`vibe_score`、`engagement`、`snippet` 等字段；若互动量不可得，`ranked_by` 标注为 `reference_account_priority` 或 `relevance (no engagement on listing)`。

```bash
python3 ${SKILL_DIR}/retrieval/retrieve.py \
  --account-dir "${selected_account_dir}" \
  --topic "{topic_display}" \
  --platform "{platform}" \
  --consent \   # ← 仅当用户已同意（CDP 平台）；B站/通用搜索可省略
  --output "${output_dir}/${output_files.trends}" \
  --save-examples "${output_dir}/${output_files.reference_examples}"
```

- **平台定向**：检索只在目标平台内进行，「在哪个平台发，就学哪个平台的爆款」。
- **传播力排序**：每条结果带 `vibe_score`，公式和权重由 `${selected_account_dir}/para_config.yaml` 的 `real_vibe_score` 控制，默认是「加权互动量 ÷ 发布天数」后 log 归一到 0-100。
- `--save-examples` 把网感指数最高的几条单独存到 `${output_dir}/reference_examples.json`，
  作为 Step 5 重写时的**热点参考样本**（学它们的标题钩子、结构、表达）。
- `reference_examples.json` 中的样本统一视为 `reference_role: trend_hotspot`；若文件里没有显式字段，rewrite 时也按热点样本处理，不要把这些作者当作账号人设来源。
- `${selected_account_dir}/para_config.yaml` 控制 provider、检索数量、是否 crawl、排序、`top`、`examples_n`、参考账号启用与补足阈值等参数；命令行显式传入的参数优先级更高。
- 用 `Read` 读 `${output_dir}/${output_files.trends}` 与 `${output_dir}/${output_files.reference_examples}`。

#### 检索结果的几种状态

| `mode` / 字段 | 含义 | 你该怎么做 |
|---------------|------|-----------|
| `online` + 有 results | 检索成功 | 用真实爆款样本，进入 Step 3 |
| `consent_required: true` | CDP 平台、还没同意 | 回到 2b 问用户 |
| `login_required: true` | 同意了，但浏览器没登录该平台 | 提示登录后重试 |
| `offline` / results 为空 | 没 key / 检索失败 / 用户拒绝 | 进入 V1（仅知识库），**不要报错** |

> 区分两个分数：`trends.json` / `reference_examples.json` 里每条结果的 `vibe_score`
> 是**真实帖子的传播力**（用来挑样本）；Step 4 的 `vibe_index` 是对**用户内容**的质量诊断（由你打分）。

### Step 2.5：账号风格参考样本 / Account Style Reference Samples

如果 `${selected_account_dir}/reference_accounts.md` 有与目标平台匹配的参考账号，额外抓取这些账号自己的近期/代表内容，作为“账号人设与表达风格”的参考。
这些内容可以和本次主题相对无关；它们的作用不是学选题热度，而是帮助 rewrite 保持账号定位、语气、节奏和人设一致。

若目标平台需要 CDP 或 DuckDuckGo 浏览器回退，沿用 Step 2b 的同意规则；没有用户同意时不要加 `--consent`。

```bash
python3 ${SKILL_DIR}/retrieval/learning_report.py \
  --account-dir "${selected_account_dir}" \
  --platform "{platform}" \
  --purpose account_reference_examples \
  --items-per-account "{para_config.account_reference_samples.items_per_account}" \
  --limit-per-account "{para_config.account_reference_samples.limit_per_account}" \
  --output-dir "${output_dir}" \
  --consent   # 仅当用户已同意浏览器检索时添加
```

- 默认每个参考账号抓取 `3` 条，可通过 `para_config.account_reference_samples.items_per_account` 修改。
- 输出 `${output_dir}/${output_files.account_reference_examples}`。
- 每条样本必须标明 `source_type: account_reference` 和 `reference_role: account_style`，并保留 `source_account`、`source_account_url`、`account`、`author`、`url`、`title`、`snippet`、`vibe_score`。
- 若某账号返回 `no_account_matched_results`，不要把低置信度候选当作账号样本；在后续改写说明里写明该账号样本不足。
- 用 `Read` 读 `${output_dir}/${output_files.account_reference_examples}`，把它作为 `account_reference_examples` 传给 Step 5/6。

### Step 3：规律抽取 / Pattern Extraction

- 读取 `${SKILL_DIR}/prompts/extract_patterns.md`
- 数据源：有 `${output_dir}/${output_files.trends}`（online）则以真实语料为主、知识库为辅；否则**完全用知识库**
  （`knowledge/platforms/{platform}.yaml` + `knowledge/topics/{topic}.yaml`）
- 若 Step 0 有 `account_positioning`，过滤或标注与账号目标人群、领域边界、风格语气冲突的爆款规律。
- 输出标题规律 / 情绪规律 / 内容结构规律，并标注 `source`

### Step 4：网感评分 / Vibe Critique

- 读取 `${SKILL_DIR}/prompts/critique_content.md`
- 对原始内容打 7 个维度分（hook_strength / novelty / authenticity / shareability /
  saveability / platform_fit / ai_smell），计算 **网感指数（0-100）**
- 若 Step 0 有 `account_positioning`，`platform_fit` 同时检查「平台契合 + 账号定位契合」；定位偏离必须写进 problems。
- 若 Step 1.5 有 `source_links`，指出原文里哪些事实钩子可以从来源里加强，哪些事实不能仅凭原文或链接失败来扩写。
- 输出具体问题清单（指出哪句、哪里、为什么扣分），并保存到 `${output_dir}/${output_files.critique}`。

### Step 5：内容优化 / Rewrite

- 读取 `${SKILL_DIR}/prompts/improve_content.md`
- 综合 {原始内容 + 用户来源链接 + 平台规则 + 抽取规律 + 诊断问题 + 热点参考样本 + 账号风格参考样本} 重写
- 若 Step 0 有 `account_positioning`，重写必须优先符合账号定位；热点规律只能作为表达参考，不能改变目标人群、领域边界、风格语气或硬约束。
- **用户来源链接优先**：若 `${output_dir}/${output_files.source_links}` 有可读来源，必须基于来源里的真实信息补强文案；不要只根据原文猜测论文/网页内容。
- **热点参考样本**：若有 `${output_dir}/${output_files.reference_examples}`，把高 `vibe_score` 的帖子作为 `trend_hotspot`，只学标题钩子、结构和平台表达方式；不要学习其账号人设、立场或事实。
- **账号风格参考样本**：若有 `${output_dir}/${output_files.account_reference_examples}`，把这些样本作为 `account_style`，优先学习目标账号想模仿的语气、节奏、人设边界和表达习惯；不要照抄原句、经历、事实或图片。
- 若热点样本和账号风格样本冲突，按优先级处理：用户来源事实 > 账号定位 > 账号风格样本 > 热点网感技巧。
- 逐条回应 Step 4 的 problems；遵守平台 `dos`，规避 `donts` 与 `ai_smell_signals`
- **不要虚构事实**（价格、菜名等）；缺失处用占位提示作者补充
- 保存改写结果到 `${output_dir}/${output_files.rewrite}`，文件形状参考 `outputs/xiaohongshu/rewrite.md`。

### Step 6：改写后账号一致性评分 / Account Consistency After Rewrite

- 读取 `${SKILL_DIR}/prompts/account_consistency.md`
- 只评价 Step 5 的**改写后内容**，不要评价改写前原文。
- 若 Step 0 有 `account_positioning`，按 `para_config.account_consistency` 的维度、权重、惩罚和 caps 严格计算 `account_consistency_score`。
- 若 Step 2.5 有 `account_reference_examples`，用它辅助判断 `reference_account_alignment`：是否学到了账号风格，但没有过度模仿。
- 若 `account_positioning` 不可用，仍输出低置信度评估，并提示“缺少账号定位，分数仅供参考”。
- 保存到 `${output_dir}/${output_files.account_consistency}`。

### Step 7：发布前风险审查 / Final Risk Audit

- 读取 `${SKILL_DIR}/prompts/final_risk_audit.md`
- 对比原文与改写后内容，检查是否加入原文没提供的数据、经历、价格、排名、医学/法律/投资判断等。
- 若 Step 1.5 有 `source_links`，把 `must_confirm_facts` 分成 `supported_by_source_links` 与 `needs_user_confirmation`；来源中可支持的事实不用要求用户再次确认，但要保留出处 URL。
- 输出 `must_confirm_facts`：必须由用户确认的事实列表。
- 结合 `knowledge/platforms/{platform}.yaml` 与 `para_config.risk_audit` 做平台敏感/发布风险提醒；不做法律判断。
- 重点提示医疗、金融、夸大功效、搬运/洗稿、引战、未授权图片等基础风险。
- 保存到 `${output_dir}/${output_files.risk_audit}`。

### Step 8：呈现结果 / Present

向用户展示：

```text
原始网感指数：52
优化后网感指数：88
改写后账号一致性：82
发布风险：medium（有 2 个事实需确认）
```

- 7 维度评分小结
- 改写后账号一致性评分与主要扣分原因
- 必须用户确认的事实列表
- 已使用的用户来源链接，以及链接读取失败说明（如有）
- 平台敏感/发布风险提示
- 优化版本（符合目标平台结构与格式）
- 改动说明（标题 / 细节 / 结构 / 账号定位 / 降 AI 味）
- 如有占位，明确提醒作者补充真实信息

---

## 竞品账号学习报告 / Reference Account Learning Report

当用户触发 `/trend-aware-content-improver learning-report` 或“生成参考账号学习报告 / 竞品账号学习报告”时，执行这个独立流程，不进入主改写 pipeline。

### Learning Step 0：读取配置

- 按主流程 Step 0 的账号选择规则，先确定 `selected_account_dir`。若有多个账号配置且用户没指定，先询问使用哪个账号生成学习报告。
- 读取 `${selected_account_dir}/account_positioning.md`。
- 读取 `${selected_account_dir}/reference_accounts.md`。
- 读取 `${selected_account_dir}/para_config.yaml`。
- 若 `reference_accounts.md` 没有目标平台的有效账号 URL，先提示用户补充，不要编造账号。
- 若用户没给平台，先问一句平台是哪个；若没给 `n`，使用 `para_config.learning_report.items_per_account`。

### Learning Step 1：创建输出目录

- `specific_topic_label = learning-report`
- `specific_topic = timestamp-learning-report`
- `output_dir = ${SKILL_DIR}/outputs/{platform}/{specific_topic}`
- `timestamp` 使用 `para_config.output.timestamp_format`，默认 `YYYYMMDD-HHMMSS`。

### Learning Step 2：抓取参考账号近期内容

若目标平台需要 CDP 或 DuckDuckGo 浏览器回退，沿用主流程 Step 2b 的同意规则；没有用户同意时不要加 `--consent`。

```bash
python3 ${SKILL_DIR}/retrieval/learning_report.py \
  --account-dir "${selected_account_dir}" \
  --platform "{platform}" \
  --items-per-account "{n}" \
  --output-dir "${output_dir}" \
  --consent   # 仅当用户已同意浏览器检索时添加
```

- 脚本会读取 `${selected_account_dir}/reference_accounts.md`，逐账号检索真实内容。
- 结果按真实 `vibe_score` 排序；公式由 `para_config.real_vibe_score` 控制。
- 输出 `${output_dir}/${output_files.learning_raw}`，包含账号、标题、URL、作者、互动量、发布时间、`vibe_score` 与账号匹配置信度。
- 若某账号返回 `no_account_matched_results`，在报告中如实说明，不要把非该账号内容当成样本。

### Learning Step 3：生成报告

- 读取 `${SKILL_DIR}/prompts/learning_report.md`。
- 读取 `${output_dir}/${output_files.learning_raw}`。
- 结合 `account_positioning` 判断“适合学什么 / 不适合学什么”。
- 保存报告到 `${output_dir}/${output_files.learning_report}`。

### Learning Step 4：呈现报告摘要

向用户展示：

- 抓取账号数、内容数、最高 `vibe_score`
- 最近高赞选题
- 常用标题句式
- 内容结构
- 评论区/用户需求（没有真实评论时标注为推断）
- 适合本账号学习与不适合学习
- 下周可试选题

---

## V1 / V2 说明

- **V1（始终可用，离线）**：账号定位 + 平台规则库 + 主题框架 + Prompt 工程，不联网也能完整跑完主流程。
- **V2（可选，联网）**：Step 2 接入真实热点语料，让规律抽取基于「当下正在传播什么」。
  未配置 key 时无缝降级为 V1。

---

## 支持平台 / Supported platforms

V1 规则库：哔哩哔哩 bilibili、小红书 xiaohongshu、知乎 zhihu、微信公众号 weixin、
微博 weibo、豆瓣 douban、虎扑 hupu、Twitter/X twitter、LinkedIn linkedin。
V2 检索：B站走原生免密钥接口；小红书/知乎/微信公众号/豆瓣/虎扑/微博走 CDP 真实浏览器；
Twitter/LinkedIn 走免密钥的 SearXNG / DuckDuckGo + `site:` 定向（设 `TREND_SEARXNG_URL`
用自建实例则免浏览器，否则走 DuckDuckGo 浏览器回退）。

扩展：新增平台规则 = 加一份 `knowledge/platforms/*.yaml`；新增检索定向 = 在
`retrieval/strategy.py` 注册；新增平台原生源 = 仿 `retrieval/bilibili.py` 接入 `NATIVE_PROVIDERS`。
