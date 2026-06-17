# Prompt: Pattern Extraction / 传播规律抽取

> 本 Prompt 由 Claude 执行（非代码）。目标：抽取当前主题在目标平台上的传播规律。
> Executed by Claude (not code). Goal: extract the propagation patterns for this
> topic on the target platform.

## 输入 / Input

- `topic` / `topic_display`：来自 detect_topic
- `platform`：目标平台
- `para_config`：来自 `selected_account_dir/para_config.yaml`
- `output_files`：来自 `para_config.output.files`
- **趋势语料（V2，可选）**：`outputs/{platform}/{specific_topic}/{output_files.trends}`，由 `retrieval/retrieve.py` 生成
- **本次运行目录**：`outputs/{platform}/{specific_topic}/`
- **知识库（V1，始终可用）**：
  - `knowledge/platforms/{platform}.yaml`
  - `knowledge/topics/{topic}.yaml`（若 topic 为 general 则跳过）
- **账号定位（可选）**：`selected_account_dir/account_positioning.md` 提炼出的 `account_positioning`
- **优先模仿账号（可选）**：`selected_account_dir/reference_accounts.md` 提炼出的 `reference_accounts`

## 数据来源选择 / Source selection

1. **优先 V2**：如果 `outputs/{platform}/{specific_topic}/{output_files.trends}` 存在且 `results` 非空，以真实热点语料为主、知识库为辅，抽取当下正在传播的规律。
   - 结果已按 `vibe_score` 降序排好；`vibe_score` 的公式和权重由 `para_config.real_vibe_score` 控制，默认是「加权互动量 ÷ 发布天数」后 log 归一到 0-100。
   - **优先从 `vibe_score` 最高的几条帖子里学规律**，低分或 `vibe_score: null`（没抓到互动量）的样本仅作参考，不要等同看待。
   - 每条结果的 `engagement`（likes/saves/comments/shares）和 `published_days` 可帮你判断它为什么火（高收藏 = 收藏价值强，高分享 = 传播力强）。
   - 判断样本是否来自 `reference_accounts`：
     - 优先看结果字段：`source_type: reference_account`、`from_reference_account: true`、`source_account`、`account`、`author`。
     - 若没有显式字段，再用结果 `url` 与 `reference_accounts.homepage_url` 的域名/路径/handle 做保守匹配，或用 `account`/`author` 与 `reference_accounts.account_name` 匹配。
     - 匹配不到时标为 `unknown_source`，不要当作参考账号样本。
   - 若确认包含来自 `reference_accounts` 的样本，优先学习这些账号的结构、节奏和选题方式；样本不足、不匹配或来源未知时，再参考普通爆款样本。
2. **回退 V1**：如果没有 `outputs/{platform}/{specific_topic}/{output_files.trends}`、文件为空、或检索返回 `mode: offline`，**完全基于知识库** YAML 抽取规律。这是正常路径，不要因为缺少检索就报错。
3. 明确标注你用的是哪种来源（`source: trend_corpus` 或 `source: knowledge_base`）。
4. 如果存在 `account_positioning`，把爆款规律分成「可借鉴」和「不适合本账号」两类；不要因为某种表达很火就让账号偏离目标人群、领域边界或长期风格。

## 抽取维度 / Dimensions

参考 InternetSensor 规律三件套：

### 标题规律 Title patterns
- 当前主题下高频、有效的标题句式（钩子类型：反差 / 稀缺 / 后悔 / 干货……）

### 情绪规律 Emotion levers
- 哪些情绪在驱动互动（真实感 / 反差感 / 惊喜感 / 稀缺感 / 收藏价值……）

### 内容结构规律 Structure
- 高表现内容的骨架（如 Hook → 故事 → 价值 → 行动建议）

## 输出 / Output

```yaml
source: knowledge_base       # trend_corpus（V2）或 knowledge_base（V1）
platform: xiaohongshu
topic: food
title_patterns:
  - 反差/稀缺型钩子："开学两年才发现……"
  - 收藏导向："建议直接收藏"
emotion_levers: [真实感, 反差感, 稀缺感, 收藏价值]
structure: [Hook, 故事, 价值, 行动建议]
notes: 校园美食偏好"藏宝店"叙事与性价比细节
account_fit_notes:
  suitable:
    - 收藏导向的信息密度适合当前账号
  avoid:
    - 过度标题党会削弱账号可信度
```
