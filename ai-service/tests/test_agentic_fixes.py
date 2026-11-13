# -*- coding: utf-8 -*-
# 阶段4 Agentic RAG 安全/状态一致性/评测可靠性 增量修复回归测试
# 用法：python tests/test_agentic_fixes.py
# 覆盖修复清单（对应需求书）：
#   S01-S07   Situation 信息充分性（去除长度误判 / 情况A/B/C / LLM 失败保守兜底）
#   E01-E07   Evidence 证据评估（dense 排序取 gap / 单候选 gap=None / rank_disagreement 诊断）
#   V01-V05   Verification 动作级 grounding（复合动作拆分）
#   R01-R08   Router 状态机（evidence retry / revise / re_retrieve / 检索预算 / replan 预算 /
#             agent 步数预算 / 陈旧 matched 状态一致性）
#   F01-F06   故障降级（检索/LLM/生成/改写/验证超时 → 保守兜底，不硬答）
# 与 tests/test_agentic.py 互补：本文件聚焦「修复项」的边界行为，不重复既有 happy path。
import contextlib
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import agentic_router as router_mod
from agentic_situation import SituationAssessmentAgent
from agentic_evidence import EvidenceAssessmentAgent
from agentic_verification import VerificationAgent
from agentic_rewrite import QueryRewriter
from agentic_router import AgenticRouter


def _fail(*args, **kwargs):
    raise ValueError("LLM down")


def _llm_return(text):
    return lambda prompt, **kwargs: text


@contextlib.contextmanager
def _max_agent_steps(n):
    """临时调高/调低 agent 步数上限，隔离「步数预算」与其他预算的相互干扰。"""
    old = router_mod.MAX_AGENT_STEPS
    router_mod.MAX_AGENT_STEPS = n
    try:
        yield
    finally:
        router_mod.MAX_AGENT_STEPS = old


# ============================================================
# 共享 fixture（SOURCE_MAP / FakeGenerator / _make_router）
# ============================================================
SOURCE_MAP = {
    1: {'source_id': 'kb_1', 'category': '现场急救', 'field_type': 'output', 'detail': '立即止血包扎'},
    2: {'source_id': 'kb_2', 'category': '现场急救', 'field_type': 'output', 'detail': '清创消毒'},
}


class FakeGenerator:
    """可控生成器：mode=llm 可模拟故障，grounded 稳定返回一条有引用支撑的处置步骤。"""

    def __init__(self, fail_llm=False):
        self.fail_llm = fail_llm
        self.source_map = SOURCE_MAP

    def build_context(self, injury):
        return ('ctx', self.source_map)

    def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
        if mode == 'llm' and self.fail_llm:
            raise Exception('Ollama 连接失败')
        return {
            'injury': injury, 'mode': mode,
            'steps': [{'step': 1, 'action': '立即止血包扎', 'citations': [1]}],
            'sources': [dict(ref=1, **self.source_map[1])],
            'faithfulness': {'overall_faithful': 1.0},
        }


def _make_router(retriever, generator=None, situation=None, verifier=None, rewriter=None):
    """组装 AgenticRouter。situation 默认注入 _fail，避免任何意外路径触网。"""
    return AgenticRouter(
        retriever=retriever,
        generator=generator or FakeGenerator(),
        situation_agent=situation or SituationAssessmentAgent(injury_names={'头皮裂伤'}, llm_fn=_fail),
        verification_agent=verifier,
        rewriter=rewriter or QueryRewriter(llm_fn=_fail),
    )


# ============================================================
# S01-S07：Situation 信息充分性（P0-1）
# ============================================================
def test_s01_exact_injury_name_sufficient():
    a = SituationAssessmentAgent(injury_names={'头皮裂伤'}, llm_fn=_fail)
    r = a.assess('头皮裂伤')
    assert r['status'] == 'sufficient' and r['via_llm'] is False, r


def test_s02_location_only_not_sufficient():
    a = SituationAssessmentAgent(
        injury_names=set(),
        llm_fn=_llm_return('{"status":"insufficient","reason":"缺伤情性质","missing_information":["伤情性质"]}'),
    )
    r = a.assess('头部')
    assert r['status'] == 'insufficient', r
    assert r['via_llm'] is True  # 仅部位 → 走 LLM 识别缺失项


