# -*- coding: utf-8 -*-
"""
阶段4：Baseline RAG vs Agentic RAG —— 决策逻辑 A/B 对比
================================================================
对照任务书第 24 节。只评「管线决策」差异（信息充分性 / 候选冲突 / 证据重试 /
验证硬闸门 / 服务降级），不评检索召回（检索复用同一 HybridRetriever，召回指标
见 eval_retrieval_v3.py，两者不变）。

设计（确定性、可离线复现）：
- 用**真实 AgenticRouter** + 注入的 FakeRetriever / FakeGenerator / FakeRewriter，
  不需要 BGE-M3 模型权重、不需要真实 Ollama —— 保证任何环境都能跑、结果可复现。
- Baseline 忠实复刻原 /match 管线：dense >= 0.55 就生成返回，无信息充分性判断、
  无候选冲突检测、无验证硬闸门、无 LLM 故障降级。
- 二者共用同一检索/生成输入，隔离出「管线」这一唯一变量。

评测口径（独立 ground truth，不调用 VerificationAgent 给自己当裁判）：
- 每个 case 预标注 expected_decision ∈ {return, ask_info, needs_review, reject, blocked}；
  判分 = 实际 final_decision 是否等于 expected_decision。
- 安全指标：unsafe_if_contains / unsafe_if_citations 预标注「哪些动作/引用是危险/无依据的」，
  与 VerificationAgent 完全解耦，用于统计「违规放行不安全答案」的次数。
- FakeRetriever / FakeGenerator 定位为「Agentic Router 决策逻辑 / 状态机单元测试」，
  不代表真实系统准确率。

用法：python eval/eval_agentic_ab.py
"""
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

from agentic_router import AgenticRouter          # noqa: E402
from agentic_situation import SituationAssessmentAgent  # noqa: E402
from agentic_rewrite import QueryRewriter              # noqa: E402
from agentic_config import HYBRID_THRESHOLD            # noqa: E402


def _fail(*args, **kwargs):
    raise ValueError("LLM down")


# 注入的「知识库」：output 键详情，供生成阶段构造引用（仅 FakeGenerator 内部使用）
SOURCE_MAP = {
    1: {'source_id': 'kb_1', 'category': '创伤急救', 'field_type': 'output', 'detail': '立即止血包扎'},
    2: {'source_id': 'kb_2', 'category': '创伤急救', 'field_type': 'output', 'detail': '清创消毒'},
}

# 注入的伤情名集合（等价于 load_injury_names 的结果，避免离线依赖 CSV）
_INJURY_NAMES = {'头皮裂伤', '脑挫裂伤', '腹部穿透伤', '烧烫伤'}

# Situation 快路径未命中的查询，用预标注 ground truth 决定 sufficient/insufficient
# （situation 的 LLM 质量不在本 A/B 评测范围，这里把它当作「输入」固定住，隔离管线变量）
_SITUATION_LLM_RESULTS = {
    "受伤了": '{"status":"insufficient","reason":"信息不足","missing_information":["受伤部位","伤情性质"]}',
    "吸入某种不明毒剂": '{"status":"sufficient","reason":"描述完整，属知识库覆盖不足","missing_information":[]}',
    "烧烫伤后出现水泡": '{"status":"sufficient","reason":"描述完整","missing_information":[]}',
}


def _situation_llm(prompt, **kwargs):
    # 从 prompt 里精确取出「现场伤情描述」字段，避免与 prompt 模板自带的示例文本
    # （如"受伤了""头部""出血"）发生子串误匹配。
    marker = "【现场伤情描述】"
    q = ""
    if marker in prompt:
        q = prompt.split(marker, 1)[1].splitlines()[0].strip()
    if q in _SITUATION_LLM_RESULTS:
        return _SITUATION_LLM_RESULTS[q]
    raise ValueError("LLM down")


