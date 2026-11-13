# -*- coding: utf-8 -*-
"""
决策阈值标定（阶段2 接入服务的配套）
============================================
问题：HybridRetriever 用 RRF 决定排序，但 decide_match 的阈值/margin 原本是为
char-TF-IDF 余弦调的。RRF 分量级 ~0.05，不能直接复用旧阈值。

方案：排序用 RRF，置信度用 dense 余弦（[0,1] 可解释），本脚本用评测集实证
dense 置信度的分布，为 decide_match 选定 阈值 + 分数差 参数。

用法：python eval/calibrate_decision.py [eval_queries_v2.json]
输出：各类别（exact/paraphrase/symptom/offtopic）Top-1 dense 置信度分布 + 分数差分布
"""
import json
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

INDEX_PATH = os.path.join(ROOT_DIR, "kb", "index", "recall")
LOCAL_MODEL_PATH = os.path.join(ROOT_DIR, "models", "bge-m3")
TOP_K = 3


def stats(vals):
    vals = sorted(vals)
    n = len(vals)
    if n == 0:
        return "n=0"
    mean = sum(vals) / n
    return (f"n={n:3d}  min={vals[0]:.3f}  p25={vals[n//4]:.3f}  mean={mean:.3f}  "
            f"median={vals[n//2]:.3f}  p75={vals[(3*n)//4]:.3f}  max={vals[-1]:.3f}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(EVAL_DIR, "eval_queries_v2.json")
    cases = json.load(open(path, encoding="utf-8"))

    model_path = LOCAL_MODEL_PATH if os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")) else "BAAI/bge-m3"
    model = BGEM3FlagModel(model_path, use_fp16=True)
    retriever = HybridRetriever.load(INDEX_PATH, model)

    by_cat = {}
    for c in cases:
        results = retriever.retrieve(c["query"], top_k=TOP_K)
        top1 = results[0]
        top2 = results[1] if len(results) > 1 else None
        gap = top1["score"] - top2["score"] if top2 else 1.0
        rrf_gap = top1.get("rrf", 0.0) - top2.get("rrf", 0.0) if top2 else 0.0
        cat = c["category"]
        by_cat.setdefault(cat, []).append({
            "id": c["id"],
            "query": c["query"],
            "expected": c.get("expected", ""),
            "top1": top1["injury"],
            "top1_score": top1["score"],
            "top1_rrf": top1.get("rrf", 0.0),
            "gap": round(gap, 4),
            "rrf_gap": round(rrf_gap, 6),
            "hit": top1["injury"] == c.get("expected", ""),
        })

    print("=" * 70)
    print("HybridRetriever 各类别 Top-1 dense 置信度分布（score = dense 余弦）")
    print("=" * 70)
    for cat in ["exact", "paraphrase", "symptom", "offtopic"]:
        rows = by_cat.get(cat, [])
        if not rows:
            continue
        scores = [r["top1_score"] for r in rows]
        gaps = [r["gap"] for r in rows]
        rrf_gaps = [r["rrf_gap"] for r in rows]
        hits = sum(1 for r in rows if r["hit"])
        print(f"\n[{cat}] 命中={hits}/{len(rows)}")
        print("  Top-1 置信度: " + stats(scores))
        print("  dense gap    : " + stats(gaps))
        print("  RRF gap      : " + stats(rrf_gaps))

    # 明细：offtopic 误收（dense >= 0.55 会被阈值放行）与 symptom 漏收（dense < 0.55）
    print("\n" + "=" * 70)
    print("offtopic 中 dense >= 0.55 的误收明细：")
    print("=" * 70)
    for r in by_cat.get("offtopic", []):
        if r["top1_score"] >= 0.55:
            print(f"  {r['query']!r:20} -> {r['top1']}  dense={r['top1_score']:.3f}  rrf_gap={r['rrf_gap']:.5f}")
    print("\nsymptom 中 dense < 0.55 的漏收明细：")
    for r in by_cat.get("symptom", []):
        if r["top1_score"] < 0.55:
            print(f"  {r['query']!r:20} -> {r['top1']}  dense={r['top1_score']:.3f}  (期望 {r['expected']})")

    # 阈值扫参：报告不同阈值下的 命中/误收 情况
    print("\n" + "=" * 70)
    print("阈值扫参（阈值 T：Top-1 dense 置信度 >= T 才通过；offtopic 应被拒绝）")
    print("=" * 70)
    print(f"{'T':>6} | {'exact命中':>8} {'para命中':>8} {'symp命中':>8} {'offtopic误收':>11}")
    for T in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]:
        exact_h = sum(1 for r in by_cat.get("exact", []) if r["top1_score"] >= T)
        para_h = sum(1 for r in by_cat.get("paraphrase", []) if r["top1_score"] >= T)
        symp_h = sum(1 for r in by_cat.get("symptom", []) if r["top1_score"] >= T)
        off_wrong = sum(1 for r in by_cat.get("offtopic", []) if r["top1_score"] >= T)
        print(f"{T:>6.2f} | {exact_h:>6}/{len(by_cat['exact'])} {para_h:>6}/{len(by_cat['paraphrase'])} "
              f"{symp_h:>6}/{len(by_cat['symptom'])} {off_wrong:>7}/{len(by_cat['offtopic'])}")


if __name__ == "__main__":
    main()
