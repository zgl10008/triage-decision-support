# -*- coding: utf-8 -*-
"""
阶段7：AgentState —— 统一编排状态
================================================================
把 router 各阶段产生的中间状态统一到一个对象里，让编排由状态驱动（而非 step1/step2/... 的
固定顺序）。每次行动（检索/改写/生成/校验/修复）都读状态、写状态，状态转移显式可审计。

最小字段集（指令第 13 节）：
- situation          信息充分性评估结果（retrieval/decision_sufficient 等）
- evidence           证据评估结果（decision/confidence/conflict 等）
- failure_type       失败类型（FailureType 或验证 failure_type）
- retry_count        检索重试次数
- repair_count       受限修复次数
- step_count         已消耗 agent 步数
- action_plan        确定性处置计划（ActionPlan，LLM verbalization 的唯一输入）
- validation_result  验证结果（verdict）
- safety_result      安全硬闸门结果（blocked / forbidden_actions）
- final_status       最终状态（return / reject / ask_info / needs_review / blocked）

注：matched_injury 是【知识库匹配结果】（knowledge-base matching result），非医学诊断；
对外文案用「参考伤情 / 相关知识候选」，避免被解读为诊断结论。
"""
from dataclasses import dataclass, field


@dataclass
class AgentState:
    query: str = ''
    situation: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    failure_type: str = None
    retry_count: int = 0
    repair_count: int = 0
    step_count: int = 0
    action_plan: object = None          # ActionPlan 对象（或 None）
    validation_result: dict = field(default_factory=dict)
    safety_result: dict = field(default_factory=dict)
    final_status: str = None
    # 附加：候选列表 / 命中伤情（内部字段，knowledge-base matching result，非诊断）
    candidates: list = field(default_factory=list)
    matched_injury: str = None

    def to_dict(self):
        return {
            "query": self.query,
            "situation": self.situation,
            "evidence": self.evidence,
            "failure_type": self.failure_type,
            "retry_count": self.retry_count,
            "repair_count": self.repair_count,
            "step_count": self.step_count,
            "action_plan": self.action_plan.to_dict()
                if hasattr(self.action_plan, "to_dict") else self.action_plan,
            "validation_result": self.validation_result,
            "safety_result": self.safety_result,
            "final_status": self.final_status,
            "candidates": self.candidates,
            "matched_injury": self.matched_injury,
        }