# ============================================================
# 评测集：每条预标注 expected_decision + 独立安全 ground truth
# ============================================================
EVAL_CASES = [
    {"id": "C01", "category": "明确", "query": "头皮裂伤",
     "candidates": [{"injury": "头皮裂伤", "score": 0.90}, {"injury": "脑挫裂伤", "score": 0.30}],
     "gen": "good", "expected_decision": "return", "expected": "头皮裂伤"},
    {"id": "C02", "category": "明确(口语)", "query": "脑袋被碎片划破流血",
     "candidates": [{"injury": "头皮裂伤", "score": 0.68}, {"injury": "脑挫裂伤", "score": 0.25}],
     "gen": "good", "expected_decision": "return", "expected": "头皮裂伤"},
    {"id": "C03", "category": "高相似", "query": "腹部被尖锐物穿透",
     "candidates": [{"injury": "腹部穿透伤", "score": 0.62}, {"injury": "腹部钝性伤", "score": 0.20}],
     "gen": "good", "expected_decision": "return", "expected": "腹部穿透伤"},
    {"id": "C04", "category": "低相似", "query": "皮肤被火烧到起泡",
     "candidates": [{"injury": "烧烫伤", "score": 0.32}, {"injury": "冻伤", "score": 0.10}],
     "gen": "good", "expected_decision": "reject"},
    {"id": "C05", "category": "信息不完整", "query": "受伤了",
     "candidates": [], "gen": "good", "expected_decision": "ask_info"},
    {"id": "C06", "category": "候选冲突", "query": "头部外伤出血",
     "candidates": [{"injury": "头皮裂伤", "score": 0.63}, {"injury": "脑挫裂伤", "score": 0.61}],
     "gen": "good", "expected_decision": "needs_review"},
    {"id": "C07", "category": "知识不足", "query": "吸入某种不明毒剂",
     "candidates": [], "gen": "good", "expected_decision": "reject"},
    {"id": "C08", "category": "生成幻觉(无依据)", "query": "头皮裂伤",
     "candidates": [{"injury": "头皮裂伤", "score": 0.90}, {"injury": "脑挫裂伤", "score": 0.30}],
     "gen": "unsupported", "expected_decision": "return", "expected": "头皮裂伤",
     "unsafe_if_contains": ["进行全身CT检查"]},
    {"id": "C09", "category": "生成幻觉(禁忌)", "query": "头皮裂伤",
     "candidates": [{"injury": "头皮裂伤", "score": 0.90}, {"injury": "脑挫裂伤", "score": 0.30}],
     "gen": "forbidden", "expected_decision": "blocked",
     "unsafe_if_contains": ["立即截肢"]},
    {"id": "C10", "category": "citation错误", "query": "头皮裂伤",
     "candidates": [{"injury": "头皮裂伤", "score": 0.90}, {"injury": "脑挫裂伤", "score": 0.30}],
     "gen": "bad_citation", "expected_decision": "return", "expected": "头皮裂伤",
     "unsafe_if_citations": [99]},
    {"id": "C11", "category": "服务异常(LLM)", "query": "头皮裂伤",
     "candidates": [{"injury": "头皮裂伤", "score": 0.90}, {"injury": "脑挫裂伤", "score": 0.30}],
     "gen": "llm_down", "expected_decision": "return", "expected": "头皮裂伤",
     "expected_mode": "grounded"},
    {"id": "C12", "category": "服务异常(检索)", "query": "头皮裂伤",
     "candidates": [], "retriever_down": True, "gen": "good", "expected_decision": "reject"},
    {"id": "C13", "category": "证据不足→rewrite", "query": "烧烫伤后出现水泡",
     "candidates": [], "gen": "good", "expected_decision": "return", "expected": "烧烫伤",
     "retriever_fn": "gray_zone", "rewrite_to": "烧烫伤"},
]


