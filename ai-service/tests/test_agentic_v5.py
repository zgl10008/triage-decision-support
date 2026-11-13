# -*- coding: utf-8 -*-
# V5.0 重构验收测试（无需 BGE-M3、无需真实 Ollama）
# 用法：python tests/test_agentic_v5.py
# 覆盖指令第 23 节新增验收点：
#   ① Information 分层  ② 条件式缺失信息  ③ Failure-aware  ④ 候选冲突(处置路径)
#   ⑤ ActionPlan(无 KB 外动作)  ⑥ Verbalization(只表达白名单)  ⑦ Constrained Repair
#   ⑧ Safety(危险动作 block 且不进 repair)  ⑨ Budget(retry/repair/step 上限)
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
from agentic_evidence import EvidenceAssessmentAgent, treatment_conflict
from agentic_recovery import (
    diagnose_failure, RECOVERY_STRATEGY,
    LEXICAL_GAP, SEMANTIC_GAP, MISSING_INFORMATION, CANDIDATE_CONFLICT, LOW_EVIDENCE,
)
from agentic_action_plan import ActionPlanningAgent
from agentic_repair import ConstrainedRepair, DELETE_CLAIM, REPLACE_WORDING, ATTACH_CITATION
from agentic_verification import VerificationAgent
from agentic_rewrite import QueryRewriter
from agentic_router import AgenticRouter
from agentic_config import MAX_RETRIEVAL_RETRY, MAX_REPLAN, MAX_AGENT_STEPS
from rag_generator import GroundedGenerator


def _fail(*args, **kwargs):
    raise ValueError("LLM down")


def _llm_return(text):
    return lambda prompt, **kwargs: text


# ============================================================
# ① Information 分层（retrieval_sufficient / decision_sufficient / safety_critical_missing）
# ============================================================
def test_situation_layers_head_injury_missing_consciousness():
    a = SituationAssessmentAgent(injury_names={'头皮裂伤'}, llm_fn=_fail)
    r = a.assess('头部被坠物击中，大量出血')
    assert r['retrieval_sufficient'] is True, r
    assert '意识状态' in r['safety_critical_missing'], r   # 头部伤未提供意识状态 → 条件式缺失
    assert r['decision_sufficient'] is False, r            # 检索够但决策层缺安全关键信息


def test_situation_layers_consciousness_provided():
    a = SituationAssessmentAgent(injury_names={'头皮裂伤'}, llm_fn=_fail)
    r = a.assess('头部被坠物击中出血，意识清醒')
    assert r['safety_critical_missing'] == [], r
    assert r['decision_sufficient'] is True, r


# ============================================================
# ② 条件式缺失信息（不是机械规定缺意识/呼吸/出血/恶化一律 False）
# ============================================================
def test_conditional_missing_mild_injury_no_question():
    a = SituationAssessmentAgent(injury_names=set(), llm_fn=_fail)
    r = a.assess('脚踝扭伤疼痛')
    assert r['safety_critical_missing'] == [], r   # 无头部/胸/贯穿/中毒场景，不追问


def test_conditional_missing_resp_provided():
    a = SituationAssessmentAgent(injury_names=set(), llm_fn=_fail)
    r = a.assess('胸口被撞，呼吸困难')
    assert r['safety_critical_missing'] == [], r   # 呼吸状态已提供


def test_conditional_missing_penetrating_bleeding():
    a = SituationAssessmentAgent(injury_names=set(), llm_fn=_fail)
    r = a.assess('腹部穿透伤')
    assert '出血情况' in r['safety_critical_missing'], r   # 贯穿伤但未提供出血情况


# ============================================================
# ③ Failure-aware（FailureType 确定性诊断，禁止完全依赖 LLM）
# ============================================================
def test_diagnose_missing_information_priority():
    sit = {'missing_information': ['受伤部位']}
    assert diagnose_failure({}, sit, [], 'q') == MISSING_INFORMATION


def test_diagnose_candidate_conflict():
    ev = {'candidate_conflict': True, 'confidence': 0.80}
    assert diagnose_failure(ev, {}, [], 'q') == CANDIDATE_CONFLICT


