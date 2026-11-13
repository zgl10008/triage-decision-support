# -*- coding: utf-8 -*-
"""
Phase 3-5：Efficiency / Latency / Cost Evaluation
================================================================
V5 增加了 Situation / Evidence / Verification / Repair，不能只看准确率。这里量化：
- 结构化开销（确定性、可复现）：agent_steps / retrieval_attempts / replan_count /
  llm_call_count（逻辑计数）/ latency_ms（编排开销，不含 LLM 推理）。
- 真实延迟抽查（--real）：真实 BGE-M3 检索 + 真实 Ollama 生成，baseline(/match 逻辑)
  vs V5 的端到端墙钟延迟。n 很小，只作锚点，不宣称统计显著。

用法：
  python eval/eval_phase3_efficiency.py            # 仅结构化开销（快）
  python eval/eval_phase3_efficiency.py --real     # 追加真实 Ollama 延迟抽查
产出：eval/results/efficiency_evaluation.json / .csv
"""
import csv
import json
import os
import sys
import time

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(EVAL_DIR, "..")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from agentic_router import AgenticRouter                    # noqa: E402
from agentic_situation import SituationAssessmentAgent      # noqa: E402
from agentic_rewrite import QueryRewriter                    # noqa: E402
from agentic_config import HYBRID_THRESHOLD                 # noqa: E402
from eval_agentic_ab import SOURCE_MAP, _INJURY_NAMES        # noqa: E402

RESULTS_DIR = os.path.join(EVAL_DIR, "results")
INDEX_PATH = os.path.join(ROOT_DIR, "kb", "index", "recall")
LOCAL_MODEL_PATH = os.path.join(ROOT_DIR, "models", "bge-m3")


class Counter:
    def __init__(self):
        self.situation = 0
        self.rewrite = 0
        self.generation = 0


class FakeGenerator:
    def __init__(self, gen_mode, counter):
        self.gen_mode = gen_mode
        self.counter = counter

    def build_context(self, injury):
        return ('ctx', SOURCE_MAP)

    def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
        self.counter.generation += 1
        steps = {
            'good': [{'step': 1, 'action': '立即止血包扎', 'citations': [1]}],
            'unsupported': [{'step': 1, 'action': '立即止血包扎', 'citations': [1]},
                            {'step': 2, 'action': '进行全身CT检查', 'citations': [1]}],
        }.get(self.gen_mode, [{'step': 1, 'action': '立即止血包扎', 'citations': [1]}])
        return {'injury': injury, 'mode': mode, 'steps': steps,
                'sources': [dict(ref=1, **SOURCE_MAP[1])],
                'faithfulness': {'overall_faithful': 1.0}}


def _situation_llm(counter, results):
    def fn(prompt, **kw):
        counter.situation += 1
        marker = "【现场伤情描述】"
        q = prompt.split(marker, 1)[1].splitlines()[0].strip() if marker in prompt else ""
        if q in results:
            return results[q]
        raise ValueError("LLM down")
    return fn


def _rewrite_llm(counter, target):
    def fn(prompt, **kw):
        counter.rewrite += 1
        return '{{"rewritten_query":"{}"}}'.format(target)
    return fn


# (name, query, retriever_spec, gen_mode, situation_results, rewrite_target)
# retriever_spec: 'fast' | 'gray'
STRUCT_SCENARIOS = [
    ("fast_path", "头皮裂伤", "fast", "good", {}, None),
    ("complex_rewrite", "烧烫伤后出现水泡", "gray", "good",
     {"烧烫伤后出现水泡": '{"status":"sufficient","reason":"描述完整","missing_information":[]}'},
     "烧烫伤"),
    ("repair_path", "头皮裂伤", "fast", "unsupported", {}, None),
]


def build_router(scn, counter):
    query, retr_spec, gen_mode, sit_results, rewrite_target = scn[1], scn[2], scn[3], scn[4], scn[5]

    def retriever(q, top_k=3):
        if retr_spec == 'gray':
            if q == '烧烫伤':
                return [{'injury': '烧烫伤', 'score': 0.82}]
            return [{'injury': '烧烫伤', 'score': 0.52}]
        return [{'injury': '头皮裂伤', 'score': 0.90}, {'injury': '脑挫裂伤', 'score': 0.30}]

    rewriter = QueryRewriter(llm_fn=_rewrite_llm(counter, rewrite_target)) if rewrite_target \
        else QueryRewriter(llm_fn=(lambda *a, **k: (_ for _ in ()).throw(ValueError("down"))))
    situation = SituationAssessmentAgent(
        injury_names=_INJURY_NAMES, llm_fn=_situation_llm(counter, sit_results))
    return AgenticRouter(retriever=retriever, generator=FakeGenerator(gen_mode, counter),
                         situation_agent=situation, rewriter=rewriter)


