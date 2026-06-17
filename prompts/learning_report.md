# Prompt: Reference Account Learning Report / 竞品账号学习报告

> 本 Prompt 由 Claude 执行（非代码）。目标：基于 reference accounts 最近抓取的真实内容，
> 总结可长期学习的选题、标题、结构和评论区需求。

## 输入 / Input

- `learning_raw`：`${output_dir}/${output_files.learning_raw}`，由 `retrieval/learning_report.py` 生成
- `account_positioning`：来自 `selected_account_dir/account_positioning.md`
- `reference_accounts`：来自 `selected_account_dir/reference_accounts.md`
- `para_config`：来自 `selected_account_dir/para_config.yaml`
- `output_dir`：报告输出目录，格式为 `outputs/{platform}/{specific_topic}/`
- `output_files`：来自 `para_config.output.files`

## 任务 / Task

阅读每个参考账号抓到的真实内容和 `vibe_score`，生成一份运营学习报告。

重点总结：

1. 最近高赞/高网感选题：哪些主题更容易起量，哪些只是短期热点。
2. 常用标题句式：按钩子类型归类，不要照抄原句。
3. 内容结构：开头、展开、证据/细节、结尾 CTA 的常见骨架。
4. 评论区高频问题：如果抓取结果没有评论区内容，则基于标题/正文谨慎推断，并标注 `inferred`。
5. 适合你的账号学什么：结合 `account_positioning`，列出可借鉴点。
6. 不适合学什么：容易让账号跑偏、过度模仿、风险较高的套路。
7. 下周可试选题：给 5-10 个可执行选题，标注适配平台和账号定位理由。

## 输出 / Output

保存为 `${output_dir}/${output_files.learning_report}`。

建议结构：

```markdown
# 竞品账号学习报告

## 数据概况

- 平台：
- 参考账号数：
- 抓取内容数：
- 最高真实网感指数：

## 最近高赞选题

| 选题 | 参考账号 | 代表内容 | vibe_score | 为什么有效 |
|---|---|---|---:|---|

## 标题句式

- 反差型：
- 结论前置型：
- 清单/教程型：

## 内容结构

- 常见结构：
- 适合本账号改造方式：

## 评论区/用户需求

- 高频问题：
- 可延展内容：

## 适合学习

- ...

## 不适合学习

- ...

## 下周可试选题

1. ...
```

约束：

- 必须引用 `learning_raw` 中真实样本的标题/账号/vibe_score 作为依据。
- 只把 `items` 当作已确认来自参考账号的样本；`candidate_items` 只是低置信度搜索命中，不能当作参考账号内容。
- 不能复制参考账号原文或个人经历。
- 不要把“抓取不到评论区”伪装成真实评论；只能标注为推断。
