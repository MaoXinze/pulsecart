# 净界智能扫地机器人合成演示集

本目录由 `scripts/generate_demo_reviews.py` 使用固定随机种子生成，专门用于 PulseCart 的本地导入、审核队列、趋势洞察和界面演示。数据不含个人信息，也不来自任何电商平台或真实客户。

| 文件 | 内容 | 正确用途 |
| --- | --- | --- |
| `reviews.csv` | 1,200 条可导入评论 | 导入与分析演示 |
| `review_tasks.jsonl` | 300 条待人工审核任务 | 审核队列与质量流程演示 |
| `synthetic_reference_labels.jsonl` | 生成时的合成参考标签 | 仅用于流程和页面验收，不能用于正式训练或对外指标 |
| `manifest.json` | 随机种子、分布、场景和文件校验和 | 追溯与完整性验证 |

数据刻意包含一个可发现的产品问题场景：`JC-S2-PRO` 的 `2.1.0` 版本在 2026-07-01 后出现更多导航避障负面信号。该场景用于验证时间、SKU、版本和属性筛选是否正常，不能解释为真实产品问题。

重新生成：

```powershell
cd sentiment-ai
python scripts/generate_demo_reviews.py
```

对 `review_tasks.jsonl` 中的任务完成人工审核后，只有 `review_status` 为 `approved` 或 `verified` 的记录，才可作为 `scripts/train_baseline.py` 的训练输入。