def struct_overhead():
    rows = []
    for (name, query, retr, gen_mode, sit, rw) in STRUCT_SCENARIOS:
        counter = Counter()
        router = build_router((name, query, retr, gen_mode, sit, rw), counter)
        # 预热一次让 import / 类初始化不摊进 latency
        router.run(query, generation_mode='llm', with_judge=False)
        counter = Counter()
        router = build_router((name, query, retr, gen_mode, sit, rw), counter)
        t0 = time.perf_counter()
        r = router.run(query, generation_mode='llm', with_judge=False)
        latency = (time.perf_counter() - t0) * 1000
        tr = r.get("trace") or {}
        rows.append({
            "scenario": name,
            "final_decision": r.get("final_decision"),
            "latency_ms": round(latency, 2),
            "agent_steps": tr.get("total_steps", 0),
            "retrieval_attempts": tr.get("retrieval_attempt_count", 0),
            "replan_count": tr.get("replan_count", 0),
            "llm_calls_situation": counter.situation,
            "llm_calls_rewrite": counter.rewrite,
            "llm_calls_generation": counter.generation,
            "llm_calls_total": counter.situation + counter.rewrite + counter.generation,
            "note": "orchestration overhead（LLM 推理耗时未计入，见 --real 抽查）",
        })
    return rows


def real_spot_check():
    """真实 BGE-M3 + 真实 Ollama，baseline(/match 逻辑) vs V5，n=小样本锚点。"""
    from FlagEmbedding import BGEM3FlagModel
    from rag_retriever import HybridRetriever
    from rag_generator import GroundedGenerator

    model = BGEM3FlagModel(LOCAL_MODEL_PATH, use_fp16=True)
    retriever = HybridRetriever.load(INDEX_PATH, model)
    generator = GroundedGenerator()

    def baseline(query):
        t0 = time.perf_counter()
        cands = retriever.retrieve(query, top_k=3)
        if not cands or cands[0]["score"] < HYBRID_THRESHOLD:
            return {"decision": "reject", "latency_ms": (time.perf_counter() - t0) * 1000}
        matched = cands[0]["injury"]
        gen = generator.generate(matched, mode="llm", with_judge=False)
        return {"decision": "return", "matched": matched,
                "latency_ms": (time.perf_counter() - t0) * 1000, "mode": gen.get("mode")}

    # HybridRetriever 实例不可调用（无 __call__），router._retrieve 用 self.retriever(query, top_k=...)
    # 函数式调用，故包成 lambda；否则 TypeError 被吞成 [] → 秒级误拒（0.5ms 假快）。
    router = AgenticRouter(retriever=lambda q, top_k=3: retriever.retrieve(q, top_k=top_k),
                           generator=generator)

    def v5(query):
        t0 = time.perf_counter()
        r = router.run(query, generation_mode="llm", with_judge=False)
        return {"decision": r.get("final_decision"), "matched": r.get("matched_injury"),
                "latency_ms": (time.perf_counter() - t0) * 1000, "mode": r.get("mode")}

    queries = ["头皮裂伤", "脑袋被坠物划破流血"]
    rows = []
    for q in queries:
        for name, fn in (("baseline", baseline), ("v5", v5)):
            try:
                out = fn(q)
            except Exception as e:  # noqa: BLE001
                out = {"decision": "error", "latency_ms": None, "error": str(e)[:80]}
            rows.append({"scenario": f"real_{name}", "query": q, **out,
                         "note": "real Ollama latency（deepseek-r1:1.5b，含 LLM 推理）"})
    return rows


def main():
    use_real = "--real" in sys.argv
    rows = struct_overhead()
    if use_real:
        try:
            rows += real_spot_check()
        except Exception as e:  # noqa: BLE001
            rows.append({"scenario": "real_spot_check", "error": str(e)[:120],
                         "note": "real Ollama spot check unavailable"})

    out = {"struct_overhead": rows, "real_spot_check_included": use_real}
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "efficiency_evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    fieldnames = ["scenario", "query", "decision", "latency_ms", "agent_steps",
                  "retrieval_attempts", "replan_count", "llm_calls_total", "note"]
    with open(os.path.join(RESULTS_DIR, "efficiency_evaluation.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    print("Efficiency Evaluation（结构化开销，编排耗时、LLM 推理未计入）\n")
    print(f"{'场景':<16} {'决策':<10} {'latency_ms':>12} {'steps':>6} {'retrieval':>10} {'replan':>7} {'llm_calls':>9}")
    print("-" * 74)
    for r in rows:
        if r.get("scenario", "").startswith("real_"):
            continue
        print(f"{r['scenario']:<16} {r['final_decision']:<10} {r['latency_ms']:>12.2f} "
              f"{r['agent_steps']:>6} {r['retrieval_attempts']:>10} {r['replan_count']:>7} "
              f"{r['llm_calls_total']:>9}")
    if use_real:
        print("\n真实 Ollama 延迟抽查（n=小样本锚点，含 LLM 推理）：")
        for r in rows:
            if r.get("scenario", "").startswith("real_"):
                print(f"  {r['scenario']:<14} {r.get('query',''):<16} 决策={r.get('decision')} "
                      f"latency={r.get('latency_ms')} ms")
    print("\n已写入 eval/results/efficiency_evaluation.json / .csv")


if __name__ == "__main__":
    main()