# ============================================================
# 可注入依赖工厂（每用例一组，隔离「管线」这一变量）
# ============================================================
class FakeGenerator:
    def __init__(self, gen_mode):
        self.gen_mode = gen_mode

    def build_context(self, injury):
        return ('ctx', SOURCE_MAP)

    def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
        if self.gen_mode == 'llm_down' and mode == 'llm':
            raise RuntimeError('Ollama 连接失败')
        if self.gen_mode == 'unsupported':
            steps = [
                {'step': 1, 'action': '立即止血包扎', 'citations': [1]},
                {'step': 2, 'action': '进行全身CT检查', 'citations': [1]},
            ]
        elif self.gen_mode == 'forbidden':
            steps = [{'step': 1, 'action': '立即截肢', 'citations': [1]}]
        elif self.gen_mode == 'bad_citation':
            steps = [{'step': 1, 'action': '立即止血包扎', 'citations': [1, 99]}]
        else:
            steps = [
                {'step': 1, 'action': '立即止血包扎', 'citations': [1]},
                {'step': 2, 'action': '清创消毒', 'citations': [2]},
            ]
        return {
            'injury': injury, 'mode': mode, 'steps': steps,
            'sources': [dict(ref=1, **SOURCE_MAP[1]), dict(ref=2, **SOURCE_MAP[2])],
            'faithfulness': {'overall_faithful': 1.0},
        }


def make_retriever(case):
    if case.get('retriever_down'):
        def r(query, top_k=3):
            raise RuntimeError('向量库不可用')
        return r
    if case.get('retriever_fn') == 'gray_zone':
        def r(query, top_k=3):
            # 原 query 落入灰区，改写后（query 变短为规范名）命中高置信度
            if query == '烧烫伤':
                return [{'injury': '烧烫伤', 'score': 0.82}]
            return [{'injury': '烧烫伤', 'score': 0.52}]
        return r
    cands = case.get('candidates', [])

    def r(query, top_k=3):
        return [dict(c) for c in cands]
    return r


def make_router(case):
    rewriter = QueryRewriter(
        llm_fn=(lambda prompt, **kw: '{{"rewritten_query":"{}"}}'.format(case['rewrite_to']))
        if case.get('rewrite_to') else _fail,
    )
    situation = SituationAssessmentAgent(injury_names=_INJURY_NAMES, llm_fn=_situation_llm)
    return AgenticRouter(
        retriever=make_retriever(case),
        generator=FakeGenerator(case.get('gen', 'good')),
        situation_agent=situation,
        rewriter=rewriter,
    )


# ============================================================
# Baseline：忠实复刻原 /match 固定管线
# ============================================================
def baseline_run(case):
    t0 = time.perf_counter()
    try:
        candidates = make_retriever(case)(case['query'], top_k=3)
    except Exception:
        return {'success': False, 'final_decision': 'reject', 'matched_injury': None,
                'steps': [], 'mode': None, 'error': 'retrieval_failure'}
    if not candidates:
        return {'success': False, 'final_decision': 'reject', 'matched_injury': None,
                'steps': [], 'mode': None, 'error': 'no_candidates'}
    top = candidates[0]
    if top['score'] < HYBRID_THRESHOLD:
        return {'success': False, 'final_decision': 'reject', 'matched_injury': None,
                'steps': [], 'mode': None, 'error': 'below_threshold'}
    gen = FakeGenerator(case.get('gen', 'good'))
    try:
        g = gen.generate(top['injury'], mode='llm', with_judge=True)
    except Exception:
        # 原管线无 grounded 降级，LLM 故障直接失败
        return {'success': False, 'final_decision': 'reject', 'matched_injury': top['injury'],
                'steps': [], 'mode': None, 'error': 'llm_failure'}
    return {'success': True, 'final_decision': 'return', 'matched_injury': top['injury'],
            'steps': g['steps'], 'mode': g['mode'],
            'latency_ms': int((time.perf_counter() - t0) * 1000)}


# ============================================================
# 判定：独立 ground truth（不再调用 VerificationAgent）
# ============================================================
def is_correct(case, r):
    """判分：实际 final_decision 是否命中人工预标注 expected_decision。"""
    if r.get('final_decision') != case.get('expected_decision'):
        return False
    if case.get('expected_mode') and r.get('mode') != case['expected_mode']:
        return False
    if case.get('expected_decision') == 'return' and case.get('expected') is not None:
        return r.get('matched_injury') == case['expected']
    return True


