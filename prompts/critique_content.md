# Prompt: Vibe Critic / 网感评分器

> 本 Prompt 由 Claude 执行（非代码）。目标：从多个维度诊断内容为什么没有网感。
> Executed by Claude (not code). Goal: diagnose why the content lacks vibe.

## 输入 / Input

- `content`：待评价的原始内容
- `source_links`（可选）：`${output_dir}/${output_files.source_links}`，用户原文里 URL/PDF/网页的抽取结果
- `platform`：目标平台 → `knowledge/platforms/{platform}.yaml`
- `topic` + 抽取结果（来自 extract_patterns）
- `topic` YAML（若非 general）→ `knowledge/topics/{topic}.yaml`
- `account_positioning`（可选）：来自 `selected_account_dir/account_positioning.md`
- `para_config`：来自 `selected_account_dir/para_config.yaml`
- `output_dir`：本次运行目录，格式为 `outputs/{platform}/{specific_topic}/`
- `output_files`：来自 `para_config.output.files`

## 评分维度 / Scoring dimensions（每项 0-10）

| 维度 | dimension | 看什么 |
|------|-----------|--------|
| 钩子强度 | hook_strength | 前两行能否停住划动；标题有没有钩子 |
| 新颖度 | novelty | 角度是否新鲜，还是人人都在说的套话 |
| 真实感 | authenticity | 像真人经历还是广告/模板 |
| 分享价值 | shareability | 别人愿不愿意转给朋友 |
| 收藏价值 | saveability | 有没有值得收藏备用的实用信息 |
| 平台契合 | platform_fit | 语气、长度、格式是否符合该平台；若有账号定位，也检查是否符合账号目标人群、领域边界和风格 |
| AI味 | ai_smell | AI写作痕迹（**越高越差**，10 = 满是AI味） |

> 注意 `ai_smell` 是反向维度：分数越高代表 AI 味越重、越糟糕。

## 网感指数 / Vibe Index（0-100）

综合上述维度计算一个整体网感指数。**必须严格按 `para_config.predicted_vibe_index` 计算，不要凭感觉微调**。

默认配置等价于下列公式：

```
正向维度均值 = mean(hook_strength, novelty, authenticity,
                    shareability, saveability, platform_fit)   # 0-10
ai_penalty   = ai_smell                                        # 0-10
vibe_index   = round((正向维度均值 * (1 - ai_smell/20)) * 10)   # 0-100
```

如果用户在 `para_config.predicted_vibe_index.positive_dimensions` 中设置了权重，则使用加权平均：

```
positive_mean = weighted_mean(score[dimension], weight)
if para_config.predicted_vibe_index.ai_smell.enabled:
    penalty_factor = 1 - ai_smell / penalty_divisor
else:
    penalty_factor = 1
vibe_index = round(positive_mean * penalty_factor * scale, round_digits)
vibe_index = clamp(vibe_index, min_score, max_score)
```

即 AI 味越重，对整体分数的折扣越大。

输出前自检一次：用 6 个正向维度、权重配置和 `ai_smell` 重新代入公式，确保 `vibe_index`
与公式结果一致。

## 问题分析 / Problem analysis

针对得分低的维度，给出**具体、可操作**的问题点，不要泛泛而谈。
例如：「'味道不错'是空泛形容词，没有具体菜品、口感或价格，真实感和收藏价值都被拉低。」

若存在 `account_positioning`，必须额外检查：
- 内容是否吸引了错误人群，或忽略核心受众的真实需求。
- 是否为了追热点偏离主领域、可延展领域或硬约束。
- 语气是否变成不属于该账号的风格（例如过度标题党、营销腔、说教腔）。

发现定位偏离时，把它写进 `problems`，并优先归因到 `platform_fit` 或 `authenticity`。

若存在 `source_links`：
- 如果来源可读，指出原文没有用好哪些真实信息（如论文标题、问题、方法、实验/结论、限制），这些可作为改写的事实素材。
- 如果用户给了链接但来源不可读，把“链接内容未读取，后续不能基于链接猜测细节”写进 `problems` 或 `notes`。
- 不要因为链接存在就默认你已经知道链接内容；只以 `source_links` 中抽取到的文本为依据。

## 输出 / Output

输出同样的结构，并保存为 `${output_dir}/${output_files.critique}`。文件内容参考：

```json
{
  "platform": "xiaohongshu",
  "topic": "food",
  "original": {
    "title": "学校附近有一家很好吃的牛肉面店",
    "body": "价格不贵，味道不错。"
  },
  "scores": {
    "hook_strength": 3,
    "novelty": 4,
    "authenticity": 5,
    "shareability": 5,
    "saveability": 6,
    "platform_fit": 5,
    "ai_smell": 6
  },
  "vibe_index": 52,
  "problems": [
    "标题缺钩子：直接陈述事实，前两行无法停住划动",
    "\"价格不贵、味道不错\"为空泛评价，缺具体细节（菜品/价格/分量）",
    "结构平铺直叙，没有 Hook→故事→价值→行动建议 的节奏",
    "缺少收藏导向的行动建议"
  ],
  "reference_basis": "${output_dir}/${output_files.reference_examples}",
  "formula_config": "selected_account_dir/para_config.yaml#predicted_vibe_index"
}
```

对话中可简洁展示为 YAML：

```yaml
platform: xiaohongshu
topic: food
scores:
  hook_strength: 3
  novelty: 4
  authenticity: 5
  shareability: 5
  saveability: 6
  platform_fit: 5
  ai_smell: 6        # 反向，越高越差
vibe_index: 52       # 0-100
problems:
  - 标题缺钩子：直接陈述事实，前两行无法停住划动
  - "价格不贵、味道不错"为空泛评价，缺具体细节（菜品/价格/分量）
  - 结构平铺直叙，没有 Hook→故事→价值→行动建议 的节奏
  - 缺少收藏导向的行动建议
```
