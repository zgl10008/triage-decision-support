# -*- coding: utf-8 -*-
"""
检索配对消融：Dense vs Dense+Char-TF-IDF（逐 query 配对 + 统计检验）
====================================================================
只对比两组通道（用户指定），在 eval_queries_rebuilt.json（150 条）上：

    G1  Dense             use_sparse=False, use_tfidf=False
    G2  Dense + TF-IDF    use_sparse=False, use_tfidf=True

做法：
- 逐 query 记录命中 rank（top_k=10，避免 @1/3/5 被截断），保存 per-query 明细。
- 指标：Recall@1/3/5、MRR@1/3、nDCG@1/3（整体 + exact/paraphrase/symptom 分层）。
- 统计：配对 bootstrap（差值 95% CI，seed 固定）、McNemar 精确检验（hit@3）、
  win/loss/tie（按 reciprocal rank 比较）。

结论口径：只有当「混合 - Dense」的指标差值 95% CI 下界 > 0 且 McNemar p<0.05，
才判「有可靠提升」；CI 跨 0 → 判「无可靠证据表明提升」。
"""
import csv
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(EVAL_DIR, "..")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from FlagEmbedding import BGEM3FlagModel          # noqa: E402
from rag_retriever import HybridRetriever         # noqa: E402

INDEX_PATH = os.path.join(ROOT_DIR, "kb", "index", "recall")
LOCAL_MODEL_PATH = os.path.join(ROOT_DIR, "models", "bge-m3")
RESULTS_DIR = os.path.join(EVAL_DIR, "results", "retrieval_ab_paired")

TOP_K = 10            # 记录完整排名，@1/3/5 从这 10 里取
N_BOOT = 10000
SEED = 42

RANK_SUBSETS = ("overall", "exact", "paraphrase", "symptom", "difficult")


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rank_of(results, expected):
    for i, r in enumerate(results[:TOP_K]):
        if r["injury"] == expected:
            return i + 1
    return 0


def metric_on(ranks, k, metric):
    n = len(ranks)
    if n == 0:
        return 0.0
    if metric == "recall":
        return sum(1 for r in ranks if 0 < r <= k) / n
    if metric == "mrr":
        return sum(1.0 / r for r in ranks if 0 < r <= k) / n
    if metric == "ndcg":
        return sum(1.0 / math.log2(r + 1) for r in ranks if 0 < r <= k) / n
    raise ValueError(metric)


def per_query_metric(rank, k, metric):
    if metric == "recall":
        return 1.0 if 0 < rank <= k else 0.0
    if metric == "mrr":
        return 1.0 / rank if 0 < rank <= k else 0.0
    if metric == "ndcg":
        return 1.0 / math.log2(rank + 1) if 0 < rank <= k else 0.0
    raise ValueError(metric)


def bootstrap_paired(x1, x2, n_boot=N_BOOT, seed=SEED):
    """x1=G1 逐 query 指标值，x2=G2 逐 query 指标值。返回 (mean_diff, lo, hi)。"""
    import random
    rng = random.Random(seed)
    n = len(x1)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        d = sum(x2[i] - x1[i] for i in idx) / n
        diffs.append(d)
    diffs.sort()
    lo = diffs[int(0.025 * n_boot)]
    hi = diffs[int(0.975 * n_boot)]
    mean = sum(x2[i] - x1[i] for i in range(n)) / n
    return mean, lo, hi


def mcnemar(ranks1, ranks2, k):
    """hit@k 的 McNemar 精确检验。返回 (b, c, p)。b=G1中G2不中，c=G1不中G2中。"""
    b = c = 0
    for r1, r2 in zip(ranks1, ranks2):
        h1 = 0 < r1 <= k
        h2 = 0 < r2 <= k
        if h1 and not h2:
            b += 1
        elif not h1 and h2:
            c += 1
    # 双尾精确检验（二项分布，对称假设下）
    n = b + c
    if n == 0:
        return b, c, 1.0
    from math import comb
    p_two_tailed = 2.0 * sum(comb(n, i) * (0.5 ** n) for i in range(min(b, c) + 1))
    p_two_tailed = min(1.0, p_two_tailed)
    return b, c, p_two_tailed