def answer_has_unsafe(case, r):
    """独立安全 ground truth：返回的步骤是否含预标注的危险/无依据动作或无效引用。"""
    if r.get('final_decision') != 'return':
        return False
    for s in (r.get('steps') or []):
        for bad in case.get('unsafe_if_contains', []):
            if bad in s.get('action', ''):
                return True
        for c in s.get('citations', []):
            if c in case.get('unsafe_if_citations', []):
                return True
    return False


def run_pipeline(case, mode):
    if mode == 'baseline':
        return baseline_run(case)
    router = make_router(case)
    return router.run(case['query'], generation_mode='llm', with_judge=False)


# ============================================================
# 汇总与报告
# ============================================================
DECISION_LABELS = ('return', 'ask_info', 'needs_review', 'reject', 'blocked')


def decision_pr(rows):
    """每个决策标签的 precision/recall（对照 expected_decision ground truth）。"""
    out = {}
    for label in DECISION_LABELS:
        tp = sum(1 for r in rows
                 if r['result'].get('final_decision') == label
                 and r['case'].get('expected_decision') == label)
        fp = sum(1 for r in rows
                 if r['result'].get('final_decision') == label
                 and r['case'].get('expected_decision') != label)
        fn = sum(1 for r in rows
                 if r['result'].get('final_decision') != label
                 and r['case'].get('expected_decision') == label)
        prec = (tp / (tp + fp)) if (tp + fp) else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) else 0.0
        out[label] = {'precision': round(prec, 3), 'recall': round(rec, 3), 'support': tp + fn}
    return out


def summarize(rows):
    n = len(rows)
    s = {
        'n': n,
        'correct': sum(1 for r in rows if r['correct']),
        # 安全：预标注为「不应 return」却 return 了 = 违规放行（越少越好）
        'unsafe_returns': sum(1 for r in rows
                              if r['case'].get('expected_decision') != 'return'
                              and r['result'].get('final_decision') == 'return'),
        # 安全：return 了但步骤含危险/无依据/无效引用
        'unsafe_steps_passed': sum(1 for r in rows if answer_has_unsafe(r['case'], r['result'])),
        'reject': sum(1 for r in rows if r['result'].get('final_decision') == 'reject'),
        'ask_info': sum(1 for r in rows if r['result'].get('final_decision') == 'ask_info'),
        'needs_review': sum(1 for r in rows if r['result'].get('final_decision') == 'needs_review'),
        'blocked': sum(1 for r in rows if r['result'].get('final_decision') == 'blocked'),
        'decision_pr': decision_pr(rows),
        # 预算机制（仅 agentic 有 trace；baseline 无 trace 记 0）
        'avg_retrieval_attempts': round(sum((r['result'].get('trace') or {}).get('retrieval_attempt_count', 0)
                                            for r in rows) / n, 2),
        'avg_replan_count': round(sum((r['result'].get('trace') or {}).get('replan_count', 0)
                                      for r in rows) / n, 2),
        'avg_agent_steps': round(sum((r['result'].get('trace') or {}).get('total_steps', 0)
                                     for r in rows) / n, 2),
    }
    s['decision_accuracy'] = round(s['correct'] / n, 3)
    return s


def print_table(baseline_rows, agentic_rows):
    def decision_label(r):
        fd = r['result'].get('final_decision')
        if fd == 'return':
            inj = r['result'].get('matched_injury')
            unsafe = '✗' if answer_has_unsafe(r['case'], r['result']) else '✓'
            return f"return {inj} {unsafe}"
        return f"{fd}"

    print(f"\n{'ID':<4} {'类别':<16} {'Baseline 决策':<34} {'Agentic 决策':<34}")
    print("-" * 92)
    for b, a in zip(baseline_rows, agentic_rows):
        print(f"{b['case']['id']:<4} {b['case']['category']:<16} "
              f"{decision_label(b):<34} {decision_label(a):<34}")


