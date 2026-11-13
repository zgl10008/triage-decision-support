# 检索精排消融：BGE-reranker-v2-m3

> 复现时间：2026-11-13
> 数据：`eval/eval_queries_rebuilt.json`（150 条；可回答 130 条）
> 脚本：`eval/eval_retrieval_rerank_ab.py`
> 权重：`models/bge-reranker-v2-m3`（BAAI/bge-reranker-v2-m3）
> 方式：Phase A 用 BGE-M3 召回 top-50；Phase B 释放嵌入模型后，用 reranker 对候选精排

## 1. 四组指标（n=130）

| 组 | Top-1 | Top-3 | Top-5 | MRR@3 | nDCG@3 |
|---|---:|---:|---:|---:|---:|
| Dense | 0.754 | 0.915 | 0.938 | 0.828 | 0.851 |
| Dense + rerank | 0.846 | 0.962 | 0.977 | 0.901 | 0.917 |
| Dense + 字符 TF-IDF（混合） | 0.762 | 0.900 | 0.938 | 0.824 | 0.844 |
| 混合 + rerank | 0.846 | 0.962 | 0.977 | 0.901 | 0.917 |

## 2. 配对对比（差值 = 精排后 − 精排前）

| 对比 | Top-1 | 95% CI | MRR@3 | 95% CI | Top-3 | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Dense + rerank vs Dense | +0.092 | [0.031, 0.162] | +0.073 | [0.029, 0.121] | +0.046 | [0.008, 0.092] |
| 混合 + rerank vs 混合 | +0.085 | [0.015, 0.154] | +0.077 | [0.027, 0.129] | +0.062 | [0.015, 0.108] |

Top-1 的 McNemar 精确检验（由 `per_query_ranks.csv` 计算）：Dense b=4 / c=16，p=0.0118；混合 b=6 / c=17，p=0.0347。
Top-3 的 McNemar：Dense p=0.0703；混合 p=0.0215。
精排后 Dense 与混合的排序完全一致（win/loss/tie = 0/0/100），混合通道的差异被精排抹平。

## 3. 结论与边界

- 精排对 Top-1 与 MRR@3 有稳定增益，配对 bootstrap 95% CI 均不含 0；分层上 symptom 的 Top-1 提升最大（+0.167）。
- 精排是离线消融，线上默认未启用；8GB 显存下 BGE-M3 与 reranker 需要分阶段加载。
- 开发集没有独立标注，样本量 130，不能表述为临床准确率或独立测试集结果。
