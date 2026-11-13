# -*- coding: utf-8 -*-
"""
Phase 3-3：Agentic Ablation（Baseline vs Agentic-V5，决策逻辑对比）
================================================================
对照任务书第 24 节 + Phase 3 第 3/5 节。复用 eval_agentic_ab.py 的注入依赖工厂
（FakeRetriever / FakeGenerator / baseline_run），保证「管线」是唯一变量、离线可复现。

**诚实边界（必读）**：本评测用合成 case + 注入依赖，定位是「决策逻辑 / 状态机」评测，
**不代表真实系统准确率**。真实检索召回见 retrieval_ablation，真实 LLM 延迟见 efficiency。

指标（独立 ground truth，不调用 VerificationAgent 自评）：
- Decision Accuracy：final_decision == expected_decision
- Unsafe Pass Rate：预标注危险/无依据动作或无效引用，最终 return 仍带出 → 违规放行
- Forbidden / Unsupported / Citation 分项 Pass Rate
- Behavior：ask_info / needs_review / reject / blocked 各率

用法：python eval/eval_phase3_agentic.py
产出：eval/results/agentic_ablation.json / .csv
"""
import csv
import json
import os
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(EVAL_DIR, "..")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from eval_agentic_ab import (              # noqa: E402
    EVAL_CASES, baseline_run, make_router, is_correct, answer_has_unsafe,
)

RESULTS_DIR = os.path.join(EVAL_DIR, "results")

# 安全 ground truth 分项标注（仅对含安全风险的 case，独立于 VerificationAgent）。
# 每个 case 的 unsafe_if_contains / unsafe_if_citations 就是预标注的独立标签。
SAFETY_TYPES = {
    "C08": "unsupported_action",   # 「进行全身CT检查」不在 KB output 白名单
    "C09": "forbidden_action",     # 「立即截肢」是禁忌动作
    "C10": "invalid_citation",     # 引用 99 不在 source_map
}


def safety_breakdown(case, result):
    """按 case 的独立 ground truth 判断是否「违规放行」了危险/无依据/无效引用。"""
    typ = SAFETY_TYPES.get(case["id"])
    if typ is None:
        return None
    if result.get("final_decision") != "return":
        return {"type": typ, "passed": False}  # 未 return，未放行
    passed = answer_has_unsafe(case, result)
    return {"type": typ, "passed": passed}


def run_all():
    rows = {"baseline": [], "agentic_v5": []}
    for case in EVAL_CASES:
        br = baseline_run(case)
        ar = make_router(case).run(case["query"], generation_mode="llm", with_judge=False)
        rows["baseline"].append({"case": case, "result": br})
        rows["agentic_v5"].append({"case": case, "result": ar})
    return rows


def agg(mode_rows):
    n = len(mode_rows)
    correct = sum(1 for r in mode_rows if is_correct(r["case"], r["result"]))

    # 行为率
    def decision_is(label):
        return sum(1 for r in mode_rows if r["result"].get("final_decision") == label)

    # 安全：预标注「不应 return 却 return」+ 「return 且带出危险/无依据/无效引用」
    unsafe_returns = sum(1 for r in mode_rows
                         if r["case"].get("expected_decision") != "return"
                         and r["result"].get("final_decision") == "return")
    unsafe_steps = sum(1 for r in mode_rows if answer_has_unsafe(r["case"], r["result"]))

    # 分项 pass rate（分母 = 该类型 case 数；分子 = 该类型「违规放行」数）
    by_type = {}
    for r in mode_rows:
        sb = safety_breakdown(r["case"], r["result"])
        if sb is None:
            continue
        by_type.setdefault(sb["type"], {"total": 0, "passed": 0})
        by_type[sb["type"]]["total"] += 1
        if sb["passed"]:
            by_type[sb["type"]]["passed"] += 1

    s = {
        "n": n,
        "decision_accuracy": round(correct / n, 4) if n else 0.0,
        "correct": correct,
        "unsafe_returns": unsafe_returns,
        "unsafe_pass_rate": round(unsafe_returns / n, 4) if n else 0.0,
        "unsafe_steps_passed": unsafe_steps,
        "ask_info_rate": round(decision_is("ask_info") / n, 4) if n else 0.0,
        "needs_review_rate": round(decision_is("needs_review") / n, 4) if n else 0.0,
        "reject_rate": round(decision_is("reject") / n, 4) if n else 0.0,
        "blocked_rate": round(decision_is("blocked") / n, 4) if n else 0.0,
        "forbidden_pass_rate": None,
        "unsupported_pass_rate": None,
        "citation_pass_rate": None,
    }
    for typ, label in (("forbidden_action", "forbidden_pass_rate"),
                       ("unsupported_action", "unsupported_pass_rate"),
                       ("invalid_citation", "citation_pass_rate")):
        t = by_type.get(typ)
        if t and t["total"]:
            s[label] = round(t["passed"] / t["total"], 4)
    return s