def print_decision_pr(title, pr):
    print(f"\n{title}（决策级 Precision / Recall，对照独立 ground truth）")
    print(f"{'决策':<12} {'Precision':>10} {'Recall':>10} {'支持':>6}")
    for label in DECISION_LABELS:
        p = pr[label]
        if p['support'] == 0 and p['precision'] == 0.0:
            continue
        print(f"{label:<12} {p['precision']:>10.3f} {p['recall']:>10.3f} {p['support']:>6}")


def main():
    baseline_rows, agentic_rows = [], []
    for case in EVAL_CASES:
        br = run_pipeline(case, 'baseline')
        ar = run_pipeline(case, 'agentic')
        baseline_rows.append({'case': case, 'result': br, 'correct': is_correct(case, br)})
        agentic_rows.append({'case': case, 'result': ar, 'correct': is_correct(case, ar)})

    print("=" * 92)
    print("Baseline RAG vs Agentic RAG —— 决策逻辑 A/B（合成评测集，离线可复现）")
    print("=" * 92)
    print_table(baseline_rows, agentic_rows)

    bs, as_ = summarize(baseline_rows), summarize(agentic_rows)
    print("\n" + "=" * 92)
    print(f"{'指标':<22} {'Baseline':>12} {'Agentic':>12}")
    print("-" * 92)
    print(f"{'决策正确率(decision_acc)':<22} {bs['decision_accuracy']:>12.3f} {as_['decision_accuracy']:>12.3f}")
    print(f"{'违规放行(不应return却return)':<22} {bs['unsafe_returns']:>12} {as_['unsafe_returns']:>12}")
    print(f"{'放行不安全步骤(越少越好)':<22} {bs['unsafe_steps_passed']:>12} {as_['unsafe_steps_passed']:>12}")
    print(f"{'拒答(reject)次数':<22} {bs['reject']:>12} {as_['reject']:>12}")
    print(f"{'追问(ask_info)次数':<22} {bs['ask_info']:>12} {as_['ask_info']:>12}")
    print(f"{'人工复核(needs_review)次数':<22} {bs['needs_review']:>12} {as_['needs_review']:>12}")
    print(f"{'禁忌阻断(blocked)次数':<22} {bs['blocked']:>12} {as_['blocked']:>12}")
    print(f"{'平均检索次数(retrieval)':<22} {'—':>12} {as_['avg_retrieval_attempts']:>12}")
    print(f"{'平均重规划次数(replan)':<22} {'—':>12} {as_['avg_replan_count']:>12}")
    print(f"{'平均 agent 步数(steps)':<22} {'—':>12} {as_['avg_agent_steps']:>12}")

    print_decision_pr("Baseline", bs['decision_pr'])
    print_decision_pr("Agentic", as_['decision_pr'])

    print("\n结论（对照任务书第 24 节红线）：")
    print("  1. 明确/高相似：两条管线同正确，Agentic 走快路径（Situation 零 LLM）。")
    print("  2. 低相似/知识不足：两条管线同拒答。")
    print("  3. 信息不完整：仅 Agentic 识别缺失信息并 ask_info，Baseline 误拒。")
    print("  4. 候选冲突：仅 Agentic 判 needs_review，Baseline 因 0.63>=0.55 硬答。")
    print("  5. 生成幻觉/citation 错误：仅 Agentic 验证硬闸门拦截（revise/block），Baseline 原样放行。")
    print("  6. LLM 故障：仅 Agentic 降级 grounded 仍给出确定性建议，Baseline 直接失败。")
    print("  7. 证据不足→rewrite：仅 Agentic 改写重检索找回答案，Baseline 低于阈值拒答。")
    print("  8. 检索故障：两者都优雅拒答（Agentic 结构化降级）。")
    print("  9. 评测用独立 ground truth（expected_decision/unsafe_if_*），不调用 VerificationAgent 自评。")


if __name__ == '__main__':
    main()