def test_s03_nature_only_not_sufficient():
    a = SituationAssessmentAgent(
        injury_names=set(),
        llm_fn=_llm_return('{"status":"insufficient","reason":"缺部位","missing_information":["受伤部位"]}'),
    )
    r = a.assess('出血')
    assert r['status'] == 'insufficient', r
    assert r['via_llm'] is True  # 仅伤情信号 → 走 LLM


def test_s04_injured_phrase_not_sufficient():
    a = SituationAssessmentAgent(
        injury_names=set(),
        llm_fn=_llm_return('{"status":"insufficient","reason":"缺部位/性质","missing_information":["受伤部位","伤情性质"]}'),
    )
    r = a.assess('我受伤了')
    assert r['status'] == 'insufficient', r


def test_s05_pain_phrase_not_sufficient():
    """关键回归：旧逻辑 len>=6 会把"好疼啊怎么办"误判 sufficient。"""
    a = SituationAssessmentAgent(
        injury_names=set(),
        llm_fn=_llm_return('{"status":"insufficient","reason":"缺部位/性质","missing_information":["受伤部位","伤情性质"]}'),
    )
    r = a.assess('好疼啊怎么办')
    assert r['status'] == 'insufficient', r
    assert r['via_llm'] is True


def test_s06_location_plus_nature_sufficient():
    a = SituationAssessmentAgent(injury_names=set(), llm_fn=_fail)
    r = a.assess('头部大量出血')
    assert r['status'] == 'sufficient' and r['via_llm'] is False, r


def test_s07_llm_fail_fallback_insufficient():
    """情况 D：LLM 失败 → 保守 insufficient，绝不由 LLM 失败放行。"""
    a = SituationAssessmentAgent(injury_names=set(), llm_fn=_fail)
    r = a.assess('头部')
    assert r['status'] == 'insufficient', r
    assert r['via_llm'] is False  # 确定性兜底
    assert r['missing_information'], r


# ============================================================
# E01-E07：Evidence 证据评估（P0-2/3/4）
# ============================================================
def test_e01_single_high_candidate_no_gap_no_fast_path():
    """单候选高分：不虚构 dense_second=0.0 → gap=None → 不走快路径。"""
    a = EvidenceAssessmentAgent()
    r = a.assess([{'injury': '头皮裂伤', 'score': 0.90}])
    assert r['signals']['gap'] is None, r['signals']
    assert r['decision'] == 'sufficient', r
    assert '快路径' not in r['reason'], r['reason']  # 走阈值分支，非快路径


def test_e02_two_candidates_large_gap_fast_path():
    a = EvidenceAssessmentAgent()
    r = a.assess([{'injury': '头皮裂伤', 'score': 0.80}, {'injury': '脑挫裂伤', 'score': 0.30}])
    assert r['decision'] == 'sufficient' and '快路径' in r['reason'], r
    assert r['signals']['gap'] == 0.5, r['signals']


def test_e03_close_scores_conflict():
    a = EvidenceAssessmentAgent()
    r = a.assess([{'injury': '头皮裂伤', 'score': 0.63}, {'injury': '脑挫裂伤', 'score': 0.61}])
    assert r['decision'] == 'conflict' and r['needs_review'] is True, r


def test_e04_rank_disagreement_is_diagnostic():
    """RRF 排序 top1 与 dense top1 不同：仅作诊断信号，不单独 reject。"""
    a = EvidenceAssessmentAgent()
    # RRF 把 dense 低分者排前；dense top1 实为第二个
    r = a.assess([{'injury': '脑挫裂伤', 'score': 0.30}, {'injury': '头皮裂伤', 'score': 0.80}])
    assert r['signals']['rank_disagreement'] is True, r['signals']
    assert r['decision'] == 'sufficient', r  # 不因单纯排名不同就 reject
    assert r['needs_review'] is False, r


def test_e05_gray_zone_need_retry():
    a = EvidenceAssessmentAgent()
    r = a.assess([{'injury': 'A', 'score': 0.52}, {'injury': 'B', 'score': 0.30}], retries_left=1)
    assert r['decision'] == 'insufficient' and r['need_retry'] is True, r
    assert r['retry_strategy'] == 'query_rewrite'


