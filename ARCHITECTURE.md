# 架构 / Architecture

> 网感增强引擎的设计：流水线、职责划分，以及 AgentSkills 宿主间的可移植性契约。
> Design of the Trend-Aware Content Improver: the pipeline, separation of
> concerns, and the portability contract across AgentSkills hosts.

---

## 设计原则 / Design principle

> 网感本质上是一种**动态知识**，而不是固定 Prompt。

因此**推理与数据分离**：

- **推理（reasoning）** 写在 `prompts/` 的 Markdown 里，由 agent（Claude）执行 —— 运行时无关。
- **联网（network）** 写在 `retrieval/` 的 Python CLI 里，通过 shell 调用 —— 任何 agent 运行时都能 shell out。
- **知识（knowledge）** 写在 `knowledge/` 的 YAML 里，是可热插拔的「平台 / 主题」规则库。

这样新增能力大多是**加数据文件**，而不是改代码。

---

## 流水线 / Pipeline

```text
用户内容 + 平台
      │
      ▼
[0] 账号选择 Account Context   ← myaccount/{account_id}/ 三件套
      │   account_positioning / reference_accounts / para_config
      ▼
[1] 主题识别 Topic Detection   ← prompts/detect_topic.md + knowledge/topics/*.yaml
      │   topic / topic_display
      ▼
[2] 热点检索 Trend Retrieval   ← retrieval/retrieve.py（V2，可选，失败回退 V1）
      │   outputs/trends.json（按 vibe_score 降序的真实爆款样本）
      ▼
[3] 规律抽取 Pattern Extraction ← prompts/extract_patterns.md
      │   标题/情绪/结构规律（source: trend_corpus | knowledge_base）
      ▼
[4] 网感评分 Vibe Critic       ← prompts/critique_content.md + knowledge/platforms/*.yaml
      │   7 维度评分 + vibe_index(0-100) + 问题清单
      ▼
[5] 内容优化 Rewrite           ← prompts/improve_content.md
      │   优化版本 + 改动说明
      ▼
[6] 呈现 Present               ← SKILL.md：原始 vs 优化 网感指数
```

每步把结构化结果交给下一步；中间产物（如 `trends.json`）落在 `outputs/`。
若 `myaccount/` 下存在多个账号文件夹，`SKILL.md` 先询问本次使用哪个 `account_id`；
之后所有账号定位、参考账号和参数配置都来自选中的 `myaccount/{account_id}/`。
若没有任何账号配置，流程降级为 `selected_account_id = none`：账号定位和参考账号不可用，
参数使用代码默认值，主 pipeline 仍完整执行。

---

## 两个「网感分数」的区别 / Two vibe scores, don't conflate

| 名称 | 在哪 | 算什么 | 谁算 |
|------|------|--------|------|
| `vibe_score` | `outputs/trends.json` 每条结果 | **检索到的真实帖子**的传播力（加权互动量 ÷ 发布天数，log 归一 0-100） | `retrieval/engagement.py`（代码） |
| `vibe_index` | Step 4 诊断输出 | **用户自己内容**的质量（7 维度综合 0-100） | `prompts/critique_content.md`（Claude） |

`vibe_score` 用来**挑选值得学习的样本**；`vibe_index` 用来**诊断和量化优化效果**。

---

## 传播力评分 / Traction scoring（retrieval/engagement.py）

挑「值得学」的样本，靠的是真实传播力而非搜索相关性：

```text
weighted_engagement = 1·likes + 2·comments + 3·saves + 4·shares + 0.01·views
vibe_score = 100 · log10(weighted_engagement / days + 1) / log10(BASELINE + 1)
```

- 收藏、分享权重更高 —— 它们更能代表「收藏价值」和「传播力」。
- 播放/浏览是低权重触达信号 —— 对 B站、虎扑等平台有帮助，但不会压过主动互动。
- 除以发布天数 —— 新帖的高互动比老帖更说明当下趋势。
- log 归一 —— 避免头部爆款碾压一切，压到可比的 0-100。
- 抓不到互动量的样本 `vibe_score = null`，排序时沉底。

**互动量来源（优先级）**：

1. **provider 自带结构化指标（首选）** —— B站/微博原生接口、CDP 平台提取器（小红书点赞、
   知乎赞同/评论、豆瓣评价量、虎扑亮/回复/浏览）直接返回 `engagement`。
   `enrich_result` 检测到已有指标就**直接采用、不覆盖**。
2. **页面文本兜底** —— 仅当结果没带任何指标时，才用 `EXTRACTORS` 注册表从标题/摘要/
   抓取的页面文本里正则提取（`extract_<platform>`，未注册的走 `extract_generic`）。

这样既用上真实平台的精确数字，又对纯文本来源（如通用搜索结果）保持兜底；
取最高 `vibe_score` 的几条经 `--save-examples` 落到 `outputs/reference_examples.json`，供重写时参考。

---

## 浏览器检索的同意闸门 / Consent gate for browser retrieval

CDP 平台（小红书/知乎/微信公众号/豆瓣/虎扑）检索会驱动**用户本机真实浏览器**，可能用到登录态、
存在账号风险。因此设了一道硬闸门，**绝不静默碰浏览器**：