def test_diagnose_low_evidence():
    assert diagnose_failure({'confidence': 0.40}, {}, [], 'q') == LOW_EVIDENCE


def test_diagnose_lexical_gap():
    cand = [{'injury': '头皮裂伤'}]
    assert diagnose_failure({'confidence': 0.52}, {}, cand, '脑袋破了流血') == LEXICAL_GAP


def test_diagnose_semantic_gap():
    cand = [{'injury': '烧伤'}]
    assert diagnose_failure({'confidence': 0.52}, {}, cand, '被火烧伤手臂') == SEMANTIC_GAP


def test_recovery_strategy_map():
    assert RECOVERY_STRATEGY[MISSING_INFORMATION] == 'ask_info'
    assert RECOVERY_STRATEGY[LEXICAL_GAP] == 'terminology_rewrite'
    assert RECOVERY_STRATEGY[SEMANTIC_GAP] == 'semantic_expansion'


# ============================================================
# ④ 候选冲突（处置路径比较：分数接近 + 处置一致 → 不 review；处置冲突 → needs_review）
# ============================================================
def test_treatment_conflict_equivalent():
    assert treatment_conflict('头皮裂伤', '头皮裂伤') == 'equivalent'


def test_conflict_close_scores_compatible_treatment_not_review():
    # 分数接近 + 处置一致（头皮裂伤 vs 头皮挫伤）→ 不判 conflict、不 review
    a = EvidenceAssessmentAgent()
    r = a.assess([{'injury': '头皮裂伤', 'score': 0.63}, {'injury': '头皮挫伤', 'score': 0.61}])
    assert r['decision'] == 'sufficient', r
    assert r['needs_review'] is False, r


def test_conflict_close_scores_conflicting_treatment_needs_review():
    # 分数接近 + 处置冲突（头皮裂伤 vs 脑挫裂伤）→ needs_review
    a = EvidenceAssessmentAgent()
    r = a.assess([{'injury': '头皮裂伤', 'score': 0.63}, {'injury': '脑挫裂伤', 'score': 0.61}])
    assert r['decision'] == 'conflict', r
    assert r['needs_review'] is True, r


# ============================================================
# ⑤ ActionPlan（不得包含 KB 不存在的动作）
# ============================================================
def test_action_plan_actions_all_from_kb():
    ap = ActionPlanningAgent()
    plan = ap.plan('头皮裂伤')
    assert plan.candidate_conditions == ['头皮裂伤']
    assert plan.supported_actions, "头皮裂伤应有常规处置白名单"
    kb_outputs = {
        r['detail'] for r in ap._load()
        if r['injury_type'] == '头皮裂伤' and r['field_type'] == 'output'
    }
    for a in plan.all_actions():
        assert a.action in kb_outputs, f"动作 '{a.action}' 不在 KB output 中（不得新增医学动作）"


# ============================================================
# ⑥ Verbalization（LLM 只能表达 ActionPlan 白名单）
# ============================================================
def test_verbalize_only_whitelist():
    gen = GroundedGenerator()
    plan = ActionPlanningAgent().plan('头皮裂伤')
    whitelisted = plan.supported_actions[0].action
    # 伪造 LLM 输出：一个白名单动作 + 一个编造动作
    data = {'steps': [
        {'step': 1, 'action_id': plan.supported_actions[0].action_id},
        {'step': 2, 'action': '立即截肢', 'citations': [999]},
    ]}
    steps = gen._validate_verbalized_steps(data, plan)
    actions = [s['action'] for s in steps]
    assert whitelisted in actions
    assert '立即截肢' not in actions   # 编造动作被白名单过滤


# ============================================================
# ⑦ Constrained Repair（delete_claim / replace_wording / attach_citation，不新增动作）
# ============================================================
REPAIR_SOURCE_MAP = {1: {'detail': '立即止血包扎'}, 2: {'detail': '建立静脉通道'}}


def test_repair_delete_claim():
    v = VerificationAgent()
    steps = [{'action': '涂抹红花油', 'citations': [1]}]
    verdict = v.verify(steps, REPAIR_SOURCE_MAP)
    r = ConstrainedRepair().repair(steps, REPAIR_SOURCE_MAP, verdict)
    assert r['ops'] and r['ops'][0]['op'] == DELETE_CLAIM, r['ops']
    assert r['steps'] == []


