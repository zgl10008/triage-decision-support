# -*- coding: utf-8 -*-
"""
Phase 3-1：Retrieval Ablation（正式检索消融）
================================================================
在**同一开发/消融集** `eval_queries_rebuilt.json`（150 条，难例 77%）上对比两组通道：

    A. Dense
    B. Dense + char-TF-IDF

指标（对每个 subset）：Recall@1/3/5、MRR@1/3/5、nDCG@1/3/5。
- offtopic（20 条）无 expected，不参与排名指标（单独统计其 top-1 命中情况作拒答参考）。
- 使用 HybridRetriever + BGE-M3 真实向量；该集合不是独立测试集，结果只用于开发消融。

用法：python eval/eval_phase3_retrieval.py [eval_set.json]
产出：eval/results/retrieval_ablation.json / .csv
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
RESULTS_DIR = os.path.join(EVAL_DIR, "results")

# 排名子集：有 expected（可判对错）的类别；offtopic 无 ground truth，单独统计。
RANK_SUBSETS = ("overall", "exact", "paraphrase", "symptom")
GROUPS = [
    ("Dense", {"use_sparse": False, "use_tfidf": False}),
    ("Dense+TF-IDF", {"use_sparse": False, "use_tfidf": True}),
]


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dcg_at(rank, k):
    """单相关文档 DCG：命中且 rank<=k → 1/log2(rank+1)，否则 0。"""
    return 1.0 / math.log2(rank + 1) if 0 < rank <= k else 0.0


def metrics_for(ranks, k):
    """ranks: list[int]，0 表示未命中。返回 recall/mrr/ndcg @k。"""
    hits = [r for r in ranks if 0 < r <= k]
    n = len(ranks)
    if n == 0:
        return 0.0, 0.0, 0.0
    recall = len(hits) / n
    mrr = sum(1.0 / r for r in hits) / n
    ndcg = sum(_dcg_at(r, k) for r in ranks) / n
    return recall, mrr, ndcg


def run_group(retriever, cases, cfg, top_k=5):
    """跑一组通道，返回每个 answerable case 的命中 rank（0=未命中）+ offtopic top1。"""
    ranks = {}          # id -> rank（仅 answerable）
    offtopic_hit = 0    # offtopic 中 top-1 恰为非空（衡量是否会乱答，越小越好）
    offtopic_n = 0
    for c in cases:
        results = retriever.retrieve(
            c["query"], top_k=top_k,
            use_hyde=False, use_rerank=False,
            use_tfidf=cfg["use_tfidf"], use_sparse=cfg["use_sparse"],
        )
        if c.get("expected"):
            rank = 0
            for i, r in enumerate(results):
                if r["injury"] == c["expected"]:
                    rank = i + 1
                    break
            ranks[c["id"]] = rank
        else:  # offtopic
            offtopic_n += 1
            # 真实语义检索对 off-topic 应返回低置信（top-1 不该是某个伤情名的高分命中）。
            # 这里记「top-1 是否仍给出候选」作参考（不判对错，因为无 ground truth）。
            if results:
                offtopic_hit += 1
    return ranks, offtopic_hit, offtopic_n


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(EVAL_DIR, "eval_queries_rebuilt.json")
    cases = load_cases(path)

    model_path = LOCAL_MODEL_PATH if os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")) else "BAAI/bge-m3"
    model = BGEM3FlagModel(model_path, use_fp16=True)
    retriever = HybridRetriever.load(INDEX_PATH, model)

    # 子集索引
    by_subset = {s: [] for s in RANK_SUBSETS}
    for c in cases:
        by_subset["overall"].append(c)
        if c.get("expected") and c["category"] in ("exact", "paraphrase", "symptom"):
            by_subset[c["category"]].append(c)

    rows = []          # CSV 行
    json_out = {"dataset": os.path.basename(path), "num_queries": len(cases),
                "num_answerable": len([c for c in cases if c.get("expected")]),
                "offtopic_queries": len([c for c in cases if not c.get("expected")]),
                "groups": {}}

    for label, cfg in GROUPS:
        ranks, off_hit, off_n = run_group(retriever, cases, cfg, top_k=5)
        json_out["groups"][label] = {"subsets": {}, "offtopic_top1_nonempty": off_hit,
                                     "offtopic_queries": off_n}

        for sub in RANK_SUBSETS:
            sub_ranks = [ranks[c["id"]] for c in by_subset[sub] if c.get("expected")]
            r1, m1, n1 = metrics_for(sub_ranks, 1)
            r3, m3, n3 = metrics_for(sub_ranks, 3)
            r5, m5, n5 = metrics_for(sub_ranks, 5)
            row = {
                "method": label, "subset": sub, "num_queries": len(sub_ranks),
                "recall@1": round(r1, 4), "recall@3": round(r3, 4), "recall@5": round(r5, 4),
                "mrr@1": round(m1, 4), "mrr@3": round(m3, 4), "mrr@5": round(m5, 4),
                "ndcg@1": round(n1, 4), "ndcg@3": round(n3, 4), "ndcg@5": round(n5, 4),
            }
            rows.append(row)
            json_out["groups"][label]["subsets"][sub] = {
                k: v for k, v in row.items() if k not in ("method", "subset")}

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "retrieval_ablation.json"), "w", encoding="utf-8") as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2)

    # CSV：一列 method，一列 subset，其余为指标
    fieldnames = ["method", "subset", "num_queries",
                  "recall@1", "recall@3", "recall@5",
                  "mrr@1", "mrr@3", "mrr@5",
                  "ndcg@1", "ndcg@3", "ndcg@5"]
    with open(os.path.join(RESULTS_DIR, "retrieval_ablation.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fieldnames})

    # 打印 Markdown（overall 一行 + 各 subset）
    print("评测集：{}（{} 条，answerable {} 条，offtopic {} 条）".format(
        os.path.basename(path), len(cases), json_out["num_answerable"], json_out["offtopic_queries"]))
    print("\n| Method | Subset | Recall@1 | Recall@3 | Recall@5 | MRR@3 | MRR@5 | nDCG@3 | nDCG@5 | n |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for label, _ in GROUPS:
        for sub in RANK_SUBSETS:
            g = json_out["groups"][label]["subsets"][sub]
            print("| {} | {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {} |".format(
                label, sub, g["recall@1"], g["recall@3"], g["recall@5"],
                g["mrr@3"], g["mrr@5"], g["ndcg@3"], g["ndcg@5"], g["num_queries"]))

    print("\n已写入 eval/results/retrieval_ablation.json / .csv")


if __name__ == "__main__":
    main()
