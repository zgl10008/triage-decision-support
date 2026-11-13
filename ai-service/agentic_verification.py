# -*- coding: utf-8 -*-
"""
阶段4：Verification / Safety Agent —— 生成后安全校验（确定性硬闸门）
================================================================
生成之后必须校验，至少覆盖任务书第 11 节的五类检查：

1. Citation Accuracy —— 每个步骤的引用编号是否真实存在；
2. Faithfulness —— 回答是否超出知识证据（复用 GroundedGenerator 的 lexical + LLM-as-judge）；
3. Unsupported Action —— 是否出现知识库没有依据的处置动作（确定性 lexical grounding）；
4. Forbidden / Unsafe Action —— 是否出现明确危险且知识库未收录的操作（关键词 + KB 权威判定）；
5. Evidence Coverage —— 关键步骤是否都有引用支撑。

设计（安全优先，确定性为主）：
- 本 Agent 的硬闸门全是**确定性**规则：citation 合法性、lexical grounding、禁忌关键词 vs KB 全集。
  LLM-as-judge（faithfulness）只作辅助分数，不单独决定放行——因为 1.5B judge 不可靠。
- 禁忌动作判定「KB 权威」：某危险操作关键词若出现在该伤情的 output 键详情里 → 合法；
  若不在 → 判 forbidden（block，禁止自动重生成）。避免硬编码医疗政策出错。
- 失败分类（failure_type → recommended_action）对应任务书第 12 节：
    citation_error       → revise（修引用/去无效）
    unsupported_action   → revise（删无依据动作）
    insufficient_evidence→ re_retrieve（重新检索）
    forbidden_action     → block（直接阻断）
"""
import re

from rag_generator import GroundedGenerator

# // 复合动作拆分用的分隔符（中英文标点/换行）
_ACTION_SEPARATORS = '，；、。,\n;'
# // 拆分后开头需剥离的连接词（复合动作如"立即止血包扎，并建立静脉通道"）
_ACTION_CONJUNCTIONS = ('并', '然后', '以及', '随后', '再', '同时')

# // 确定性「无依据动作」判定阈值：action 的 n-gram 被引用条目覆盖比例低于此值 → 视为无依据
# // 与 rag_generator.LEXICAL_FALLBACK_THRESHOLD 同口径（0.5）
LEXICAL_SUPPORT_THRESHOLD = 0.5
# // 忠实度通过阈值：overall_faithful 低于此值 → 语义层判失败（多数步骤不被引用支撑）
FAITHFUL_PASS_THRESHOLD = 0.75
# // 高危/侵入性操作关键词：出现在 action 且不在该伤情 output 键全集 → 判 forbidden
FORBIDDEN_KEYWORDS = [
    "截肢", "截指", "截趾", "开胸", "开颅", "剖腹", "气管切开", "气管插管",
    "胸外按压", "除颤", "心肺复苏", "手术切除",
]


