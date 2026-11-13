# -*- coding: utf-8 -*-
"""
阶段4：Evidence Assessment Agent —— 证据充分性 / 候选冲突 / 是否重检索
================================================================
这是 Agentic 改造的核心。它把「dense 余弦 >= 0.55 就答」这一个二值判定，升级为
综合多个信号的证据评估：dense 相似度、top1-top2 gap、RRF/dense 排名一致性、候选冲突。

设计（遵循「确定性优先，Agent 负责判断」）：
- 本 Agent 的「判断」由**确定性信号综合 + 分层阈值**完成，不依赖弱模型决定安全边界；
  LLM 语义消歧仅作为可选开关（with_llm=False 默认关闭），失败/关闭都走确定性兜底。
- 保留既有 0.55 阈值（HYBRID_THRESHOLD）作为基础信号，在其上分层：
    dense >= fast_path_threshold 且 gap >= fast_path_gap → sufficient（快路径）
    0.55 <= dense < fast_path            → sufficient（低置信，照常生成+全量验证）
    evidence_low <= dense < 0.55         → insufficient + need_retry（query_rewrite）
    dense < evidence_low                 → insufficient（不重试，拒答/补信息）
- 候选冲突：top1≈top2 且伤情明显不同 → conflict，即使 dense >= 0.55 也不硬答。

输出结构（任务书第 7 节）：
  {"decision", "confidence", "reason", "matched_injury",
   "need_retry", "retry_strategy", "candidate_conflict", "needs_review", "signals"}
"""
import json
import os

from agentic_config import (
    FAST_PATH_THRESHOLD, FAST_PATH_GAP, EVIDENCE_LOW, HYBRID_THRESHOLD, TFIDF_THRESHOLD, CONFLICT_GAP,
)
from multimodal_fusion import conflict_detect

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
KB_RECORDS_PATH = os.path.join(CURRENT_DIR, 'kb', 'kb_records.json')

# // 处置路径比较：两个候选伤情「名字不同」不代表「处置冲突」——若处置一致（同为压迫止血），
# // 分数接近也不该触发 needs_review。本模块比较 KB 里 output 键的处置动作集合。
_TREATMENT_CACHE = {}


def _treatment_actions(injury, records_path=None):
    """加载某伤情在 KB 中的处置动作集合（field_type=='output' 的 detail）。"""
    path = records_path or KB_RECORDS_PATH
    if path not in _TREATMENT_CACHE:
        with open(path, encoding='utf-8') as f:
            _TREATMENT_CACHE[path] = json.load(f)
    actions = set()
    for r in _TREATMENT_CACHE[path]:
        if r.get('injury_type') == injury and r.get('field_type') == 'output':
            actions.add(r.get('detail', ''))
    return actions


def treatment_conflict(a, b, records_path=None):
    """比较两个伤情的处置路径，返回 equivalent/compatible/partially_conflicting/conflicting。

    处置路径 = output 键动作集合。判定（确定性，无需 LLM）：
    - equivalent            动作集合完全相同
    - conflicting           动作集合无交集（处置完全不同）
    - compatible            交集占并集 >= 0.5（处置大体一致）或一方无处置信息（无法判冲突）
    - partially_conflicting 有交集但占比 < 0.5

    只有 partially_conflicting / conflicting 才需要 needs_review。
    """
    ta = _treatment_actions(a, records_path)
    tb = _treatment_actions(b, records_path)
    if not ta or not tb:
        return 'compatible'  # 一方缺处置信息 → 不能判冲突，交其他信号
    if ta == tb:
        return 'equivalent'
    inter = ta & tb
    if not inter:
        return 'conflicting'
    jaccard = len(inter) / len(ta | tb)
    if jaccard >= 0.5:
        return 'compatible'
    return 'partially_conflicting'


def _is_distinct(a, b):
    """两个伤情名是否「明显不同」（非相等、非包含关系）。"""
    if not a or not b:
        return False
    if a == b:
        return False
    return (a not in b) and (b not in a)


