# 检索配对消融：Dense vs Dense + Char-TF-IDF

> 复现时间：2026-11-13
> 数据：`eval/eval_queries_rebuilt.json`（150 条；可回答 130 条：exact 30 / paraphrase 40 / symptom 60 / offtopic 20）
> 脚本：`eval/eval_retrieval_ab_paired.py`
> 环境：Python 3.10+、BGE-M3 本地权重、当前 `kb/index/recall` 索引

## 1. 结果（逐 query 配对，top_k=10）

| Subset | n | 指标 | Dense | Dense+TF-IDF | Δ | 95% CI | 方向 |
|---|---|---:|---:|---:|---:|---:|---|
| overall | 130 | recall@1 | 0.754 | 0.762 | +0.008 | [−0.046, 0.062] | ≈ |
| overall | 130 | recall@3 | 0.915 | 0.900 | −0.015 | [−0.062, 0.031] | ≈ |
| overall | 130 | recall@5 | 0.938 | 0.938 | 0.000 | [−0.046, 0.046] | ≈ |
| overall | 130 | mrr@3 | 0.828 | 0.824 | −0.004 | [−0.045, 0.037] | ≈ |
| overall | 130 | ndcg@3 | 0.851 | 0.844 | −0.007 | [−0.047, 0.033] | ≈ |
| paraphrase | 40 | recall@1 | 0.700 | 0.650 | −0.050 | [−0.175, 0.075] | ≈ |
| paraphrase | 40 | recall@3 | 0.875 | 0.800 | −0.075 | [−0.200, 0.050] | ≈ |
| symptom | 60 | recall@1 | 0.667 | 0.717 | +0.050 | [−0.033, 0.133] | ≈ |
| symptom | 60 | recall@5 | 0.917 | 0.950 | +0.033 | [−0.033, 0.100] | ≈ |
| difficult | 100 | recall@3 | 0.890 | 0.870 | −0.020 | [−0.080, 0.040] | ≈ |

McNemar（Recall@3，配对）：overall b=6 / c=4 / p=0.754；paraphrase p=0.453；symptom p=1.0。
win / loss / tie：overall 15 / 14 / 101。

## 2. 结论

1. Dense + Char-TF-IDF 相对单路 Dense 没有统计显著提升：所有主指标的 95% CI 均跨 0，McNemar p 值均大于 0.05；整体 Recall@3 与 MRR@3 甚至略降（−0.015 / −0.004）。
2. 分层上增益与损失互相抵消：symptom（口语症状）Recall@1 +0.05 受益；paraphrase（近义改写）Recall@1 −0.05、Recall@3 −0.075 受损。
3. 不同指标不能混用：MRR@3 对第 2、3 名给部分分，Recall@5 统计前 5 名命中，二者都不是 Top-1。对外引用时必须标注具体指标。

## 3. 边界

- 这是开发/消融集，未做独立标注（`independent_annotation=false`），可回答样本仅 130 条，CI 较宽。
- 只评检索排序，不评生成质量与端到端决策；offtopic 20 条不参与排序指标。
- 结论仅适用于当前知识库、索引与阈值；知识库变更后应重跑。