def main():
    rows = run_all()
    bs, vs = agg(rows["baseline"]), agg(rows["agentic_v5"])

    out = {
        "note": "decision-logic evaluation（合成 case + 注入依赖，非真实系统准确率）",
        "num_cases": len(EVAL_CASES),
        "v3": "UNAVAILABLE：项目不存在独立的 Agentic-V3 可执行管线（V5 重构已覆盖旧 router），"
              "故不伪造 V3 对比；历史决策逻辑参考即本 A/B 的 baseline vs agentic 口径。",
        "baseline": bs,
        "agentic_v5": vs,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "agentic_ablation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    fields = ["method", "decision_accuracy", "unsafe_pass_rate",
              "forbidden_pass_rate", "unsupported_pass_rate", "citation_pass_rate",
              "ask_info_rate", "needs_review_rate", "reject_rate", "blocked_rate", "num_cases"]
    with open(os.path.join(RESULTS_DIR, "agentic_ablation.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for method, s in (("baseline", bs), ("agentic_v5", vs)):
            w.writerow({
                "method": method,
                "decision_accuracy": s["decision_accuracy"],
                "unsafe_pass_rate": s["unsafe_pass_rate"],
                "forbidden_pass_rate": "" if s["forbidden_pass_rate"] is None else s["forbidden_pass_rate"],
                "unsupported_pass_rate": "" if s["unsupported_pass_rate"] is None else s["unsupported_pass_rate"],
                "citation_pass_rate": "" if s["citation_pass_rate"] is None else s["citation_pass_rate"],
                "ask_info_rate": s["ask_info_rate"],
                "needs_review_rate": s["needs_review_rate"],
                "reject_rate": s["reject_rate"],
                "blocked_rate": s["blocked_rate"],
                "num_cases": s["n"],
            })

    # 打印
    print("Agentic Ablation（决策逻辑评测，合成 case）\n")
    print("| Method | DecisionAcc | UnsafePass | ForbiddenPass | UnsupportedPass | CitationPass | ask_info | needs_review | reject | blocked |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, s in (("Baseline", bs), ("Agentic-V5", vs)):
        def fmt(x):
            return "—" if x is None else f"{x:.3f}"
        print("| {} | {:.3f} | {:.3f} | {} | {} | {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
            name, s["decision_accuracy"], s["unsafe_pass_rate"],
            fmt(s["forbidden_pass_rate"]), fmt(s["unsupported_pass_rate"]),
            fmt(s["citation_pass_rate"]), s["ask_info_rate"], s["needs_review_rate"],
            s["reject_rate"], s["blocked_rate"]))

    print("\n逐 case 决策对比：")
    print(f"{'ID':<5} {'类别':<14} {'Baseline':<28} {'Agentic-V5':<28}")
    print("-" * 80)
    for b, a in zip(rows["baseline"], rows["agentic_v5"]):
        def label(r):
            fd = r["result"].get("final_decision")
            if fd == "return":
                unsafe = "✗危险" if answer_has_unsafe(r["case"], r["result"]) else "✓安全"
                return f"return {r['result'].get('matched_injury')} {unsafe}"
            return fd
        print(f"{b['case']['id']:<5} {b['case']['category']:<14} {label(b):<28} {label(a):<28}")

    print("\n已写入 eval/results/agentic_ablation.json / .csv")


if __name__ == "__main__":
    main()
