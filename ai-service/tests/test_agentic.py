# -*- coding: utf-8 -*-
# 阶段4 Agentic RAG 单元 / 集成测试（无需 BGE 模型、无需真实 Ollama）
# 用法：python tests/test_agentic.py
# 覆盖任务书第 23 节验收标准 7 条：
#   ① 明确伤情快路径  ② 信息不足识别缺失信息  ③ 证据不足触发 rewrite
#   ④ 候选冲突不硬答  ⑤ 无依据/禁忌动作拦截  ⑥ citation 错误处理  ⑦ 服务故障降级
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

from agentic_situation import SituationAssessmentAgent
from agentic_evidence import EvidenceAssessmentAgent
from agentic_verification import VerificationAgent
from agentic_rewrite import QueryRewriter
from agentic_router import AgenticRouter


def _fail(*args, **kwargs):
    raise ValueError("LLM down")


def _llm_return(text):
    return lambda prompt, **kwargs: text


# ============================================================
# Situation Assessment（① 快路径 / ② 信息不足）
# ============================================================
def test_situation_fast_path():
    agent = SituationAssessmentAgent(injury_names={'头皮裂伤'})
    r = agent.assess('头部被坠物击中，大量出血')
    assert r['status'] == 'sufficient', r
    assert r['via_llm'] is False
    assert '大量出血' in r['risk_flags']


def test_situation_exact_name():
    agent = SituationAssessmentAgent(injury_names={'头皮裂伤'})
    r = agent.assess('头皮裂伤')
    assert r['status'] == 'sufficient', r
    assert r['via_llm'] is False


def test_situation_insufficient():
    agent = SituationAssessmentAgent(
        injury_names=set(),
        llm_fn=_llm_return('{"status":"insufficient","reason":"缺部位","missing_information":["受伤部位","伤情性质"]}'),
    )
    r = agent.assess('受伤了')
    assert r['status'] == 'insufficient'
    assert r['via_llm'] is True
    assert '受伤部位' in r['missing_information']


def test_situation_insufficient_llm_fail_fallback():
    agent = SituationAssessmentAgent(injury_names=set(), llm_fn=_fail)
    r = agent.assess('受伤了')
    assert r['status'] == 'insufficient'
    assert r['via_llm'] is False  # 确定性兜底，不依赖 LLM
    assert r['missing_information']


# ============================================================
# Evidence Assessment（① 快路径 / ③ 灰区 retry / ④ 候选冲突）
# ============================================================
def test_evidence_sufficient_fast_path():
    agent = EvidenceAssessmentAgent()
    cands = [{'injury': '头皮裂伤', 'score': 0.80}, {'injury': '脑挫裂伤', 'score': 0.30}]
    r = agent.assess(cands)
    assert r['decision'] == 'sufficient' and r['matched_injury'] == '头皮裂伤'


def test_evidence_insufficient_retry():
    agent = EvidenceAssessmentAgent()
    cands = [{'injury': 'A', 'score': 0.52}, {'injury': 'B', 'score': 0.30}]
    r = agent.assess(cands, retries_left=1)
    assert r['decision'] == 'insufficient'
    assert r['need_retry'] is True and r['retry_strategy'] == 'query_rewrite'


def test_evidence_insufficient_no_retry():
    agent = EvidenceAssessmentAgent()
    r = agent.assess([{'injury': 'A', 'score': 0.40}], retries_left=0)
    assert r['decision'] == 'insufficient' and r['need_retry'] is False


def test_evidence_conflict_not_hard_answer():
    agent = EvidenceAssessmentAgent()
    cands = [{'injury': '头皮裂伤', 'score': 0.63}, {'injury': '脑挫裂伤', 'score': 0.61}]
    r = agent.assess(cands, retries_left=0)
    assert r['decision'] == 'conflict'
    assert r['candidate_conflict'] is True and r['needs_review'] is True


# ============================================================
# Verification / Safety（⑤ 无依据/禁忌拦截 / ⑥ citation 错误）
# ============================================================
SOURCE_MAP = {
    1: {'source_id': 'kb_1', 'category': '现场急救', 'field_type': 'output', 'detail': '立即止血包扎'},
    2: {'source_id': 'kb_2', 'category': '现场急救', 'field_type': 'output', 'detail': '清创消毒'},
}