def test_e06_no_candidates():
    a = EvidenceAssessmentAgent()
    r = a.assess([])
    assert r['decision'] == 'insufficient' and r['need_retry'] is False, r
    assert r['signals']['gap'] is None


def test_e07_visual_conflict_needs_review():
    a = EvidenceAssessmentAgent()
    text = [{'injury': '头皮裂伤', 'score': 0.90}, {'injury': '脑挫裂伤', 'score': 0.30}]
    vis = [{'name': '腹部穿透伤', 'confidence': 0.9}]
    r = a.assess(text, visual_candidates=vis)
    assert r['signals']['visual_conflict'] is True, r['signals']
    assert r['needs_review'] is True, r
    assert r['decision'] == 'sufficient', r  # 视觉冲突不推翻 dense 判定，交由 router 转人工


# ============================================================
# V01-V05：Verification 动作级 grounding（P1-10）
# ============================================================
def test_v01_valid_citation_pass():
    v = VerificationAgent()
    steps = [
        {'step': 1, 'action': '立即止血包扎', 'citations': [1]},
        {'step': 2, 'action': '清创消毒', 'citations': [2]},
    ]
    r = v.verify(steps, SOURCE_MAP)
    assert r['decision'] == 'pass', r


def test_v02_invalid_citation():
    v = VerificationAgent()
    r = v.verify([{'step': 1, 'action': '立即止血包扎', 'citations': [1, 99]}], SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'citation_error', r


def test_v03_unsupported_action():
    v = VerificationAgent()
    r = v.verify([{'step': 1, 'action': '进行全身CT检查', 'citations': [1]}], SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'unsupported_action', r


def test_v04_forbidden_action_block():
    v = VerificationAgent()
    r = v.verify([{'step': 1, 'action': '立即截肢', 'citations': [1]}], SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'forbidden_action', r
    assert r['recommended_action'] == 'block'


def test_v05_multi_action_one_unsupported():
    """复合动作逐原子 grounding：部分动作有依据、部分无依据 → 整步判无依据。"""
    v = VerificationAgent()
    steps = [{'step': 1, 'action': '立即止血包扎，并建立静脉通道', 'citations': [1]}]
    r = v.verify(steps, SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'unsupported_action', r
    assert '建立静脉通道' in r['unsupported_actions'][0], r


# ============================================================
# R01-R08：Router 状态机 / 预算 / 状态一致性（P0-5/6/7/8）
# ============================================================
def test_r01_fast_path_return():
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    r = _make_router(retrieve).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is True and r['final_decision'] == 'return', r
    assert r['matched_injury'] == '头皮裂伤'


def test_r02_evidence_retry():
    def retrieve(query, top_k=3):
        if query == '头皮裂伤':
            return [{'injury': '头皮裂伤', 'score': 0.9}]
        return [{'injury': '头皮裂伤', 'score': 0.52}]  # 原始 query 落灰区

    rewriter = QueryRewriter(llm_fn=_llm_return('{"rewritten_query":"头皮裂伤"}'))
    r = _make_router(retrieve, rewriter=rewriter).run('头部裂伤出血', generation_mode='grounded', with_judge=False)
    assert r['success'] is True and r['final_decision'] == 'return', r
    assert r['trace']['retrieval_attempt_count'] == 2, r['trace']


def test_r03_verification_revise_filters_unsupported():
    gen = FakeGenerator()
    gen.generate = lambda injury, visual_evidence=None, mode='llm', with_judge=True: {
        'injury': injury, 'mode': mode,
        'steps': [
            {'step': 1, 'action': '立即止血包扎', 'citations': [1]},
            {'step': 2, 'action': '进行全身CT检查', 'citations': [1]},
        ],
        'sources': [dict(ref=1, **SOURCE_MAP[1])],
        'faithfulness': {'overall_faithful': 1.0},
    }

    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    r = _make_router(retrieve, generator=gen).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is True and r['final_decision'] == 'return', r
    assert len(r['steps']) == 1 and r['steps'][0]['action'] == '立即止血包扎', r['steps']


def test_r04_verification_reretrieve_returns():
    class V:
        def __init__(self):
            self.calls = 0

        def verify(self, steps, source_map, faithfulness=None):
            self.calls += 1
            if self.calls == 1:
                return {'decision': 'fail', 'score': 0.3, 'citation_valid': True, 'faithful': False,
                        'unsupported_actions': [], 'invalid_citations': [], 'forbidden_actions': [],
                        'coverage': 1.0, 'reason': '证据不足', 'failure_type': 'insufficient_evidence',
                        'recommended_action': 're_retrieve'}
            return {'decision': 'pass', 'score': 1.0, 'citation_valid': True, 'faithful': True,
                    'unsupported_actions': [], 'invalid_citations': [], 'forbidden_actions': [],
                    'coverage': 1.0, 'reason': '通过', 'failure_type': None, 'recommended_action': None}

        def filter_safe_steps(self, steps, source_map):
            return steps, []

    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}]

    rewriter = QueryRewriter(llm_fn=_llm_return('{"rewritten_query":"头皮裂伤出血"}'))
    v = V()
    with _max_agent_steps(100):
        r = _make_router(retrieve, verifier=v, rewriter=rewriter).run(
            '头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is True and r['final_decision'] == 'return', r
    assert v.calls >= 2, v.calls
    assert r['trace']['retrieval_attempt_count'] == 2, r['trace']


def test_r05_retrieval_budget_respected():
    """请求级检索预算：max_retrieval_retry=1 → 整个请求最多 2 次检索，跨阶段共享。"""
    class V:
        def verify(self, steps, source_map, faithfulness=None):
            return {'decision': 'fail', 'score': 0.3, 'citation_valid': True, 'faithful': False,
                    'unsupported_actions': [], 'invalid_citations': [], 'forbidden_actions': [],
                    'coverage': 1.0, 'reason': '证据不足', 'failure_type': 'insufficient_evidence',
                    'recommended_action': 're_retrieve'}

        def filter_safe_steps(self, steps, source_map):
            return steps, []

    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}]

    rewriter = QueryRewriter(llm_fn=_llm_return('{"rewritten_query":"改写查询"}'))
    with _max_agent_steps(100):
        r = _make_router(retrieve, verifier=V(), rewriter=rewriter).run(
            '头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['trace']['retrieval_attempt_count'] == 2, r['trace']
    assert r['final_decision'] == 'reject', r


def test_r06_replan_budget_respected():
    """max_replan=1 → 最多一次 replan；revise 后仍 fail → 拒答而非无限循环。"""
    class V:
        def verify(self, steps, source_map, faithfulness=None):
            return {'decision': 'fail', 'score': 0.3, 'citation_valid': True, 'faithful': False,
                    'unsupported_actions': ['x'], 'invalid_citations': [], 'forbidden_actions': [],
                    'coverage': 1.0, 'reason': '无依据', 'failure_type': 'unsupported_action',
                    'recommended_action': 'revise'}

        def filter_safe_steps(self, steps, source_map):
            return steps, []  # 保留全部 → 重验证仍 fail

    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}]

    r = _make_router(retrieve, verifier=V()).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['final_decision'] == 'reject', r
    assert r['trace']['replan_count'] == 1, r['trace']