def test_repair_replace_wording():
    v = VerificationAgent()
    steps = [{'action': '立即止血包扎，并涂抹红花油', 'citations': [1]}]
    verdict = v.verify(steps, REPAIR_SOURCE_MAP)
    r = ConstrainedRepair().repair(steps, REPAIR_SOURCE_MAP, verdict)
    assert r['ops'] and r['ops'][0]['op'] == REPLACE_WORDING, r['ops']
    assert r['steps'][0]['action'] == '立即止血包扎'   # 只保留有依据子句，不写新文本


def test_repair_attach_citation():
    v = VerificationAgent()
    steps = [{'action': '立即止血包扎', 'citations': [99]}]
    verdict = v.verify(steps, REPAIR_SOURCE_MAP)
    r = ConstrainedRepair().repair(steps, REPAIR_SOURCE_MAP, verdict)
    assert r['ops'] and r['ops'][0]['op'] == ATTACH_CITATION, r['ops']
    assert r['steps'][0]['citations'] == [1]


def test_repair_not_add_action():
    v = VerificationAgent()
    steps = [{'action': '涂抹红花油', 'citations': [1]}]
    verdict = v.verify(steps, REPAIR_SOURCE_MAP)
    r = ConstrainedRepair().repair(steps, REPAIR_SOURCE_MAP, verdict)
    assert len(r['steps']) <= len(steps)   # repair 只删不增


# ============================================================
# ⑧ Safety（危险动作 → blocked；blocked 不进 repair）
# ============================================================
def test_safety_block_not_repaired():
    v = VerificationAgent()
    steps = [{'action': '立即截肢', 'citations': [1]}]
    verdict = v.verify(steps, REPAIR_SOURCE_MAP)
    assert verdict['failure_type'] == 'forbidden_action', verdict
    assert verdict['recommended_action'] == 'block'
    assert verdict['safety_blocked'] is True
    r = ConstrainedRepair().repair(steps, REPAIR_SOURCE_MAP, verdict)
    assert r['ops'] == []                # blocked 不进 repair
    assert r['retries_used'] == 0


# ============================================================
# ⑨ Budget（retry_count <= MAX_RETRIEVAL_RETRY，repair_count <= MAX_REPLAN，step_count <= MAX_AGENT_STEPS）
# ============================================================
class _FakeGenerator:
    SOURCE_MAP = REPAIR_SOURCE_MAP

    def build_context(self, injury):
        return ('ctx', self.SOURCE_MAP)

    def generate(self, injury, visual_evidence=None, mode='llm', with_judge=True):
        return {
            'injury': injury, 'mode': mode,
            'steps': [{'step': 1, 'action': '立即止血包扎', 'citations': [1]}],
            'sources': [dict(ref=1, **self.SOURCE_MAP[1])],
            'faithfulness': {'overall_faithful': 1.0},
        }


def _make_router(retriever, rewriter=None):
    return AgenticRouter(
        retriever=retriever,
        generator=_FakeGenerator(),
        situation_agent=SituationAssessmentAgent(injury_names={'头皮裂伤'}, llm_fn=_fail),
        rewriter=rewriter or QueryRewriter(llm_fn=_fail),
    )


def test_budget_bounds_fast_path():
    def retrieve(query, top_k=3):
        return [{'injury': '头皮裂伤', 'score': 0.9}, {'injury': '脑挫裂伤', 'score': 0.3}]

    r = _make_router(retrieve).run('头皮裂伤', generation_mode='grounded', with_judge=False)
    st = r['state']
    assert st['retry_count'] <= MAX_RETRIEVAL_RETRY, st
    assert st['repair_count'] <= MAX_REPLAN, st
    assert st['step_count'] <= MAX_AGENT_STEPS, st
    assert st['final_status'] == 'return'


def test_repair_max_retry_one():
    assert ConstrainedRepair().max_retry == 1   # MAX_REPAIR_RETRY=1


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
