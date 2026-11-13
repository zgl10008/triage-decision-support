# -*- coding: utf-8 -*-
"""
阶段4：服务降级（Service Degradation）
================================================================
灾害现场系统，任一依赖故障都要有明确降级路径，尽可能提供有限服务、绝不硬答。

覆盖（任务书第 14 节）：
- LLM 不可用       → grounded 确定性降级（忠实度天然=1.0，无需 judge）
- 验证超时          → 保守拒答（不放行未验证的高风险建议）
- 检索不可用        → char-TFIDF 回退（已由 app 的 hybrid→tfidf 回退承担）
- Situation/Evidence LLM 失败 → 各 Agent 内部已确定性兜底（返回保守判定）

注意：本模块只提供「降级动作」，不决定何时触发；触发判定由 router 的 try/except 完成。
"""
import requests

from rag_generator import GroundedGenerator


def classify_llm_error(exc):
    """把 LLM 调用异常归类，供降级决策与 trace 记录。"""
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.HTTPError)):
        return "unavailable"
    return "other"


def grounded_fallback(generator, injury, visual_evidence=None):
    """LLM 不可用 → grounded 确定性降级。

    直接取 output 键动作按救治阶段排序去重，忠实度天然=1.0，不依赖 LLM。
    即使 grounded 也失败，返回空步骤 + 明确 error，不硬给方案。
    """
    try:
        result = generator.generate(injury, visual_evidence=visual_evidence,
                                    mode='grounded', with_judge=False)
        result["degraded"] = True
        result["degraded_reason"] = "llm_unavailable"
        return result
    except Exception as e:  # noqa: BLE001 —— 降级层兜底一切，向上抛会中断整个请求
        return {"injury": injury, "mode": "grounded", "steps": [],
                "error": f"grounded 降级失败：{e}", "degraded": True}


def verification_timeout_reject():
    """验证超时 → 保守拒答，不放行未经验证的高风险建议。"""
    return {
        "success": False,
        "error": "处置建议验证超时，出于安全考虑保守拒答",
        "decision": "reject",
        "failure_type": "verification_timeout",
    }