```text
auto 选到 native: cdp
   │
   ▼
cdp_platforms.search(consent=?)
   ├─ consent=False → raise ConsentRequired（在导航浏览器之前）
   │      └─ retrieve.py 捕获 → 写 mode:"consent_required" 信封（exit 0）
   │            └─ SKILL.md 据此询问用户：
   │                  同意 → 重试带 --consent；若 login_required 提示先登录
   │                  拒绝 → 回退 V1 规则库改写（不联网、不碰浏览器）
   └─ consent=True → 驱动浏览器检索 → 真实结果 + vibe_score 排序
```

- 同意是**用户的决定**：`auto` 路径捕获到 `ConsentRequired` 会**原样抛出**，
  不会偷偷 fall through 到 keyed 搜索。
- B站原生源不碰浏览器，**无需同意**；通用搜索（tavily 等）也不碰浏览器，无需同意。
- 三种状态信号：`consent_required`（还没同意）/ `login_required`（同意了但没登录该平台）/
  `offline`（没 key、检索失败、或用户拒绝 → 回退 V1）。

---

## 可移植性契约 / Portability contract（Claude Code / OpenClaw / Codex / Hermes）

目标：源码目录可以继续叫 `InternetSensorSkill`，安装时复制到各宿主的
`trend-aware-content-improver` 目录，并保持同一套 prompt / Python CLI 可复用。约束：

1. **推理零代码绑定**。所有推理在 `prompts/*.md`，不依赖任何 Claude 专属 API。
   换运行时 = 换一个会读 Markdown 指令的 agent。
2. **工具是标准 CLI**。`retrieval/*.py` 是独立 argparse 程序（`python3 retrieval/retrieve.py ...`），
   通过 Bash 调用。OpenClaw / Codex / Hermes 只要能 shell out，就能复用。
3. **路径可配置**。`SKILL.md` 使用 `${SKILL_DIR}` 指代安装后的 skill 根目录；Claude Code 可映射
   `${CLAUDE_SKILL_DIR}`，其他宿主用安装路径替换。安装器会把源码复制到宿主目录下的
   `trend-aware-content-improver/`。账号配置通过 `myaccount/{account_id}/` 选择；Python CLI
   通过 `--account-dir myaccount/{account_id}` 接收同一个选择。
4. **凭证在运行时之外**。API key 来自环境变量或 `~/.trend-improver/config.json`（`0600`），
   不进仓库、不绑定某个 agent。
5. **优雅降级**。检索失败 / 未配置 key / 库缺失 → 一律以 0 退出并标记 `mode: offline`，
   让上层无脑回退 V1，而不是崩在半路。

照此，迁移到 OpenClaw / Codex 基本只是**复制到宿主 skills 目录 + 用对应宿主触发这个 skill**，
`prompts/`、`knowledge/`、`retrieval/` 原样复用。Hermes 当前使用显式 skills 目录做保守适配。

---

## 按平台检索 / Per-platform retrieval

「在哪个平台发笔记，就检索哪个平台的爆款」由 `retrieval/strategy.py` 的注册表驱动，
`retrieve.py --provider auto` 据此选路：

```text
平台 platform
   │
   ▼
strategy.get_strategy(platform)
   │
  ├─ native 有原生免密钥源？（如 bilibili / weibo）
   │     └─ 是 → NATIVE_PROVIDERS[native].search(subject)   # 真实结构化互动量，免 key
   │
   └─ 否 → 通用搜索 provider（tavily/exa/firecrawl，需 key）
           query = build_targeted_query(subject, platform)   # 追加 site: 定向 + 平台惯用后缀
           例：完美世界 → "校园美食 爆款 热门 高赞 (site:xiaohongshu.com OR site:xhslink.com)"
```

- **native（最强）**：直接搜该平台并返回真实播放/点赞/评论/转发。B站与微博已接入。
- **site: 定向**：通用搜索源被约束在该平台域名内，确保学到的是「该平台的爆款」而非开放网。
- 任一路径产出后，`engagement.enrich_result` 优先采用 provider 已带的结构化互动量，
  没有才回退抓页面文本提取；再按 `vibe_score` 排序。

---

## 扩展点 / Extension points

| 想做什么 | 改哪里 | 要不要写代码 |
|----------|--------|:-----------:|
| 加一个平台规则 | `knowledge/platforms/<p>.yaml` | 否 |
| 加一个主题框架 | `knowledge/topics/<t>.yaml` | 否 |
| 调整某步推理 | `prompts/<step>.md` | 否 |
| 给平台加检索定向（site:/后缀） | `retrieval/strategy.py` 的 `STRATEGIES` | 否（纯配置） |
| 加一个通用搜索 provider | `retrieval/<provider>.py` + 注册 `REST_PROVIDERS` | 是 |
| 加一个平台原生检索源 | 仿 `retrieval/bilibili.py` 写 `search()` + 注册 `NATIVE_PROVIDERS` | 是 |
| 加平台专属互动量提取（抓页面用） | `retrieval/engagement.py` 的 `EXTRACTORS` | 是 |
| 调整传播力公式 | `retrieval/engagement.py` 的权重 / BASELINE | 是 |
