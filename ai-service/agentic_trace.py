# -*- coding: utf-8 -*-
"""
阶段4：Agentic RAG 执行轨迹（execution trace）
================================================================
按任务书第 17 节记录完整执行轨迹，用于调试、评测与项目展示。

约束：
- 只记录「归一化后的 query 元信息 + 各阶段决策/分数/耗时」，不记录敏感个人信息。
- 检索可能重试多次，用列表 retrieval_attempts 保存每次 attempt；
  其余单值阶段（situation/evidence/generation/verification）用槽位覆盖式记录。
- 所有计时用 time.perf_counter（单调时钟），latency 单位 ms。
"""
import time
import uuid


class TraceContext:
    """一次 Agentic 请求的轨迹容器。

    用法：
        tr = TraceContext(mode='agentic', input_type='text')
        tr.record('situation_assessment', {...})      # 单值阶段
        tr.add_retrieval_attempt({...})               # 多值阶段
        ...
        tr.to_dict()
    """

    def __init__(self, request_id=None, mode='agentic', input_type='text'):
        self.request_id = request_id or uuid.uuid4().hex[:12]
        self.mode = mode
        self.input_type = input_type
        self._t0 = time.perf_counter()
        self._sections = {}
        self._retrieval_attempts = []
        self.final_decision = None
        self.total_steps = 0

    def record(self, section, payload):
        """记录单值阶段（situation/evidence/generation/verification/...）。"""
        self._sections[section] = payload

    def add_retrieval_attempt(self, payload):
        """追加一次检索 attempt（含 attempt 序号）。"""
        self._retrieval_attempts.append(payload)

    def set_final(self, decision, total_steps):
        self.final_decision = decision
        self.total_steps = total_steps

    def _elapsed_ms(self):
        return int((time.perf_counter() - self._t0) * 1000)

    def to_dict(self):
        d = {
            "request_id": self.request_id,
            "mode": self.mode,
            "input_type": self.input_type,
            "latency_ms": self._elapsed_ms(),
            "total_steps": self.total_steps,
            "final_decision": self.final_decision,
        }
        for section, payload in self._sections.items():
            d[section] = payload
        if self._retrieval_attempts:
            # 兼容任务书 schema：单次重试时也暴露 retrieval_attempt_2 便于阅读
            d["retrieval"] = self._retrieval_attempts[0]
            for i, attempt in enumerate(self._retrieval_attempts[1:], start=2):
                d[f"retrieval_attempt_{i}"] = attempt
            d["retrieval_retry"] = len(self._retrieval_attempts) > 1
            d["retrieval_attempt_count"] = len(self._retrieval_attempts)
        return d
