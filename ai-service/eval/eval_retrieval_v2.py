# -*- coding: utf-8 -*-
"""
阶段1：检索评测脚本 v2 —— 标准 IR 指标
============================================
在旧版"最终答对率"基础上，补齐检索侧标准指标：
  - Recall@k / Hit@k ：Top-k 是否包含正确答案
  - MRR@k           ：正确答案排名的倒数均值
  - nDCG@k          ：排序质量（单相关文档场景 IDCG=1）

决策侧指标（沿用旧口径）：
  - 最终答对率：decide_match 判定后的伤情是否等于期望
  - 拒答率    ：offtopic 应拒答，实际拒答的比例

用法：python eval/eval_retrieval_v2.py [eval_queries_v2.json]
"""
import json
import math
import os
import sys
import types
import warnings

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(EVAL_DIR, ".."))


def _install_web_stubs():
    """评测只依赖检索核心，用空壳替代 flask/gevent，避免启动 Web 服务。"""
    for mod_name in ("flask", "flask_cors", "gevent", "gevent.pywsgi"):
        mod = types.ModuleType(mod_name)
        mod.__path__ = []
        sys.modules[mod_name] = mod
    flask_mod = sys.modules["flask"]
    flask_mod.Flask = type("FlaskStub", (), {
        "__init__": lambda self, *a, **k: None,
        "route": lambda self, *a, **k: (lambda f: f),
    })
    flask_mod.request = None
    flask_mod.jsonify = lambda *a, **k: None
    sys.modules["flask_cors"].CORS = lambda *a, **k: None
    sys.modules["gevent.pywsgi"].WSGIServer = object


_install_web_stubs()
import app as svc  # noqa: E402

CATEGORIES = ["exact", "paraphrase", "symptom", "offtopic"]
# 有正确答案的类别参与检索指标；offtopic 只参与拒答指标
RETRIEVAL_CATEGORIES = ["exact", "paraphrase", "symptom"]


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_case(case, top_k):
    candidates = svc.retrieve_candidates(case["query"], top_k=top_k)
    decision = svc.decide_match(candidates)
    expected = case.get("expected", "")

    # 正确答案在候选中的排名（1-based，0 表示未命中）
    rank = 0
    for i, c in enumerate(candidates):
        if c["injury"] == expected:
            rank = i + 1
            break

    predicted = decision.get("injury", "") if decision["matched"] else ""
    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "expected": expected,
        "predicted": predicted,
        "rank": rank,
        "top_k": top_k,
        "top_candidates": [c["injury"] for c in candidates],
        "matched": decision["matched"],
        "score": decision.get("score"),
        "reason": decision.get("reason"),
    }


def _dcg(rank, k):
    return 1.0 / math.log2(rank + 1) if 0 < rank <= k else 0.0


def retrieval_metrics(results, k):
    """对'有正确答案'的样本计算 Recall@k / MRR@k / nDCG@k。"""
    has_answer = [r for r in results if r["expected"]]
    if not has_answer:
        return 0.0, 0.0, 0.0
    recall = sum(1 for r in has_answer if 0 < r["rank"] <= k) / len(has_answer)
    mrr = sum((1.0 / r["rank"] if 0 < r["rank"] <= k else 0.0) for r in has_answer) / len(has_answer)
    ndcg = sum(_dcg(r["rank"], k) for r in has_answer) / len(has_answer)
    return recall, mrr, ndcg


def decision_metrics(results):
    """最终决策正确率（有答案的答对率 + offtopic 的拒答率）。"""
    has_answer = [r for r in results if r["expected"]]
    offtopic = [r for r in results if not r["expected"]]
    ans_acc = sum(1 for r in has_answer if r["predicted"] == r["expected"]) / len(has_answer) if has_answer else 0.0
    reject = sum(1 for r in offtopic if not r["matched"]) / len(offtopic) if offtopic else 0.0
    return ans_acc, reject


def print_report(results, k, title):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)
    for cat in RETRIEVAL_CATEGORIES:
        sub = [r for r in results if r["category"] == cat]
        if not sub:
            continue
        r, m, n = retrieval_metrics(sub, k)
        print(f"  [{cat:10s}] n={len(sub):3d}  Recall@{k}={r:.3f}  MRR@{k}={m:.3f}  nDCG@{k}={n:.3f}")

    overall = [r for r in results if r["category"] in RETRIEVAL_CATEGORIES]
    r, m, n = retrieval_metrics(overall, k)
    print(f"  [{'检索汇总':8s}] n={len(overall):3d}  Recall@{k}={r:.3f}  MRR@{k}={m:.3f}  nDCG@{k}={n:.3f}")

    ans_acc, reject = decision_metrics(results)
    print("\n  决策侧：最终答对率={:.3f}  无关输入拒答率={:.3f}".format(ans_acc, reject))


def print_failures(results, k):
    """打印检索未命中的样本（用于定位薄弱环节）。"""
    miss = [r for r in results if r["expected"] and not (0 < r["rank"] <= k)]
    if not miss:
        return
    print("\n检索未命中明细（Recall 缺口）：")
    for r in miss:
        print("  [{}] {} -> 期望:{} | 实际Top{}:{}".format(
            r["id"], r["query"], r["expected"], k, r["top_candidates"]))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(EVAL_DIR, "eval_queries_v2.json")
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    svc.load_model_and_knowledge()
    cases = load_cases(path)
    print("评测集：{} 条，伤情类型数：{}，Top-K={}".format(len(cases), len(svc.injury_names), k))

    results = [run_case(c, k) for c in cases]
    print_report(results, k, "当前检索基线（字符级 TF-IDF 双通道）")
    print_failures(results, k)


if __name__ == "__main__":
    main()
