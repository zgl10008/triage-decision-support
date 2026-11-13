# -*- coding: utf-8 -*-
"""
检索精排（rerank）消融：加 bge-reranker-v2-m3 精排是否有增益
================================================================
四组对比（recall_n=50，top_k=10 记录完整排名）：

    dense            Dense 单路，无精排
    dense_rerank     Dense 单路 + reranker 精排
    hybrid           Dense + Char-TF-IDF，无精排
    hybrid_rerank    Dense + Char-TF-IDF + reranker 精排

核心配对对比：
    1) dense_rerank  vs dense      —— 单路上精排是否有增益
    2) hybrid_rerank vs hybrid     —— 混合上精排是否有增益
    3) hybrid_rerank vs dense_rerank —— 都精排时混合 vs 单路

统计：配对 bootstrap（95% CI）+ McNemar(hit@3) + win/loss/tie。
结论口径同 retrieval_ab_paired：CI 下界 > 0 且 p<0.05 才算「有可靠增益」。

显存：8GB 卡无法同驻 dense(BGE-M3) + reranker 两个模型，故两阶段——
    Phase A  dense 独占 GPU 跑召回（存 top-50 候选）
    Phase B  释放 dense 后 reranker 独占 GPU 精排
"""
import csv
import gc
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

import torch                                                        # noqa: E402
from FlagEmbedding import BGEM3FlagModel                            # noqa: E402
from rag_retriever import HybridRetriever                           # noqa: E402
from transformers import AutoTokenizer, AutoModelForSequenceClassification  # noqa: E402


class SlowReranker:
    """绕过 FlagReranker 的 fast-tokenizer 依赖。

    环境里 tokenizers 0.22 移除了 sentencepiece 后端，XLMRobertaTokenizerFast
    不可用，导致 FlagReranker.compute_score 调 prepare_for_model 崩溃。
    这里用 slow tokenizer + AutoModelForSequenceClassification 复刻等价逻辑。
    """

    def __init__(self, path, use_fp16=False, max_length=512, device=None, batch_size=32):
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        if use_fp16:
            self.model = self.model.half()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.model.to(self.device)
        self.model.eval()
        self.max_length = max_length
        self.batch_size = batch_size

    def compute_score(self, pairs, normalize=True):
        scores = []
        B = self.batch_size
        for i in range(0, len(pairs), B):
            batch = pairs[i:i + B]
            qs = [p[0] for p in batch]
            ps = [p[1] for p in batch]
            enc = self.tokenizer(qs, ps, max_length=self.max_length,
                                 truncation="only_second", padding=True,
                                 return_tensors="pt")
            enc = {k: v.to(self.device) for k, v in enc.items()}
            with torch.no_grad():
                logits = self.model(**enc, return_dict=True).logits.view(-1).float()
            scores.extend(logits.cpu().numpy().tolist())
        if normalize:
            scores = [float(torch.sigmoid(torch.tensor(s))) for s in scores]
        return scores


INDEX_PATH = os.path.join(ROOT_DIR, "kb", "index", "recall")
DENSE_MODEL_PATH = os.path.join(ROOT_DIR, "models", "bge-m3")
RERANK_MODEL_PATH = os.path.join(ROOT_DIR, "models", "bge-reranker-v2-m3")
RESULTS_DIR = os.path.join(EVAL_DIR, "results", "retrieval_rerank_ab")

TOP_K = 10
RECALL_N = 50
RERANK_BATCH = 16
N_BOOT = 10000
SEED = 42

GROUPS = [
    ("dense",          {"use_tfidf": False, "use_rerank": False}),
    ("dense_rerank",   {"use_tfidf": False, "use_rerank": True}),
    ("hybrid",         {"use_tfidf": True,  "use_rerank": False}),
    ("hybrid_rerank",  {"use_tfidf": True,  "use_rerank": True}),
]

# 元组顺序 = (基线, 处理)，Δ = 处理 - 基线（后者 - 前者），Δ>0 表示处理更好
COMPARISONS = [
    ("dense",        "dense_rerank",   "单路 Dense：加精排 vs 不加"),
    ("hybrid",       "hybrid_rerank",  "混合 Dense+TF-IDF：加精排 vs 不加"),
    ("dense_rerank", "hybrid_rerank",  "都精排：混合 vs 单路"),
]

RANK_SUBSETS = ("overall", "exact", "paraphrase", "symptom", "difficult")


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rank_of(results, expected):
    for i, r in enumerate(results[:TOP_K]):
        if r["injury"] == expected:
            return i + 1
    return 0


def rank_in_order(order, expected):
    for i, inj in enumerate(order[:TOP_K]):
        if inj == expected:
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
    import random
    rng = random.Random(seed)
    n = len(x1)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(x2[i] - x1[i] for i in idx) / n)
    diffs.sort()
    lo = diffs[int(0.025 * n_boot)]
    hi = diffs[int(0.975 * n_boot)]
    mean = sum(x2[i] - x1[i] for i in range(n)) / n
    return mean, lo, hi


def mcnemar(ranks1, ranks2, k):
    from math import comb
    b = c = 0
    for r1, r2 in zip(ranks1, ranks2):
        h1 = 0 < r1 <= k
        h2 = 0 < r2 <= k
        if h1 and not h2:
            b += 1
        elif not h1 and h2:
            c += 1
    n = b + c
    if n == 0:
        return b, c, 1.0
    p = 2.0 * sum(comb(n, i) * (0.5 ** n) for i in range(min(b, c) + 1))
    return b, c, min(1.0, p)