class VerificationAgent:
    """生成后安全校验 Agent：确定性硬闸门 + 失败分类。"""

    def __init__(self, lexical_threshold=None, forbidden_keywords=None, faithful_threshold=None):
        self.lexical_threshold = lexical_threshold if lexical_threshold is not None else LEXICAL_SUPPORT_THRESHOLD
        self.forbidden_keywords = forbidden_keywords if forbidden_keywords is not None else FORBIDDEN_KEYWORDS
        self.faithful_threshold = faithful_threshold if faithful_threshold is not None else FAITHFUL_PASS_THRESHOLD

    # ---------- 确定性单步判定 ----------
    @staticmethod
    def _split_atomic_actions(action):
        """把复合动作拆成原子动作（轻量兜底，不改造生成器）。

        例："立即止血包扎，并建立静脉通道" → ["立即止血包扎", "建立静脉通道"]。
        TODO：生成器若未来支持逐原子 action 输出，可改为直接取原子列表，此处仅作兜底。
        局限：无标点的连写（如"止血包扎并建立静脉通道"）不会被拆分，仍按整段 grounding。
        """
        parts = [p.strip() for p in re.split(f'[{_ACTION_SEPARATORS}]', action or '') if p.strip()]
        for lead in _ACTION_CONJUNCTIONS:
            if parts and parts[0].startswith(lead) and len(parts[0]) > len(lead):
                parts[0] = parts[0][len(lead):].strip()
        return parts

    def _step_supported(self, action, refs, source_map):
        """action 是否被其引用的条目在字符级支撑（lexical grounding >= 阈值）。

        复合动作逐原子拆分后分别 grounding，任一关键动作无证据支撑即整步判无依据，
        避免「部分动作被 KB 支持就整步 pass」。
        """
        details = [source_map[c]["detail"] for c in refs if c in source_map]
        if not details:
            return False
        atomic = self._split_atomic_actions(action)
        if len(atomic) <= 1:
            return GroundedGenerator.lexical_grounding(action, details) >= self.lexical_threshold
        return all(
            GroundedGenerator.lexical_grounding(a, details) >= self.lexical_threshold
            for a in atomic
        )

    def _step_forbidden(self, action, full_output):
        """action 是否含禁忌操作且该操作不在伤情 output 全集（KB 权威判定）。"""
        for kw in self.forbidden_keywords:
            if kw in action and not any(kw in d for d in full_output):
                return True
        return False

    # ---------- 过滤无依据步骤（供 router 的 revise 使用） ----------
    def filter_safe_steps(self, steps, source_map):
        """返回 (safe_steps, dropped)，只保留 citation 合法 + 有依据 + 非禁忌的步骤。"""
        valid_refs = set(source_map.keys())
        full_output = [source_map[r]["detail"] for r in valid_refs]
        safe, dropped = [], []
        for s in steps:
            refs = [c for c in s.get("citations", []) if c in valid_refs]
            if (refs
                    and self._step_supported(s["action"], refs, source_map)
                    and not self._step_forbidden(s["action"], full_output)):
                safe.append(dict(s, citations=refs))
            else:
                dropped.append(s["action"])
        return safe, dropped

    # ---------- 三层校验（V5.0：deterministic / grounding / safety） ----------
    def _deterministic_validate(self, steps, source_map):
        """第 1 层：确定性校验 —— citation 合法性 / evidence coverage / unsupported action。"""
        valid_refs = set(source_map.keys())
        invalid_citations = sorted({
            str(c) for s in steps for c in s.get("citations", []) if c not in valid_refs
        })
        cited_count = sum(1 for s in steps if any(c in valid_refs for c in s.get("citations", [])))
        coverage = round(cited_count / len(steps), 3) if steps else 0.0
        unsupported = [
            s["action"] for s in steps
            if not self._step_supported(
                s["action"], [c for c in s.get("citations", []) if c in valid_refs], source_map)
        ]
        return {
            "citation_valid": not invalid_citations,
            "invalid_citations": invalid_citations,
            "coverage": coverage,
            "unsupported_actions": unsupported,
        }

    def _grounding_validate(self, faithfulness):
        """第 2 层：grounding / 忠实度 —— 复用 check_faithfulness 的融合分数，只作辅助。"""
        if not faithfulness:
            return {"faithful_overall": None, "faithful": None}
        faithful_overall = faithfulness.get("overall_faithful")
        return {
            "faithful_overall": faithful_overall,
            "faithful": faithful_overall is not None and faithful_overall >= self.faithful_threshold,
        }

    def _safety_gate(self, steps, source_map):
        """第 3 层：安全硬闸门 —— 危险/侵入性操作（KB 未收录）→ blocked，优先级最高。"""
        valid_refs = set(source_map.keys())
        full_output = [source_map[r]["detail"] for r in valid_refs]
        forbidden = [s["action"] for s in steps if self._step_forbidden(s["action"], full_output)]
        return {"forbidden_actions": forbidden, "blocked": bool(forbidden)}

    # ---------- 主入口 ----------
    def verify(self, steps, source_map, faithfulness=None):
        """三层校验并合成 verdict：Safety Hard Block 优先级最高，其次确定性，最后 grounding。

        参数：
            steps: [{"step", "action", "citations"}]
            source_map: {ref: {"source_id", "category", "field_type", "detail"}}
            faithfulness: GroundedGenerator.check_faithfulness 的结果（可选）
        """
        steps = steps or []
        if not steps:
            return {
                "decision": "fail", "score": 0.0, "citation_valid": False,
                "faithful": False, "unsupported_actions": [], "invalid_citations": [],
                "forbidden_actions": [], "coverage": 0.0, "reason": "无生成步骤",
                "failure_type": "insufficient_evidence", "recommended_action": "reject",
                "safety_blocked": False,
            }

        det = self._deterministic_validate(steps, source_map)
        grd = self._grounding_validate(faithfulness)
        safe = self._safety_gate(steps, source_map)

        # 失败分类（优先级：safety block > citation > unsupported > semantic faithful）
        reason = "通过校验"
        failure_type = None
        recommended_action = None
        decision = "pass"
        if safe["blocked"]:
            decision, failure_type, recommended_action = "fail", "forbidden_action", "block"
            reason = "存在知识库未收录的高危/侵入性操作"
        elif not det["citation_valid"]:
            decision, failure_type, recommended_action = "fail", "citation_error", "revise"
            reason = f"存在无效引用编号：{det['invalid_citations']}"
        elif det["unsupported_actions"]:
            decision, failure_type, recommended_action = "fail", "unsupported_action", "revise"
            reason = f"存在无知识依据的处置动作：{det['unsupported_actions']}"
        elif grd["faithful_overall"] is not None and grd["faithful_overall"] < self.faithful_threshold:
            decision, failure_type, recommended_action = "fail", "insufficient_evidence", "re_retrieve"
            reason = f"忠实度 {grd['faithful_overall']} 低于阈值 {self.faithful_threshold}"

        score = grd["faithful_overall"] if grd["faithful_overall"] is not None else det["coverage"]
        return {
            "decision": decision, "score": round(float(score), 3),
            "citation_valid": det["citation_valid"], "faithful": decision == "pass",
            "unsupported_actions": det["unsupported_actions"], "invalid_citations": det["invalid_citations"],
            "forbidden_actions": safe["forbidden_actions"], "coverage": det["coverage"], "reason": reason,
            "failure_type": failure_type, "recommended_action": recommended_action,
            "safety_blocked": safe["blocked"],
        }
