# 安装与配置 / Install & Setup

> English first, 中文在下方。

## Requirements

- Python 3.9+
- An AgentSkills-compatible host:
  - Claude Code (existing primary runtime)
  - OpenClaw
  - Codex
  - Hermes, with an explicit skills directory if it cannot be auto-detected

## 0. Install into an agent host

The source checkout can stay named `InternetSensorSkill`. The installed skill
directory should be named `trend-aware-content-improver` so it matches
`SKILL.md`.

```bash
# OpenClaw
python3 tools/install_skill.py openclaw --dry-run
python3 tools/install_skill.py openclaw --force

# Codex
python3 tools/install_skill.py codex --dry-run
python3 tools/install_skill.py codex --force

# Claude Code, if you also want to sync this checkout into ~/.claude/skills
python3 tools/install_skill.py claude --force
```

Codex users can invoke it explicitly with `$trend-aware-content-improver`, or by
natural language such as "use the trend-aware content improver to optimize this
Xiaohongshu post". Slash-command availability is host-specific.

Hermes support is conservative because local Hermes skill paths can vary. If
`~/.hermes/skills` exists, the installer uses it. Otherwise pass the path:

```bash
HERMES_SKILLS_DIR="$HOME/.hermes/skills" python3 tools/install_skill.py hermes --force
python3 tools/install_skill.py hermes \
  --dest "$HOME/.hermes/skills/trend-aware-content-improver" \
  --force
```

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `requests` (for retrieval/source fetching), `PyYAML` (to read the
knowledge library), and `pypdf` (to extract text from user-provided paper/PDF
links).

The skill works **fully offline (V1)** with just these. V2 trend retrieval is
optional and only needed if you want live, traction-ranked trend samples.

## 2. Configure accounts

Each account you operate should live under `myaccount/{account_id}/`:

```text
myaccount/{account_id}/
  account_positioning.md
  reference_accounts.md
  para_config.yaml
```

When multiple account folders exist, the skill asks which account to use before
the pipeline starts. Retrieval CLIs accept the same selection through
`--account-dir myaccount/{account_id}`.

Legacy root-level `myaccount/*.md` files are still supported for old installs,
but new setups should use account subfolders.

If `myaccount/` is missing or empty, the skill still runs the full pipeline with
built-in default parameters and without account positioning or priority
reference accounts.

## 3. (Optional) Enable V2 trend retrieval

V2 finds real posts, then ranks them by **traction** (`vibe_score` = weighted
engagement ÷ days since published) so the skill learns from the highest-
performing posts. Some platforms work key-free out of the box:

- Bilibili: native REST provider, no key.
- Weibo: native m.weibo.cn JSON provider, no key.
- Xiaohongshu / Zhihu / Weixin / Douban / Hupu: CDP browser provider, no API key
  but requires explicit user consent before driving the real browser.

Hosted search providers are optional fallbacks for keyed `site:` search. Configure
one only if you want that fallback:

```bash
python3 retrieval/retrieve.py --setup
```

This prompts for hosted-search API keys and stores them at `~/.trend-improver/config.json` with
permission `0600` (owner read/write only). Supported providers:

| Provider | Get a key | Notes |
|----------|-----------|-------|
| Tavily | https://tavily.com | General web search, returns relevance scores |
| Exa | https://exa.ai | Neural search with page contents |
| Firecrawl | https://firecrawl.dev | Search + crawl |
| crawl4ai | `pip install crawl4ai` | Local crawler, URL-driven, no key |

### Env-var alternative

Instead of the config file you can export keys (env vars win over the file):

```bash
export TREND_TAVILY_API_KEY=...
export TREND_EXA_API_KEY=...
export TREND_FIRECRAWL_API_KEY=...
```

### Verify retrieval

```bash
# Key-free native — Bilibili / Weibo
python3 retrieval/retrieve.py --provider auto --topic 完美世界 --platform bilibili
python3 retrieval/retrieve.py --provider auto --topic 热搜 --platform weibo

# CDP platforms first return consent_required unless you add --consent after asking the user
python3 retrieval/retrieve.py --provider auto \
  --topic 校园美食 --platform xiaohongshu \
  --limit 20 --crawl --top 8 --examples-n 5 \
  --output outputs/trends.json

# Keyed fallback — Twitter / LinkedIn or CDP-unavailable platforms
python3 retrieval/retrieve.py --provider auto \
  --topic AI agents --platform twitter \
  --limit 20 --crawl --top 8 \
  --output outputs/trends.json
```

