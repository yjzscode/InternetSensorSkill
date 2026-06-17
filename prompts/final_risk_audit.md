# Prompt: Final Risk Audit / 发布前事实与平台风险审查

> 本 Prompt 由 Claude 执行（非代码）。目标：在 pipeline 最后检查事实风险、虚构风险和平台发布风险。
> Executed by Claude (not code). Goal: audit factual and platform-sensitive risks
> before publishing. This is a publishing risk reminder, not legal advice.

## 输入 / Input

- `original_content`：用户原文
- `rewritten_content`：Step 5 改写后内容
- `source_links`（可选）：`${output_dir}/${output_files.source_links}`，用户原文里 URL/PDF/网页的抽取结果
- `platform` + `knowledge/platforms/{platform}.yaml`
- `account_positioning`（可选）
- `critique`：`${output_dir}/${output_files.critique}`
- `account_consistency`：`${output_dir}/${output_files.account_consistency}`
- `para_config`：来自 `selected_account_dir/para_config.yaml`
- `output_dir`：本次运行目录，格式为 `outputs/{platform}/{specific_topic}/`
- `output_files`：来自 `para_config.output.files`

## 审查边界 / Scope

只做“发布风险提醒”，不做法律、医学、投资等专业判断。

重点检查两类问题：

1. **事实/虚构风险**：改写版是否加入了原文和可读来源链接都没有提供的具体事实。
2. **平台敏感/违规风险**：改写版是否包含容易触发平台风控或损害账号可信度的表达。

## 事实/虚构风险 / Fact & hallucination risks

把所有“必须用户确认”的事实列出来，尤其是：

- 原文没提供的数据、比例、金额、价格、时间、地点、排名。
- 原文没提供的亲身经历、客户案例、实验结果、职业经历。
- 医学、法律、投资、教育升学等判断。
- 功效承诺、收益承诺、绝对化表达。
- 图片、截图、素材来源或授权状态。

判断方法：

- 原文明确提供的事实：可标为 `supported_by_original`。
- `source_links` 可读且明确支持的事实：可标为 `supported_by_source_links`，并记录 URL。
- 改写中新出现、但原文和 `source_links` 都没有支持的事实：必须列入 `must_confirm_facts`。
- 用户给了 URL 但链接抓取失败：把“链接未能读取/抽取，不能支撑新增事实”列入 `source_link_warnings`。
- 只是语气、结构、标题变化，不算事实风险。

## 平台风险 / Platform risks

结合 `knowledge/platforms/{platform}.yaml` 的 `donts`、`ai_smell_signals`，以及
`para_config.risk_audit.platform_sensitive_topics.common` 和对应平台条目提示风险。

常见风险：

- 医疗健康、金融投资、法律建议。
- 夸大功效、绝对化表达、收益保证。
- 搬运/洗稿、过度模仿、未授权图片。
- 引战、攻击特定群体、过度标题党。
- 公众号、知乎、LinkedIn 尤其注意未证实专业判断和数据来源。

## 输出 / Output

保存为 `${output_dir}/${output_files.risk_audit}`。

```json
{
  "platform": "zhihu",
  "risk_level": "medium",
  "must_confirm_facts": [
    {
      "claim": "3个月涨粉10万",
      "where": "正文第2段",
      "reason": "原文没有提供该数据，属于新增具体结果",
      "suggested_fix": "改为“涨粉速度明显提升（请补真实数据）”或删除"
    }
  ],
  "supported_by_source_links": [
    {
      "claim": "论文提出 Jano，用 early-stage convergence awareness 自适应加速 diffusion generation",
      "source_url": "https://openaccess.thecvf.com/...",
      "evidence": "source_links.key_sections.abstract"
    }
  ],
  "source_link_warnings": [],
  "platform_risks": [
    {
      "type": "unsourced_professional_claim",
      "severity": "medium",
      "reason": "知乎读者会追问依据，缺少来源会削弱可信度",
      "suggested_fix": "补充来源、限定适用范围，或改成个人观察"
    }
  ],
  "image_or_material_risks": [
    {
      "type": "unknown_image_authorization",
      "severity": "low",
      "reason": "如果使用非自有图片，需要确认授权"
    }
  ],
  "safe_to_publish": false,
  "publish_notes": [
    "先确认 must_confirm_facts 中的数据和经历",
    "涉及专业判断的段落建议补来源或降级成个人经验"
  ],
  "disclaimer": "本审查只做发布风险提醒，不构成法律、医学或投资建议。"
}
```

`risk_level` 取值：`low` / `medium` / `high`。

`safe_to_publish` 的保守规则：

- 有任何 `must_confirm_facts` 未确认：`false`
- 有 `high` 平台风险：`false`
- 只有低风险提示且无待确认事实：`true`
