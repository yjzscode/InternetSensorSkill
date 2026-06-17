# Prompt: Content Improver / 内容优化器

> 本 Prompt 由 Claude 执行（非代码）。目标：结合诊断结果重写内容，提升网感。
> Executed by Claude (not code). Goal: rewrite the content to raise its vibe index.

## 输入 / Input

- `content`：原始内容
- `source_links`（可选）：`${output_dir}/${output_files.source_links}`，用户原文里 URL/PDF/网页的抽取结果
- `platform` + `knowledge/platforms/{platform}.yaml`（do/don't、结构、格式）
- 抽取结果（extract_patterns）：标题/情绪/结构规律
- 诊断结果（critique_content）：各维度得分 + 问题清单
- `reference_examples`（可选）：`${output_dir}/${output_files.reference_examples}`，热点/爆款参考样本，默认 `reference_role: trend_hotspot`
- `account_reference_examples`（可选）：`${output_dir}/${output_files.account_reference_examples}`，来自 `selected_account_dir/reference_accounts.md` 的账号风格参考样本，默认 `reference_role: account_style`
- `topic` YAML（若非 general）
- `account_positioning`（可选）：来自 `selected_account_dir/account_positioning.md`
- `para_config`：来自 `selected_account_dir/para_config.yaml`
- `output_dir`：本次运行目录，格式为 `outputs/{platform}/{specific_topic}/`
- `output_files`：来自 `para_config.output.files`

## 优化原则 / Principles

1. **对症下药**：逐条针对 critique 的 `problems` 改写，不要只是换词。
2. **守平台规则**：套用 `{platform}.yaml` 的 `structure`、`formatting`、`dos`，规避 `donts` 和 `ai_smell_signals`。
3. **守账号定位**：若存在 `account_positioning`，重写优先符合目标人群、领域边界、风格语气、价值主张和硬约束。爆款样本只能借鉴钩子、结构和节奏，不能把账号改成另一个定位。
4. **用户来源优先**：如果 `source_links` 有 `status: ok` 的来源，优先使用其中的真实标题、摘要、方法、结论、数据、限制来补强文案；不要只根据原文猜测链接内容。
5. **区分两类参考样本**：
   - `reference_examples` / `trend_hotspot`：只学习热点网感技巧，如标题钩子、结构、平台表达、互动触发点。
   - `account_reference_examples` / `account_style`：学习账号想长期靠近的语气、节奏、人设边界、内容密度、CTA 方式。
6. **冲突优先级**：用户来源事实 > 账号定位 > 账号风格参考样本 > 热点网感技巧。热点样本和账号风格冲突时，保留账号风格，只借热点结构。
7. **保真**：不要编造原文和 `source_links` 都没有的事实（如具体价格、排名、实验数据、论文贡献）。缺少细节时，用占位提示或保守表达，而不是虚构。
8. **链接失败要保守**：如果用户给了 URL 但 `source_links` 抓取失败，不要假装读过链接；只能基于原文做表达优化，并提醒用户链接内容未能读取。
9. **降 AI 味**：去掉空泛形容词、过度排比、说教腔，换成第一人称、具体细节、口语节奏。
10. **保持作者本意**：优化表达，不改变原意和核心信息。

## 输出 / Output

先给分数对比，再给优化版本，最后说明改了什么。完整结果保存为 `${output_dir}/${output_files.rewrite}`，
文件结构参考 `outputs/xiaohongshu/rewrite.md`。

```text
原始网感指数：52
优化后网感指数：88
```

优化版本：

```text
（重写后的内容，符合目标平台的结构与格式）
```

改动说明 / What changed：
- 标题：从平铺陈述改为反差钩子，前两行制造"藏宝店"悬念
- 细节：补充分量、营业时间等收藏向信息（标注需作者确认的占位）
- 来源链接：从用户提供的论文/PDF/网页中提炼真实信息，避免凭空猜测
- 热点参考：借鉴了哪些 `trend_hotspot` 样本的钩子/结构
- 账号风格：借鉴了哪些 `account_style` 样本的语气/节奏/人设边界
- 结构：调整为 Hook → 故事 → 价值 → 行动建议
- 账号定位：保留面向学生的省钱实用口吻，避开探店营销腔
- 降 AI 味：删除空泛形容词，改用第一人称口语

> 若有占位（如未知价格），明确提示作者补充，不要虚构数字。
