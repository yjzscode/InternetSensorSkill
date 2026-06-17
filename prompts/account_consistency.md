# Prompt: Account Consistency Scorer / 账号一致性评分器

> 本 Prompt 由 Claude 执行（非代码）。目标：只评价“改写后内容”是否仍符合账号定位。
> Executed by Claude (not code). Goal: score whether the rewritten content still
> fits the account positioning.

## 输入 / Input

- `rewritten_content`：Step 5 输出的改写版本
- `original_content`：用户原始内容，仅用于判断改写是否偏离原意
- `platform` + `knowledge/platforms/{platform}.yaml`
- `account_positioning`：来自 `selected_account_dir/account_positioning.md`；若不可用，仍输出但标记低置信度
- `reference_accounts`（可选）：来自 `selected_account_dir/reference_accounts.md`
- `reference_examples`（可选）：`${output_dir}/${output_files.reference_examples}`
- `account_reference_examples`（可选）：`${output_dir}/${output_files.account_reference_examples}`，来自参考账号的账号风格样本
- `para_config`：来自 `selected_account_dir/para_config.yaml`
- `output_dir`：本次运行目录，格式为 `outputs/{platform}/{specific_topic}/`
- `output_files`：来自 `para_config.output.files`

## 重要规则 / Important rule

只对**改写后内容**打账号一致性分。不要评价改写前原文。

这个分数不等于网感指数：

- 网感指数回答“会不会更容易传播”。
- 账号一致性回答“这是不是这个账号该发、该这么说的内容”。

如果爆款写法与账号定位冲突，以账号定位为准。

## 评分维度 / Dimensions（每项 0-10）

按 `para_config.account_consistency.dimensions` 的权重计算：

| 维度 | dimension | 看什么 |
|------|-----------|--------|
| 目标人群契合 | target_audience_fit | 是否打中账号目标人群，而不是吸引错误人群 |
| 领域契合 | domain_fit | 是否属于主领域/可延展领域，是否触碰 avoid |
| 内容支柱契合 | content_pillar_fit | 是否符合账号长期栏目、选题支柱或内容资产方向 |
| 价值承诺契合 | value_promise_fit | 是否提供账号承诺的价值，如干货、陪伴、观点、审美 |
| 语气风格契合 | voice_style_fit | 语气、人设、表达节奏是否一致 |
| 视角身份契合 | perspective_fit | 立场、身份感、叙述视角是否像这个账号 |
| 参考账号学习度 | reference_account_alignment | 是否学到参考账号优点，但没有照搬 |
| 平台格式契合 | platform_format_fit | 是否仍适合目标平台表达形态 |

## 公式 / Formula

必须严格按 `para_config.account_consistency` 计算：

```text
base_0_to_10 = weighted_mean(score[dimension], weight)
raw_score = base_0_to_10 * 10
penalty = sum(triggered_penalty_points)
score = clamp(raw_score - penalty, min_score, max_score)
score = round(score, round_digits)
```

然后应用 caps：

```text
如果 domain_fit <= 4：score = min(score, caps.domain_fit_lte_4)
如果 target_audience_fit <= 4：score = min(score, caps.target_audience_fit_lte_4)
如果存在 severe_brand_risk：score = min(score, caps.severe_brand_risk)
```

常见惩罚项来自 `para_config.account_consistency.penalties`：

- `off_domain_topic`：明显偏离领域
- `wrong_audience`：目标人群错位
- `style_conflict`：风格冲突
- `over_imitation`：过度模仿参考账号
- `brand_risk`：损害账号可信度、价值观或长期定位

若存在 `account_reference_examples`：
- 用它判断改写是否保持了参考账号想学习的语气、节奏、内容密度和 CTA 风格。
- 只看 `source_type: account_reference` / `reference_role: account_style` 的样本。
- 如果只是学到结构与节奏，且事实与表达仍属于用户自己，`reference_account_alignment` 可以加分。
- 如果照搬原句、经历、标题模板、账号身份或具体事实，应触发 `over_imitation` 惩罚。

## 输出 / Output

保存为 `${output_dir}/${output_files.account_consistency}`。

```json
{
  "platform": "xiaohongshu",
  "account_positioning_available": true,
  "account_consistency_score": 82,
  "dimension_scores": {
    "target_audience_fit": 8,
    "domain_fit": 9,
    "content_pillar_fit": 8,
    "value_promise_fit": 7,
    "voice_style_fit": 8,
    "perspective_fit": 9,
    "reference_account_alignment": 7,
    "platform_format_fit": 8
  },
  "penalties": [
    {
      "type": "over_imitation",
      "points": 4,
      "reason": "表达节奏接近参考账号，但个人账号视角还不够突出"
    }
  ],
  "caps_applied": [],
  "verdict": "基本符合账号定位，但需要增强账号自己的身份感",
  "revision_advice": [
    "开头加入更明确的账号视角",
    "减少泛化情绪词，增加面向目标人群的具体场景",
    "保留爆款结构，但降低模仿痕迹"
  ],
  "formula_config": "selected_account_dir/para_config.yaml#account_consistency"
}
```

如果 `account_positioning` 不可用：

- `account_positioning_available` 设为 `false`
- 基于平台规则和原文意图给一个低置信度估计
- `verdict` 明确写“缺少账号定位，分数仅供参考”
