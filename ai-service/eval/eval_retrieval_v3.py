# -*- coding: utf-8 -*-
"""
阶段2：BGE-M3 混合检索评测 —— 与 TF-IDF 基线同口径对比
============================================
只评检索侧：Recall@k / MRR@k / nDCG@k（决策侧逻辑阶段 3 再做）。

用法：python eval/eval_retrieval_v3.py [eval_queries_v2.json] [top_k]
依赖：已用 build_index.py 建好 kb/index/recall.* 索引
"""
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
sys.path.insert(0, ROOT_DIR)

from FlagEmbedding import BGEM3FlagModel  # noqa: E402
from rag_retriever import HybridRetriever  # noqa: E402

CATEGORIES = ["exact", "paraphrase", "symptom", "offtopic"]
RETRIEVAL_CATEGORIES = ["exact", "paraphrase", "symptom"]

INDEX_PATH = os.path.join(ROOT_DIR, "kb", "index", "recall")
LOCAL_MODEL_PATH = os.path.join(ROOT_DIR, "models", "bge-m3")


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_case(retriever, case, top_k, use_hyde, use_rerank, use_tfidf, use_sparse=True):
    results = retriever.retrieve(
        case["query"], top_k=top_k, use_hyde=use_hyde, use_rerank=use_rerank,
        use_tfidf=use_tfidf, use_sparse=use_sparse,
    )
    expected = case.get("expected", "")
    rank = 0
    for i, c in enumerate(results):
        if c["injury"] == expected:
            rank = i + 1
            break
    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "expected": expected,
        "rank": rank,
        "top_candidates": [c["injury"] for c in results],
    }


def run_case_tfidf(retriever, case, top_k):
    """纯 char-TF-IDF 基线：只按字符级 TF-IDF 双通道排序，不用 dense/sparse。"""
    order = retriever._tfidf_order(case["query"])
    expected = case.get("expected", "")
    rank = 0
    for i, name in enumerate(order[:top_k]):
        if name == expected:
            rank = i + 1
            break
    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "expected": expected,
        "rank": rank,
        "top_candidates": order[:top_k],
    }


def _dcg(rank, k):
    return 1.0 / math.log2(rank + 1) if 0 < rank <= k else 0.0


def retrieval_metrics(results, k):
    has_answer = [r for r in results if r["expected"]]
    if not has_answer:
        return 0.0, 0.0, 0.0
    recall = sum(1 for r in has_answer if 0 < r["rank"] <= k) / len(has_answer)
    mrr = sum((1.0 / r["rank"] if 0 < r["rank"] <= k else 0.0) for r in has_answer) / len(has_answer)
    ndcg = sum(_dcg(r["rank"], k) for r in has_answer) / len(has_answer)
    return recall, mrr, ndcg


def print_report(results, k, title):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)
    for cat in RETRIEVAL_CATEGORIES:
        sub = [r for r in results if r["category"] == cat]
        if not sub:
            continue
        r, m, n = retrieval_metrics(sub, k)
        print("  [{:10s}] n={:3d}  Recall@{}={:.3f}  MRR@{}={:.3f}  nDCG@{}={:.3f}".format(
            cat, len(sub), k, r, k, m, k, n))
    overall = [r for r in results if r["category"] in RETRIEVAL_CATEGORIES]
    r, m, n = retrieval_metrics(overall, k)
    print("  [{:10s}] n={:3d}  Recall@{}={:.3f}  MRR@{}={:.3f}  nDCG@{}={:.3f}".format(
        "检索汇总", len(overall), k, r, k, m, k, n))


def print_failures(results, k):
    miss = [r for r in results if r["expected"] and not (0 < r["rank"] <= k)]
    if not miss:
        return
    print("\n检索未命中明细（Recall 缺口）：")
    for r in miss:
        print("  [{}] {} -> 期望:{} | 实际Top{}:{}".format(
            r["id"], r["query"], r["expected"], k, r["top_candidates"]))


def main():
    # 位置参数与 flag 分离：flag 一律 `--` 开头，位置参数是 [path] [top_k]。
    pos_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = pos_args[0] if pos_args else os.path.join(EVAL_DIR, "eval_queries_v2.json")
    k = int(pos_args[1]) if len(pos_args) > 1 else 3
    use_hyde = "--hyde" in sys.argv
    use_rerank = "--rerank" in sys.argv
    use_tfidf = "--no-tfidf" not in sys.argv
    use_cpu = "--cpu" in sys.argv
    use_tfidf_only = "--tfidf-only" in sys.argv
    use_dense_only = "--dense-only" in sys.argv

    model_path = LOCAL_MODEL_PATH if os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")) else "BAAI/bge-m3"
    if use_tfidf_only:
        model = None  # 纯 char-TF-IDF 基线无需 embedding 模型
    else:
        model = BGEM3FlagModel(model_path, use_fp16=not use_cpu, devices=["cpu"] if use_cpu else None)
    retriever = HybridRetriever.load(INDEX_PATH, model)

    cases = load_cases(path)

    # --dense-only：三组通道消融（Dense / Dense+BM25 / Dense+BM25+TF-IDF），各输出 Recall@k/MRR@k/nDCG@k
    if use_dense_only:
        groups = [
            ("Dense", {"use_sparse": False, "use_tfidf": False}),
            ("Dense+BM25(Sparse)", {"use_sparse": True, "use_tfidf": False}),
            ("Dense+BM25+TF-IDF", {"use_sparse": True, "use_tfidf": True}),
        ]
        print("评测集：{} 条，Top-K={}，通道消融（{} 组），HyDE={}，rerank={}".format(
            len(cases), k, len(groups), use_hyde, use_rerank))
        for label, cfg in groups:
            results = [run_case(retriever, c, k, use_hyde, use_rerank,
                                use_tfidf=cfg["use_tfidf"], use_sparse=cfg["use_sparse"])
                       for c in cases]
            print_report(results, k, f"通道消融：{label}")
        return

    if use_tfidf_only:
        channels = ["char-TF-IDF"]
        title = "字符级 TF-IDF 基线（单路）"
    else:
        channels = ["dense", "sparse"] + (["char-TF-IDF"] if use_tfidf else [])
        title = "BGE-M3 混合检索(RRF: " + "+".join(channels) + ")"
    print("评测集：{} 条，Top-K={}，通道=[{}]，HyDE={}，rerank={}".format(
        len(cases), k, "+".join(channels), use_hyde, use_rerank))

    if use_tfidf_only:
        results = [run_case_tfidf(retriever, c, k) for c in cases]
    else:
        results = [run_case(retriever, c, k, use_hyde, use_rerank, use_tfidf) for c in cases]
    print_report(results, k, title)
    print_failures(results, k)


if __name__ == "__main__":
    main()