class EvidenceAssessmentAgent:
    """证据评估 Agent：确定性信号综合 + 分层阈值 + 候选冲突检测。"""

    def __init__(self, fast_path_threshold=None, fast_path_gap=None,
                 evidence_low=None, hybrid_threshold=None, tfidf_threshold=None, conflict_gap=None,
                 llm_fn=None):
        self.fast_path_threshold = fast_path_threshold if fast_path_threshold is not None else FAST_PATH_THRESHOLD
        self.fast_path_gap = fast_path_gap if fast_path_gap is not None else FAST_PATH_GAP
        self.evidence_low = evidence_low if evidence_low is not None else EVIDENCE_LOW
        self.hybrid_threshold = hybrid_threshold if hybrid_threshold is not None else HYBRID_THRESHOLD
        self.tfidf_threshold = tfidf_threshold if tfidf_threshold is not None else TFIDF_THRESHOLD
        self.conflict_gap = conflict_gap if conflict_gap is not None else CONFLICT_GAP
        self.llm_fn = llm_fn  # 可选，默认不使用（确定性优先）

    # ---------- 确定性信号抽取 ----------
    def _signals(self, candidates, query, visual_candidates):
        if not candidates:
            return {"dense_top": 0.0, "dense_second": None, "gap": None,
                    "candidate_count": 0, "rank_disagreement": False, "visual_conflict": False}
        # candidates 是 RRF 融合排序结果，其 [0]/[1] 不代表 dense 分数的 top1/top2。
        # 必须先按 score 降序重排，再取 dense top1/top2 计算 gap。
        dense_ranked = sorted(candidates, key=lambda x: float(x.get("score", 0.0)), reverse=True)
        dense_top = float(dense_ranked[0].get("score", 0.0))
        if len(dense_ranked) >= 2:
            dense_second = float(dense_ranked[1].get("score", 0.0))
            gap = round(dense_top - dense_second, 4)
        else:
            # 单候选：不虚构 dense_second=0.0，否则高分单候选会被错误算成 gap=score → 误触发 fast path
            dense_second = None
            gap = None

        # RRF 排序 top1 与 dense 相似度 top1 是否一致。
        # 注意：rank_disagreement 是【诊断信号】，不单独参与决策——RRF 与 dense 排名不同是正常的
        # （RRF 叠加了 sparse/tfidf），只有当「排序差异 + 分数接近/语义冲突」共同出现时
        # 才由 candidate_conflict 触发 needs_review，绝不因单纯排名不同就 reject。
        dense_top_name = dense_ranked[0]["injury"]
        rrf_top_name = candidates[0]["injury"]
        rank_disagreement = (dense_top_name != rrf_top_name)

        visual_conflict = False
        if visual_candidates:
            text_top = [{"injury": c["injury"], "score": c.get("score", 0.0)} for c in candidates[:3]]
            cd = conflict_detect(text_top, visual_candidates)
            visual_conflict = bool(cd.get("needs_review"))

        return {
            "dense_top": dense_top,
            "dense_second": dense_second,
            "gap": gap,
            "candidate_count": len(candidates),
            "rank_disagreement": rank_disagreement,
            "visual_conflict": visual_conflict,
        }

    # ---------- 主入口 ----------
    def assess(self, candidates, query=None, visual_candidates=None, retries_left=0, retrieval_mode=None):
        """综合信号判定证据是否充分。

        参数：
            candidates: [{"injury", "score", "rrf"?}]，已按 RRF 排序（与 retrieve() 返回一致）
            visual_candidates: [{"name", "confidence"}]（可选，视觉候选）
            retries_left: 剩余重检索次数（决定 need_retry 是否为真）
        """
        if not candidates:
            return {
                "decision": "insufficient", "confidence": 0.0,
                "reason": "无检索候选", "matched_injury": None,
                "need_retry": False, "retry_strategy": None,
                "candidate_conflict": False, "needs_review": False,
                "signals": self._signals([], query, visual_candidates),
            }

        sig = self._signals(candidates, query, visual_candidates)
        retrieval_mode = retrieval_mode or candidates[0].get('retrieval_mode', 'hybrid')
        dense_ranked = sorted(candidates, key=lambda x: float(x.get("score", 0.0)), reverse=True)
        top1 = dense_ranked[0]
        top2 = dense_ranked[1] if len(dense_ranked) >= 2 else None
        matched = candidates[0]["injury"]  # 生成对象取 RRF 融合排序 top1（检索返回的最佳结果）

        # 候选冲突：dense top1≈top2（gap 小）且伤情明显不同，但处置路径真正冲突才 needs_review。
        # 分数接近 + 处置一致（equivalent/compatible）→ 不 review，照常走 sufficient/insufficient。
        candidate_conflict = False
        treatment_rel = None
        if top2 is not None and _is_distinct(top1["injury"], top2["injury"]):
            scores_close = (sig["gap"] is not None) and (sig["gap"] < self.conflict_gap)
            if scores_close:
                treatment_rel = treatment_conflict(top1["injury"], top2["injury"])
                candidate_conflict = treatment_rel in ("partially_conflicting", "conflicting")

        if candidate_conflict:
            return {
                "decision": "conflict", "confidence": sig["dense_top"],
                "reason": f"Top 候选分数接近且处置路径{treatment_rel}（{top1['injury']} vs {top2['injury']}，gap={sig['gap']}）",
                "matched_injury": None, "need_retry": retries_left > 0,
                "retry_strategy": "query_rewrite" if retries_left > 0 else None,
                "candidate_conflict": True, "needs_review": True, "signals": sig,
            }

        # 视觉冲突（文本 vs 视觉 top1 不一致）→ 标记人工复核，但不推翻文本判定
        if sig["visual_conflict"]:
            pass  # 由 router 决定是否标记 needs_review，证据本身仍按 dense 判定

        # TF-IDF scores are not dense semantic scores. Keep their own threshold
        # instead of applying the hybrid 0.50/0.55 decision bands.
        if retrieval_mode == 'tfidf':
            result = {
                "decision": "sufficient" if sig["dense_top"] >= self.tfidf_threshold else "insufficient",
                "confidence": sig["dense_top"],
                "reason": "tfidf score reached the configured fallback threshold"
                    if sig["dense_top"] >= self.tfidf_threshold
                    else "tfidf score is below the configured fallback threshold",
                "matched_injury": matched if sig["dense_top"] >= self.tfidf_threshold else None,
                "need_retry": False,
                "retry_strategy": None,
                "candidate_conflict": False,
                "needs_review": sig["visual_conflict"],
                "signals": {**sig, "retrieval_mode": "tfidf"},
            }
            return result

        if (sig["dense_top"] >= self.fast_path_threshold
                and sig["gap"] is not None and sig["gap"] >= self.fast_path_gap):
            return {
                "decision": "sufficient", "confidence": sig["dense_top"],
                "reason": "快路径：dense 相似度高且 top1 显著领先（存在真实第二候选）", "matched_injury": matched,
                "need_retry": False, "retry_strategy": None,
                "candidate_conflict": False, "needs_review": sig["visual_conflict"], "signals": sig,
            }
        if sig["dense_top"] >= self.hybrid_threshold:
            return {
                "decision": "sufficient", "confidence": sig["dense_top"],
                "reason": "dense 相似度达到判定阈值（低相似度，走全量验证）", "matched_injury": matched,
                "need_retry": False, "retry_strategy": None,
                "candidate_conflict": False, "needs_review": sig["visual_conflict"], "signals": sig,
            }
        if sig["dense_top"] >= self.evidence_low:
            return {
                "decision": "insufficient", "confidence": sig["dense_top"],
                "reason": f"dense 相似度落入灰区 [{self.evidence_low}, {self.hybrid_threshold})，证据不足",
                "matched_injury": None, "need_retry": retries_left > 0,
                "retry_strategy": "query_rewrite" if retries_left > 0 else None,
                "candidate_conflict": False, "needs_review": sig["visual_conflict"], "signals": sig,
            }
        return {
            "decision": "insufficient", "confidence": sig["dense_top"],
            "reason": f"dense 相似度 {sig['dense_top']} 低于灰区下界 {self.evidence_low}，证据不足",
            "matched_injury": None, "need_retry": False, "retry_strategy": None,
            "candidate_conflict": False, "needs_review": sig["visual_conflict"], "signals": sig,
        }
