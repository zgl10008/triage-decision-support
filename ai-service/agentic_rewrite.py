# -*- coding: utf-8 -*-
"""
阶段4：Adaptive Retrieval —— Query Rewrite（查询改写）
================================================================
证据不足时，不直接拒答，而是改写 query 后重新进入 Hybrid Retrieval。

设计（遵循「失败可控」）：
- LLM 改写：把口语化/信息不足的原始查询，改写为更规范、更利于检索的伤情描述。
- 确定性兜底：LLM 改写失败 → 返回原始 query（等价于「无进展」），由 router 停止重试并
  转拒答/补信息，绝不编造一个"更好"的 query。
- 重试上限由 router 用 config 的 MAX_RETRIEVAL_RETRY 控制，本模块只负责「改写」这一个动作。
"""
from agentic_config import call_ollama, parse_llm_json, AGENT_TIMEOUT

_REWRITE_PROMPT = """你是现场急救伤情检索的查询改写专家。

【原始查询】{query}
【改写原因】{reason}

任务：把口语化或信息不足的原始查询，改写为更规范、更完整、更利于检索知识库的伤情描述。

要求：
1. 严格保留原意，不得编造原始查询里没有的伤情事实；
2. 尽量使用规范的受伤部位、伤情类型术语（如"头皮裂伤""腹部穿透伤"）；
3. 若原始查询本身已规范，可原样返回。

【输出格式】严格输出 JSON，不要输出任何其他文字：
{{"rewritten_query":"..."}}
"""

# // semantic_gap 的扩展提示词：保留原意 + 补同义规范术语，不新增事实
_SEMANTIC_EXPANSION_PROMPT = """你是现场急救伤情检索的查询扩展专家。

【原始查询】{query}
【扩展原因】{reason}

任务：在保留原意的前提下，扩展查询的语义表达，补充规范的同义伤情术语，帮助检索。

要求：
1. 严格保留原意，不得编造原始查询里没有的伤情事实；
2. 补充同义/近义的规范医学术语（如"气促"补充"呼吸困难、呼吸窘迫"）；
3. 若原始查询已足够规范，可原样返回。

【输出格式】严格输出 JSON，不要输出任何其他文字：
{{"rewritten_query":"..."}}
"""


class QueryRewriter:
    """查询改写器：LLM 改写 + 确定性兜底，按恢复策略选择提示词。"""

    def __init__(self, llm_fn=None):
        self.llm_fn = llm_fn or call_ollama

    def rewrite(self, query, reason=None, strategy='terminology_rewrite'):
        """按恢复策略改写 query，返回 (rewritten_query, via_llm)。LLM 失败返回原 query。

        strategy ∈ {terminology_rewrite, semantic_expansion}。
        missing_information / candidate_conflict / low_evidence 不应走到 rewrite
        （由 router 按 failure_type 路由，rewrite 只承接 lexical/semantic 两种）。
        """
        query = (query or '').strip()
        if not query:
            return query, False
        prompt = (_SEMANTIC_EXPANSION_PROMPT if strategy == 'semantic_expansion'
                  else _REWRITE_PROMPT)
        try:
            raw = self.llm_fn(
                prompt.format(query=query, reason=reason or '证据不足'),
                temperature=0.0, timeout=AGENT_TIMEOUT,
            )
            data = parse_llm_json(raw)
            rewritten = str(data.get('rewritten_query', '')).strip()
            if rewritten:
                return rewritten, True
            return query, False
        except Exception:
            return query, False