## 4. Run the tests

```bash
python -m compileall retrieval/
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests mock all HTTP — no live API calls, safe for CI.

Optional live contract tests are skipped by default. Run them manually when you
want to validate real upstream contracts:

```bash
TREND_LIVE_BILIBILI=1 python -m unittest tests/test_live_contracts.py -v
TREND_LIVE_CDP=1 TREND_LIVE_CDP_PLATFORM=douban \
  python -m unittest tests/test_live_contracts.py -v
```

## Security note

- Never commit `~/.trend-improver/config.json`, `.env`, or any file with keys.
- The config file is written `0600`. If you ever leak a key, rotate it immediately.

---

# 中文

## 环境要求

- Python 3.9+
- 支持 AgentSkills 的宿主：
  - Claude Code（现有主要运行环境）
  - OpenClaw
  - Codex
  - Hermes（若无法自动识别，需要显式提供 skills 目录）

## 0. 安装到宿主

源码目录可以继续叫 `InternetSensorSkill`。安装到各宿主时，skill 目录应命名为
`trend-aware-content-improver`，以匹配 `SKILL.md` 里的 `name`。

```bash
# OpenClaw
python3 tools/install_skill.py openclaw --dry-run
python3 tools/install_skill.py openclaw --force

# Codex
python3 tools/install_skill.py codex --dry-run
python3 tools/install_skill.py codex --force

# Claude Code，如需同步到 ~/.claude/skills
python3 tools/install_skill.py claude --force
```

Codex 里可以显式说 `$trend-aware-content-improver`，也可以用自然语言触发，例如
“用 trend-aware content improver 优化这条小红书”。是否支持 slash command 取决于宿主。

Hermes 适配采用保守策略：如果本机存在 `~/.hermes/skills`，安装器会使用它；否则需要传入路径：

```bash
HERMES_SKILLS_DIR="$HOME/.hermes/skills" python3 tools/install_skill.py hermes --force
python3 tools/install_skill.py hermes \
  --dest "$HOME/.hermes/skills/trend-aware-content-improver" \
  --force
```

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

会安装 `requests`（检索/来源链接抓取）、`PyYAML`（读知识库）和 `pypdf`（读取用户提供的论文/PDF 链接）。
仅凭这些即可**完全离线（V1）**运行；V2 联网检索是可选项。

## 2. 配置账号

每个要运营的账号放在一个独立目录：

```text
myaccount/{account_id}/
  account_positioning.md
  reference_accounts.md
  para_config.yaml
```

当存在多个账号文件夹时，skill 会在流程开始前询问这次使用哪个账号。检索 CLI 也支持同样的选择：
`--account-dir myaccount/{account_id}`。

旧版根目录 `myaccount/*.md` 仍兼容，但新配置建议使用账号子文件夹。

如果没有设置 `myaccount/`，或目录为空，skill 仍会使用内置默认参数完整跑完流程，只是不启用账号定位和优先参考账号。

## 3.（可选）开启 V2 热点检索

V2 找到真实帖子，再按**传播力**（`vibe_score` = 加权互动量 ÷ 发布天数）排序，
让 skill 从表现最好的帖子里学规律。部分平台开箱即用：

- B站：原生 REST，免 key。
- 微博：m.weibo.cn JSON，免 key。
- 小红书 / 知乎 / 微信公众号 / 豆瓣 / 虎扑：CDP 真实浏览器，免 API key，但必须先征得用户同意。

Tavily / Exa / Firecrawl 是可选的 hosted search 兜底；需要时再配置：

```bash
python3 retrieval/retrieve.py --setup
```

会提示输入 API key，存到 `~/.trend-improver/config.json`（权限 `0600`，仅本人可读写）。
支持 Tavily / Exa / Firecrawl（REST，需 key）和 crawl4ai（本地库，`pip install crawl4ai`，无需 key）。

也可用环境变量代替配置文件（环境变量优先）：

```bash
export TREND_TAVILY_API_KEY=...
export TREND_EXA_API_KEY=...
export TREND_FIRECRAWL_API_KEY=...
```

## 4. 跑测试

```bash
python -m compileall retrieval/
python -m unittest discover -s tests -p 'test_*.py' -v
```

测试全程 mock HTTP，不打真实 API，可安全用于 CI。

## 安全提示

- 切勿提交 `~/.trend-improver/config.json`、`.env` 或任何含密钥的文件。
- 配置文件写入时设为 `0600`。若密钥泄露，立即轮换。