def win_loss_tie(ranks1, ranks2):
    w = l = t = 0
    for r1, r2 in zip(ranks1, ranks2):
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

    # ---------- Phase A：dense 独占 GPU 跑召回 ----------
    dense_model = BGEM3FlagModel(DENSE_MODEL_PATH, use_fp16=True)
    retriever = HybridRetriever.load(INDEX_PATH, dense_model)
    store = retriever.store
    id_to_text = {i: store.id_to_meta[i]["text"] for i in store.ids}

    recalled = {}  # id -> {"dense": [injury...], "hybrid": [injury...]}（top RECALL_N）
    rows = []
    for c in cases:
        exp = c.get("expected", "")
        row = {"id": c["id"], "category": c["category"], "query": c["query"], "expected": exp}
        for label, _ in GROUPS:
            row[f"rank_{label}"] = 0
            row[f"top1_{label}"] = 0.0
        if exp:
            for label, use_tfidf in (("dense", False), ("hybrid", True)):
                res = retriever.retrieve(c["query"], top_k=RECALL_N, use_hyde=False,
                                         use_rerank=False, use_tfidf=use_tfidf,
                                         use_sparse=False, recall_n=RECALL_N)
                injuries = [r["injury"] for r in res]
                recalled.setdefault(c["id"], {})[label] = injuries
                row[f"rank_{label}"] = rank_in_order(injuries, exp)
                row[f"top1_{label}"] = res[0]["score"] if res else 0.0
        rows.append(row)

    # 释放 dense 模型，腾显存给 reranker
    del dense_model, retriever
    gc.collect()
    torch.cuda.empty_cache()

    # ---------- Phase B：reranker 独占 GPU 精排 ----------
    reranker = SlowReranker(RERANK_MODEL_PATH, use_fp16=True, batch_size=RERANK_BATCH)
    rows_by_id = {r["id"]: r for r in rows}
    for c in cases:
        exp = c.get("expected", "")
        if not exp:
            continue
        row = rows_by_id[c["id"]]
        for label in ("dense", "hybrid"):
            injuries = recalled[c["id"]][label]
            texts = [id_to_text[i] for i in injuries]
            scores = reranker.compute_score([[c["query"], t] for t in texts], normalize=True)
            order = [inj for _, inj in sorted(zip(scores, injuries), key=lambda x: -x[0])]
            row[f"rank_{label}_rerank"] = rank_in_order(order, exp)
            if order:
                score_map = dict(zip(injuries, scores))
                row[f"top1_{label}_rerank"] = score_map[order[0]]

    with open(os.path.join(RESULTS_DIR, "per_query_ranks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 分组
    by = {s: [] for s in RANK_SUBSETS}
    for r in rows:
        if not r["expected"]:
            continue
        by["overall"].append(r)
        by[r["category"]].append(r)
        if r["category"] in ("paraphrase", "symptom"):
            by["difficult"].append(r)

    # 组指标表
    print("=" * 78)
    print("四组指标（overall, n=%d）" % len(by["overall"]))
    print("=" * 78)
    header = "| 组 | Recall@1 | Recall@3 | Recall@5 | MRR@3 | nDCG@3 |"
    print(header)
    print("|" + "---|" * 6)
    group_metrics = {}
    for label, cfg in GROUPS:
        ranks = [r[f"rank_{label}"] for r in by["overall"]]
        r1 = metric_on(ranks, 1, "recall")
        r3 = metric_on(ranks, 3, "recall")
        r5 = metric_on(ranks, 5, "recall")
        m3 = metric_on(ranks, 3, "mrr")
        n3 = metric_on(ranks, 3, "ndcg")
        group_metrics[label] = {"ranks_overall": ranks}
        print("| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
            label, r1, r3, r5, m3, n3))

    # 配对对比
    print("\n" + "=" * 78)
    print("配对统计（差值 = 后者 - 前者；方向 + 表示后者更好）")
    print("=" * 78)
    summary = {}
    for a_label, b_label, desc in COMPARISONS:
        print(f"\n### {desc}  （{b_label} - {a_label}）")
        print("| Subset | n | 指标 | 前者 | 后者 | Δ | 95% CI | 方向 |")
        print("|---|---|---:|---:|---:|---:|---:|---|")
        for sub in RANK_SUBSETS:
            rs = by[sub]
            n = len(rs)
            ranks_a = [r[f"rank_{a_label}"] for r in rs]
            ranks_b = [r[f"rank_{b_label}"] for r in rs]
            for metric, k in (("recall", 1), ("recall", 3), ("recall", 5), ("mrr", 3), ("ndcg", 3)):
                ma = metric_on(ranks_a, k, metric)
                mb = metric_on(ranks_b, k, metric)
                xa = [per_query_metric(r, k, metric) for r in ranks_a]
                xb = [per_query_metric(r, k, metric) for r in ranks_b]
                diff, lo, hi = bootstrap_paired(xa, xb)
                direction = "+" if lo > 0 else ("-" if hi < 0 else "≈")
                print("| {} | {} | {} | {:.3f} | {:.3f} | {:+.3f} | [{:.3f}, {:.3f}] | {} |".format(
                    sub, n, f"{metric}@{k}", ma, mb, diff, lo, hi, direction))
        # McNemar + win/loss（overall）
        b, c, p = mcnemar(ranks_a, ranks_b, 3)
        w, l, t = win_loss_tie(ranks_a, ranks_b)
        key = f"{a_label}_vs_{b_label}"
        summary[key] = {"mcnemar_recall3": {"b": b, "c": c, "p": round(p, 4)},
                        "win_loss_tie": {"win": w, "loss": l, "tie": t}}
        print(f"  → overall McNemar(hit@3): b={b} c={c} p={p:.4f}；win/loss/tie={w}/{l}/{t}")

    with open(os.path.join(RESULTS_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {RESULTS_DIR}")


if __name__ == "__main__":
    main()