def test_verify_pass():
    v = VerificationAgent()
    steps = [
        {'step': 1, 'action': '立即止血包扎', 'citations': [1]},
        {'step': 2, 'action': '清创消毒', 'citations': [2]},
    ]
    r = v.verify(steps, SOURCE_MAP)
    assert r['decision'] == 'pass', r


def test_verify_invalid_citation():
    v = VerificationAgent()
    steps = [{'step': 1, 'action': '立即止血包扎', 'citations': [1, 99]}]
    r = v.verify(steps, SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'citation_error', r


def test_verify_unsupported_action():
    v = VerificationAgent()
    steps = [{'step': 1, 'action': '进行全身CT检查', 'citations': [1]}]
    r = v.verify(steps, SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'unsupported_action', r


def test_verify_forbidden_action_block():
    v = VerificationAgent()
    steps = [{'step': 1, 'action': '立即截肢', 'citations': [1]}]
    r = v.verify(steps, SOURCE_MAP)
    assert r['decision'] == 'fail' and r['failure_type'] == 'forbidden_action', r
    assert r['recommended_action'] == 'block'


def test_rewrite_ok_and_fallback():
    rw = QueryRewriter(llm_fn=_llm_return('{"rewritten_query":"头部裂伤出血"}'))
    q, via = rw.rewrite('脑袋破了', '证据不足')
    assert q == '头部裂伤出血' and via is True

    rw_fail = QueryRewriter(llm_fn=_fail)
    q, via = rw_fail.rewrite('脑袋破了')
    assert q == '脑袋破了' and via is False


# ============================================================
# Router 集成（⑦ 服务故障降级 / 端到端 return）
# ============================================================
class FakeGenerator:
    """可控生成器：mode=llm 时可模拟 LLM 故障，grounded 永远成功。"""

    def __init__(self, fail_llm=False):
        self.fail_llm = fail_llm
        self.source_map = SOURCE_MAP

    def build_context(self, injury):
        return ('ctx', self.source_map)

    def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
        if mode == 'llm' and self.fail_llm:
            raise Exception('Ollama 连接失败')
        steps = [{'step': 1, 'action': '立即止血包扎', 'citations': [1]}]
        return {
            'injury': injury, 'mode': mode, 'steps': steps,
            'sources': [dict(ref=1, **self.source_map[1])],
            'faithfulness': {'overall_faithful': 1.0},
        }


def _make_router(retriever, fail_llm=False):
    return AgenticRouter(
        retriever=retriever,
        generator=FakeGenerator(fail_llm=fail_llm),
        situation_agent=SituationAssessmentAgent(injury_names={'头皮裂伤'}),
        rewriter=QueryRewriter(llm_fn=_fail),  # 改写走确定性兜底，不依赖 LLM
    )


def test_router_return_fast_path():
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    router = _make_router(retrieve)
    r = router.run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is True, r
    assert r['matched_injury'] == '头皮裂伤'
    assert r['final_decision'] == 'return'
    assert r['trace']['situation_assessment']['via_llm'] is False  # 快路径


def test_router_reject_low_evidence():
    def retrieve(query, top_k=3):
        return [{'injury': 'A', 'score': 0.3}]

    router = _make_router(retrieve)
    r = router.run('某个奇怪描述', generation_mode='grounded', with_judge=False)
    assert r['success'] is False
    assert r['final_decision'] in ('reject', 'ask_info'), r


def test_router_conflict_needs_review():
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.63}, {'injury': '脑挫裂伤', 'score': 0.61}]

    router = _make_router(retrieve)
    r = router.run('头部受伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is False
    assert r['final_decision'] == 'needs_review', r


def test_router_llm_failure_grounded_fallback():
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    router = _make_router(retrieve, fail_llm=True)
    r = router.run('头皮裂伤', generation_mode='llm', with_judge=True)
    # LLM 故障 → grounded 降级仍能给出确定性建议
    assert r['success'] is True, r
    assert r['final_decision'] == 'return'
    assert r['mode'] == 'grounded', r['mode']  # 已降级到 grounded
    assert r['trace']['generation']['degraded'] is True


def test_router_retriever_failure_safe():
    def retrieve(query, top_k=3):
        raise Exception('向量库不可用')

    router = _make_router(retrieve)
    r = router.run('头皮裂伤', generation_mode='grounded', with_judge=False)
    assert r['success'] is False  # 检索故障 → 拒答，不硬答
    assert r['final_decision'] in ('reject', 'ask_info'), r


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
    print(f"\n通过 {len(tests) - failed}/{len(tests)} 项")
    sys.exit(1 if failed else 0)