def win_loss_tie(ranks1, ranks2):
    """按 rank 越小越好（rank=0 视为最差）。返回 (win, loss, tie)。"""
    w = l = t = 0
    for r1, r2 in zip(ranks1, ranks2):
        # 未命中 rank=0 → 视作 rank=TOP_K+1
        a = r1 if r1 > 0 else TOP_K + 1
        b = r2 if r2 > 0 else TOP_K + 1
        if b < a:
            w += 1
        elif b > a:
            l += 1
        else:
            t += 1
    return w, l, t


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(EVAL_DIR, "eval_queries_rebuilt.json")
    cases = load_cases(path)

    model_path = LOCAL_MODEL_PATH if os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")) else "BAAI/bge-m3"
    model = BGEM3FlagModel(model_path, use_fp16=True)
    retriever = HybridRetriever.load(INDEX_PATH, model)

    # 逐 query 跑两组
    rows = []
    for c in cases:
        exp = c.get("expected", "")
        r_dense = r_hybrid = 0
        top1_dense = top1_hybrid = 0.0
        if exp:  # answerable
            res1 = retriever.retrieve(c["query"], top_k=TOP_K, use_hyde=False,
                                      use_rerank=False, use_tfidf=False, use_sparse=False)
            res2 = retriever.retrieve(c["query"], top_k=TOP_K, use_hyde=False,
                                      use_rerank=False, use_tfidf=True, use_sparse=False)
            r_dense = rank_of(res1, exp)
            r_hybrid = rank_of(res2, exp)
            top1_dense = res1[0]["score"] if res1 else 0.0
            top1_hybrid = res2[0]["score"] if res2 else 0.0
        rows.append({
            "id": c["id"], "category": c["category"], "query": c["query"],
            "expected": exp, "rank_dense": r_dense, "rank_hybrid": r_hybrid,
            "top1_dense": top1_dense, "top1_hybrid": top1_hybrid,
        })

    # 保存 per-query 明细
    with open(os.path.join(RESULTS_DIR, "per_query_ranks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 分组 ranks
    by = {s: [] for s in RANK_SUBSETS}
    for r in rows:
        if not r["expected"]:
            continue
        by["overall"].append(r)
        by[r["category"]].append(r)
        if r["category"] in ("paraphrase", "symptom"):
            by["difficult"].append(r)

    summary = {}
    lines = []
    lines.append("| Subset | n | 指标 | Dense | Dense+TF-IDF | Δ | 95% CI | 方向 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")

    for sub in RANK_SUBSETS:
        rs = by[sub]
        n = len(rs)
        ranks1 = [r["rank_dense"] for r in rs]
        ranks2 = [r["rank_hybrid"] for r in rs]
        sub_summary = {"n": n}
        for metric, ks in (("recall", (1, 3, 5)), ("mrr", (1, 3)), ("ndcg", (1, 3))):
            for k in ks:
                m1 = metric_on(ranks1, k, metric)
                m2 = metric_on(ranks2, k, metric)
                x1 = [per_query_metric(r, k, metric) for r in ranks1]
                x2 = [per_query_metric(r, k, metric) for r in ranks2]
                mean_diff, lo, hi = bootstrap_paired(x1, x2)
                direction = "+" if lo > 0 else ("-" if hi < 0 else "≈")
                key = f"{metric}@{k}"
                sub_summary[key] = {
                    "dense": round(m1, 4), "hybrid": round(m2, 4),
                    "diff": round(mean_diff, 4), "ci": [round(lo, 4), round(hi, 4)],
                    "direction": direction,
                }
                lines.append("| {} | {} | {} | {:.3f} | {:.3f} | {:+.3f} | [{:.3f}, {:.3f}] | {} |".format(
                    sub, n, key, m1, m2, mean_diff, lo, hi, direction))
        # McNemar + win/loss（仅 recall@3 做统计推断）
        b, c, p = mcnemar(ranks1, ranks2, 3)
        w, l, t = win_loss_tie(ranks1, ranks2)
        sub_summary["mcnemar_recall3"] = {"b": b, "c": c, "p": round(p, 4)}
        sub_summary["win_loss_tie"] = {"win": w, "loss": l, "tie": t}
        summary[sub] = sub_summary

    # 写 summary
    with open(os.path.join(RESULTS_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n".join(lines))
    print("\n--- McNemar（Recall@3，配对） ---")
    for sub in RANK_SUBSETS:
        m = summary[sub]["mcnemar_recall3"]
        wl = summary[sub]["win_loss_tie"]
        print(f"  {sub:12s} n={summary[sub]['n']:3d}  b={m['b']} c={m['c']} p={m['p']}  "
              f"win/loss/tie={wl['win']}/{wl['loss']}/{wl['tie']}")
    print(f"\n已写入 {RESULTS_DIR}")


if __name__ == "__main__":
    main()
