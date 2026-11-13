# -*- coding: utf-8 -*-
"""
阶段6：Constrained Repair —— 生成后受限修复（确定性，不新增医学动作）
================================================================
验证失败（citation_error / unsupported_action）后，用三种受限操作修复步骤，绝不自造动作：

- delete_claim      整步无任何 KB 条目可支撑 → 删除该 claim
- replace_wording   复合动作中部分子句无依据 → 仅保留有依据子句（删无依据子句），不写新文本
- attach_citation   动作有依据但引用编号无效/缺失 → 改挂支撑它的合法引用

红线（指令第 10 节）：
- repair 不得新增医学动作：三种操作只「删」或「改挂引用」，从不合成新动作。
- forbidden_action（安全硬闸门）不进 repair，直接 block。
- insufficient_evidence 不进 repair，走 re_retrieve。
- MAX_REPAIR_RETRY = 1：最多修一次，避免无限修补。
"""
from rag_generator import GroundedGenerator
from agentic_verification import VerificationAgent, LEXICAL_SUPPORT_THRESHOLD

MAX_REPAIR_RETRY = 1

DELETE_CLAIM = "delete_claim"
REPLACE_WORDING = "replace_wording"
ATTACH_CITATION = "attach_citation"


class ConstrainedRepair:
    """确定性受限修复器：只删 claim / 只改挂引用，绝不新增动作。"""

    def __init__(self, lexical_threshold=None, max_retry=None):
        self.lexical_threshold = lexical_threshold if lexical_threshold is not None else LEXICAL_SUPPORT_THRESHOLD
        self.max_retry = max_retry if max_retry is not None else MAX_REPAIR_RETRY

    @staticmethod
    def _split(action):
        return VerificationAgent._split_atomic_actions(action)

    def repair(self, steps, source_map, verification):
        """根据验证结果做受限修复。

        参数：
            steps: [{"action", "citations"}]
            source_map: {ref: {"detail", ...}}
            verification: VerificationAgent.verify 的结果（含 failure_type）

        返回 dict：{steps, ops, retries_used, repaired}
        """
        failure_type = verification.get('failure_type') if verification else None
        # 安全硬闸门 block 不进 repair；evidence 不足走 re_retrieve 也不 repair。
        if failure_type in ('forbidden_action', 'insufficient_evidence', None):
            return {"steps": steps, "ops": [], "retries_used": 0, "repaired": False}

        valid_refs = set(source_map.keys())
        details = {r: source_map[r]["detail"] for r in valid_refs}

        repaired, ops = [], []
        for s in steps:
            action = s.get("action", "")
            atomic = self._split(action) or [action]
            kept_parts, kept_refs = [], []
            for part in atomic:
                supporting = [
                    r for r, d in details.items()
                    if GroundedGenerator.lexical_grounding(part, [d]) >= self.lexical_threshold
                ]
                if supporting:
                    kept_parts.append(part)
                    kept_refs.append(supporting[0])

            if not kept_parts:
                # 无任何 KB 条目能支撑整步 → 删除
                ops.append({"op": DELETE_CLAIM, "action": action})
                continue

            new_action = "，".join(kept_parts) if len(kept_parts) > 1 else kept_parts[0]
            new_refs = list(dict.fromkeys(kept_refs))  # 去重保序
            if new_action != action:
                op = REPLACE_WORDING   # 删除了无依据子句，未写新文本
            else:
                op = ATTACH_CITATION   # 动作未变，只改挂合法引用
            repaired.append({"action": new_action, "citations": new_refs})
            ops.append({"op": op, "action": action, "repaired": new_action})

        return {
            "steps": repaired,
            "ops": ops,
            "retries_used": 1 if ops else 0,
            "repaired": bool(ops),
        }
