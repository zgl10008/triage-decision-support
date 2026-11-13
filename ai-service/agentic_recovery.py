# -*- coding: utf-8 -*-
"""
阶段5：Failure-aware Recovery —— 检索/证据不足时的失败诊断 + 恢复策略
================================================================
不要「低分 → 无脑 rewrite」，而是先诊断 failure_type，再选恢复策略。

FailureType（确定性优先，不依赖 LLM 判断）：
- missing_information   信息本身缺失（来自 SituationAssessment 的缺失字段）→ ask_info（禁止 rewrite）
- candidate_conflict    候选处置冲突 → conflict_analysis
- low_evidence          dense 相似度 < evidence_low → safe_fallback / reject（不重试）
- lexical_gap           口语词与 KB 术语字面差距（灰区 + 字符重叠低）→ terminology_rewrite
- semantic_gap          字面重叠不低但仍不匹配 → semantic_expansion

关键红线（指令第 6 节）：missing_information 禁止调用 rewrite——Query Rewrite 不能凭空
创造用户没有提供的事实。
"""
from agentic_config import EVIDENCE_LOW

LEXICAL_GAP = "lexical_gap"
SEMANTIC_GAP = "semantic_gap"
MISSING_INFORMATION = "missing_information"
CANDIDATE_CONFLICT = "candidate_conflict"
LOW_EVIDENCE = "low_evidence"

# // FailureType → RecoveryStrategy（指令第 6 节映射表）
RECOVERY_STRATEGY = {
    LEXICAL_GAP: "terminology_rewrite",
    SEMANTIC_GAP: "semantic_expansion",
    MISSING_INFORMATION: "ask_info",
    CANDIDATE_CONFLICT: "conflict_analysis",
    LOW_EVIDENCE: "safe_fallback",
}


def char_overlap(a, b):
    """query 与候选名的字符集合重叠度 ∈ [0,1]（确定性，衡量字面差距）。"""
    a, b = (a or '').strip(), (b or '').strip()
    set_a = set(a)
    if not set_a:
        return 0.0
    return len(set_a & set(b)) / len(set_a)


def diagnose_failure(evidence, situation, candidates, query, evidence_low=None):
    """确定性失败诊断：返回 FailureType。

    优先级（从高到低）：
    1. missing_information —— 信息本身缺失，禁止 rewrite，直接 ask_info
    2. candidate_conflict —— 候选冲突（由 EvidenceAssessment 标记）
    3. low_evidence —— dense 低于灰区下界，安全回退/拒答，不重试
    4. lexical_gap —— 灰区内且 query 与 top1 字面重叠低 → 术语改写
    5. semantic_gap —— 灰区内但字面重叠不低 → 语义扩展
    """
    evidence_low = evidence_low if evidence_low is not None else EVIDENCE_LOW

    # 1) 信息缺失（最高优先）—— 查询本身缺关键信息，改写无法凭空创造事实。
    #    注意：只认 missing_information（查询残缺）；safety_critical_missing 是「决策层」缺口
    #    （有伤情信息但缺安全细节），不应阻断检索改写，由 router 单独透出标记。
    if situation and situation.get('missing_information'):
        return MISSING_INFORMATION

    # 2) 候选冲突
    if evidence and evidence.get('candidate_conflict'):
        return CANDIDATE_CONFLICT

    conf = float(evidence.get('confidence', 0.0)) if evidence else 0.0

    # 3) low_evidence：低于灰区下界，不重试
    if conf < evidence_low:
        return LOW_EVIDENCE

    # 4/5) 灰区内的字面差距诊断
    top1 = candidates[0].get('injury', '') if candidates else ''
    if char_overlap(query, top1) < 0.30:
        return LEXICAL_GAP
    return SEMANTIC_GAP