def test_r07_agent_step_budget_respected():
    """执行下一步前检查步数预算：超限即中止，绝不超预算继续调用。"""
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    with _max_agent_steps(3):
        r = _make_router(retrieve).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['final_decision'] == 'reject', r
    assert 'step_limit_exceeded' in r['trace'], r['trace']


def test_r08_reretrieve_updates_matched_and_state():
    """re_retrieve 改写命中新伤情 → matched/source_map/steps 同步更新，杜绝陈旧状态。"""
    class Gen:
        def build_context(self, injury):
            m = {
                '伤情A': {1: {'source_id': 'a', 'category': '急救', 'field_type': 'output', 'detail': 'A处理'}},
                '伤情B': {2: {'source_id': 'b', 'category': '急救', 'field_type': 'output', 'detail': 'B处理'}},
            }
            return ('ctx', m[injury])

        def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
            ref = 1 if injury == '伤情A' else 2
            return {'injury': injury, 'mode': 'grounded',
                    'steps': [{'step': 1, 'action': injury + '处理', 'citations': [ref]}],
                    'sources': [], 'faithfulness': {'overall_faithful': 1.0}}

    class V:
        def verify(self, steps, source_map, faithfulness=None):
            if 1 in source_map:  # 伤情A → 证据不足 → re_retrieve
                return {'decision': 'fail', 'score': 0.3, 'citation_valid': True, 'faithful': False,
                        'unsupported_actions': [], 'invalid_citations': [], 'forbidden_actions': [],
                        'coverage': 1.0, 'reason': '证据不足', 'failure_type': 'insufficient_evidence',
                        'recommended_action': 're_retrieve'}
            return {'decision': 'pass', 'score': 1.0, 'citation_valid': True, 'faithful': True,
                    'unsupported_actions': [], 'invalid_citations': [], 'forbidden_actions': [],
                    'coverage': 1.0, 'reason': '通过', 'failure_type': None, 'recommended_action': None}

        def filter_safe_steps(self, steps, source_map):
            return steps, []

    def retrieve(query, top_k=3):
        if query == '头部裂伤':
            return [{'injury': '伤情B', 'score': 0.9}]
        return [{'injury': '伤情A', 'score': 0.9}]

    rewriter = QueryRewriter(llm_fn=_llm_return('{"rewritten_query":"头部裂伤"}'))
    situation = SituationAssessmentAgent(injury_names={'伤情A', '伤情B'}, llm_fn=_fail)
    with _max_agent_steps(100):
        r = _make_router(retrieve, generator=Gen(), verifier=V(), rewriter=rewriter,
                         situation=situation).run('伤情A', generation_mode='grounded', with_judge=False)
    assert r['success'] is True and r['final_decision'] == 'return', r
    assert r['matched_injury'] == '伤情B', r  # 关键：不是陈旧伤情A
    assert r['steps'][0]['action'] == '伤情B处理', r['steps']
    assert r['verification']['decision'] == 'pass', r['verification']
    assert r['trace']['generation']['injury'] == '伤情B', r['trace']


