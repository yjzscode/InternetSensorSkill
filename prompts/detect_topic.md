# Prompt: Topic Detection / 主题识别

> 本 Prompt 由 Claude 执行（非代码）。目标：把用户内容映射到一个 topic slug。
> Executed by Claude (not code). Goal: map raw content to a topic slug.

## 输入 / Input

- `content`：用户提供的原始内容
- `platform`：目标平台（bilibili / xiaohongshu / zhihu / weixin / weibo /
  douban / hupu / twitter / linkedin）
- `para_config`：来自 `selected_account_dir/para_config.yaml`（可选）
- 可读取 `knowledge/topics/` 下的 YAML 作为候选主题及其 `aliases`

## 任务 / Task

1. 阅读 `content`，判断它属于哪个领域。
2. 对照 `knowledge/topics/*.yaml` 的 `topic` 和 `aliases`，选出最匹配的一个 slug。
3. 如果没有现成主题匹配，输出 `topic: general` 并给出一个简短的自定义领域标签（如 `数码测评`），不要硬塞。
4. 额外抽取一个用于保存目录的 `specific_topic_label`：根据内容核心对象生成 2-5 个词的 kebab-case slug，优先用英文/拼音安全字符，避免空格和路径特殊字符。

## 判定原则 / Rules

- 以内容的核心对象为准（牛肉面店 → food，而非"价格"→ 消费）。
- 一条内容可能横跨多个领域，只取主导的一个。
- 校园场景的美食仍归 `food`（display 可写"校园美食"）。
- 拿不准时，宁可 `general` + 自定义标签，也不要错配到无关主题。

## 输出 / Output

输出一个 YAML 块，供后续步骤读取：

```yaml
topic: food            # slug，或 general
topic_display: 校园美食  # 人类可读领域名
matched_aliases: [牛肉面, 校园美食]   # 命中的 alias，便于解释
confidence: high       # high / medium / low
reason: 内容核心是学校附近的牛肉面店推荐，属于校园美食探店
specific_topic_label: food-beef-noodles
```

> Claude Code 在主流程中用 `para_config.output.timestamp_format`（默认 `%Y%m%d-%H%M%S`）
> 拼出 `specific_topic = {timestamp}-{specific_topic_label}`，
> 并把本次输入输出保存到 `outputs/{platform}/{specific_topic}/`。