# ============================================================
# F01-F06：故障降级（保守兜底，不硬答）
# ============================================================
def test_f01_retrieval_timeout_safe():
    def retrieve(query, top_k=3):
        raise TimeoutError('检索超时')

    r = _make_router(retrieve).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is False and r['final_decision'] in ('reject', 'ask_info'), r


def test_f02_retrieval_exception_safe():
    def retrieve(query, top_k=3):
        raise RuntimeError('向量库不可用')

    r = _make_router(retrieve).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is False and r['final_decision'] in ('reject', 'ask_info'), r


def test_f03_llm_timeout_grounded_fallback():
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    r = _make_router(retrieve, generator=FakeGenerator(fail_llm=True)).run(
        '头皮裂伤', generation_mode='llm', with_judge=True)
    assert r['success'] is True and r['mode'] == 'grounded', r
    assert r['trace']['generation']['degraded'] is True


def test_f04_llm_invalid_json_rewriter_fallback():
    rw = QueryRewriter(llm_fn=_llm_return('不是JSON'))
    q, via = rw.rewrite('脑袋破了', '证据不足')
    assert q == '脑袋破了' and via is False


def test_f05_generation_exception_grounded_fallback():
    class BoomGen:
        def build_context(self, injury):
            return ('ctx', SOURCE_MAP)

        def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
            if mode == 'llm':
                raise RuntimeError('生成失败')
            return {'injury': injury, 'mode': 'grounded',
                    'steps': [{'step': 1, 'action': '立即止血包扎', 'citations': [1]}],
                    'sources': [], 'faithfulness': {'overall_faithful': 1.0}}

    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    r = _make_router(retrieve, generator=BoomGen()).run('头皮裂伤', generation_mode='llm', with_judge=False)
    assert r['success'] is True and r['mode'] == 'grounded', r


def test_f06_verification_timeout_conservative_reject():
    class TimeoutVerifier:
        def verify(self, steps, source_map, faithfulness=None):
            raise TimeoutError('验证超时')

        def filter_safe_steps(self, steps, source_map):
            return steps, []

    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    r = _make_router(retrieve, verifier=TimeoutVerifier()).run(
        '头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is False and r['final_decision'] == 'reject', r
    assert r['verification']['failure_type'] == 'verification_timeout', r


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"❌ {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"💥 {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n通过 {len(tests) - failed}/{len(tests)} 项")
    sys.exit(1 if failed else 0)
