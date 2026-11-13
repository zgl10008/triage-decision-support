# -*- coding: utf-8 -*-
"""
阶段4：Agentic Router —— 状态机编排器（不用 LLM Supervisor）
================================================================
把各判断型 Agent 与确定性 Tool 编排成一条「自适应、证据驱动、安全约束」的管线：

    INPUT_ASSESSMENT → RETRIEVAL → EVIDENCE_ASSESSMENT → (REWRITE → RETRIEVAL)*
        → GENERATION → VERIFICATION → RETURN / REJECT / REVISE / RE-RETRIEVE / BLOCK

核心原则（贯穿全文件）：
- 状态机 + 条件路由，显式、可审计、有次数上限；不引入 LLM Supervisor。
- 确定性模块（检索/聚合/生成/校验）是 Tool，Agent 只做「判断」，判断失败一律确定性兜底。
- 所有循环都有三重约束：请求级检索预算 / MAX_REPLAN / MAX_AGENT_STEPS + LLM timeout + fallback。
- Verification 是确定性硬闸门，Agent/重试/降级都无权绕过；forbidden → 直接 block，禁止自动重生成。
"""
from agentic_config import MAX_RETRIEVAL_RETRY, MAX_REPLAN, MAX_AGENT_STEPS
from agentic_trace import TraceContext
from agentic_state import AgentState
from agentic_situation import SituationAssessmentAgent
from agentic_evidence import EvidenceAssessmentAgent
from agentic_rewrite import QueryRewriter
from agentic_verification import VerificationAgent
from agentic_repair import ConstrainedRepair
from agentic_action_plan import ActionPlanningAgent
from agentic_recovery import diagnose_failure, RECOVERY_STRATEGY
from agentic_fallback import grounded_fallback, classify_llm_error
from multimodal_fusion import build_visual_evidence_block
from rag_generator import GroundedGenerator


class StepLimitExceeded(Exception):
    """agent 步数达到 MAX_AGENT_STEPS 上限，用于在继续执行前中止请求。"""


class AgenticRouter:
    """自适应 Agentic RAG 编排器。依赖全部可注入（供单测 / 服务装配复用）。"""

    def __init__(self, retriever=None, generator=None, situation_agent=None,
                 evidence_agent=None, verification_agent=None, rewriter=None,
                 repairer=None, action_planner=None, top_k=3):
        self.retriever = retriever                      # callable(query, top_k) -> [{injury, score, rrf?}]
        self.generator = generator or GroundedGenerator()
        self.situation = situation_agent or SituationAssessmentAgent()
        self.evidence = evidence_agent or EvidenceAssessmentAgent()
        self.verifier = verification_agent or VerificationAgent()
        self.rewriter = rewriter or QueryRewriter()
        self.repairer = repairer or ConstrainedRepair()
        self.action_planner = action_planner or ActionPlanningAgent()
        self.top_k = top_k

    # ---------- 检索（确定性 Tool，含降级） ----------
    def _retrieve(self, query):
        if self.retriever is None:
            return []
        try:
            results = self.retriever(query, top_k=self.top_k)
            return list(results) if results else []
        except Exception:
            return []  # 检索失败 → 空候选 → 证据不足 → 拒答（安全，不硬答）

    # ---------- 验证（确定性硬闸门，含超时/异常保守拒答） ----------
    def _verify(self, steps, source_map, faithfulness=None):
        """包装 verifier.verify：验证超时/异常 → 保守拒答，绝不放行未验证的高风险建议。"""
        try:
            return self.verifier.verify(steps, source_map, faithfulness)
        except Exception:
            return {
                "decision": "fail", "score": 0.0, "citation_valid": False, "faithful": False,
                "unsupported_actions": [], "invalid_citations": [], "forbidden_actions": [],
                "coverage": 0.0, "reason": "验证异常，保守拒答",
                "failure_type": "verification_timeout", "recommended_action": "reject",
            }

    # ---------- ActionPlan（确定性白名单） ----------
    def _build_action_plan(self, matched, risk_flags=None):
        """从命中伤情（知识库匹配结果，非诊断）确定性提取 ActionPlan。KB 缺记录 → None。"""
        try:
            return self.action_planner.plan(matched, risk_flags=risk_flags)
        except Exception:
            return None

    @staticmethod
    def _action_plan_source_map(action_plan):
        """把 ActionPlan 的统一引用表转成验证用的 source_map（ref 同源，保证引用编号一致）。"""
        return {
            c.ref: {"source_id": c.source_id, "category": c.category,
                    "field_type": "output", "detail": c.detail}
            for c in action_plan.citations
        }

    # ---------- 生成（ActionPlan → verbalize 优先，否则 generate；统一返回 source_map） ----------
    def _generate_for(self, matched, evidence_text, mode, with_judge, trace, tick, risk_flags=None):
        """统一生成入口：返回 (generation, source_map, action_plan)。

        V5.0：LLM 只表达 ActionPlan 白名单（verbalize），失败 → grounded fallback；
        生成器不支持 verbalize 时退回 generate()（向后兼容）。source_map 与 generation 同源。
        """
        action_plan = self._build_action_plan(matched, risk_flags)
        use_verbalize = action_plan is not None and hasattr(self.generator, 'verbalize')
        tick()
        try:
            if use_verbalize:
                generation = self.generator.verbalize(
                    action_plan, visual_evidence=evidence_text, with_judge=with_judge)
            else:
                generation = self.generator.generate(
                    matched, visual_evidence=evidence_text, mode=mode, with_judge=with_judge)
        except Exception as e:
            err_type = classify_llm_error(e)
            trace.record('llm_failure', {"error_type": err_type, "error": str(e)})
            generation = grounded_fallback(self.generator, matched, visual_evidence=evidence_text)

        if use_verbalize:
            source_map = self._action_plan_source_map(action_plan)
        else:
            source_map = self.generator.build_context(matched)[1]
        return generation, source_map, action_plan

    # ---------- 主入口 ----------
    def run(self, query, visual_evidence=None, generation_mode='llm', with_judge=True, input_type='text'):
        trace = TraceContext(mode='agentic', input_type=input_type)
        state = AgentState(query=query or '')
        steps = 0
        # 请求级检索预算：整个请求最多 max_retrieval_attempts 次检索（initial + retries）。
        # 无论 retry 由 Evidence 还是 Verification 的 re_retrieve 触发，共享同一预算，
        # 避免各阶段各自拥有独立 retry budget 导致总检索次数超过 max_retrieval_retry。
        budget = {'retrieval_attempts': 0,
                  'max_retrieval_attempts': MAX_RETRIEVAL_RETRY + 1}

        def tick():
            """执行下一个 agent 动作前调用：已达步数上限则抛 StepLimitExceeded 中止，否则计数 +1。

            在「执行下一步之前」检查预算，杜绝先超预算再事后发现。
            """
            nonlocal steps
            if steps >= MAX_AGENT_STEPS:
                trace.record('step_limit_exceeded', {"steps": steps, "limit": MAX_AGENT_STEPS})
                raise StepLimitExceeded(MAX_AGENT_STEPS)
            steps += 1
            return steps

        try:
            # 视觉候选（供证据冲突检测）
            visual_candidates = None
            evidence_text = None
            if visual_evidence and visual_evidence.get('injury_candidates'):
                visual_candidates = [
                    {"name": str(c.get("name", "")).strip(), "confidence": float(c.get("confidence", 0.0))}
                    for c in visual_evidence["injury_candidates"]
                    if str(c.get("name", "")).strip()
                ]
                evidence_text = build_visual_evidence_block(visual_evidence)

            # 1) INPUT_ASSESSMENT —— 信息充分性判断（确定性快路径优先）
            tick()
            situation = self.situation.assess(query, visual_evidence)
            state.situation = situation
            trace.record('situation_assessment', situation)

            # 2) RETRIEVAL + 3) EVIDENCE —— 自适应重检索循环（FailureType 驱动，请求级预算）
            current_query = situation.get('normalized_query') or (query or '')
            candidates, evidence = self._adaptive_retrieve(
                current_query, visual_candidates, trace, tick, budget, situation)
            state.evidence = evidence
            state.candidates = candidates
            state.retry_count = max(0, budget['retrieval_attempts'] - 1)

            matched = evidence.get('matched_injury') if evidence.get('decision') == 'sufficient' else None

            # 候选冲突：即使 dense >= 阈值也不硬答 → 保守拒答 + 人工复核提示
            if evidence.get('decision') == 'conflict':
                state.failure_type = 'candidate_conflict'
                state.final_status = 'needs_review'
                return self._reject(
                    trace, steps, state,
                    decision='needs_review',
                    reason=evidence.get('reason', '候选冲突，需人工复核'),
                    candidates=candidates, evidence=evidence, situation=situation,
                )
            # 严重视觉冲突（文本 vs 视觉 top1 完全不一致）→ 不自动生成高风险建议，转人工复核
            if matched is not None and evidence.get('needs_review'):
                state.failure_type = 'candidate_conflict'
                state.final_status = 'needs_review'
                return self._reject(
                    trace, steps, state,
                    decision='needs_review',
                    reason='文本与视觉判断严重冲突，需人工复核',
                    candidates=candidates, evidence=evidence, situation=situation,
                )

            if matched is None:
                # 证据不足 → 区分「信息本身不足」与「检索不到」
                if situation.get('status') == 'insufficient':
                    state.failure_type = 'missing_information'
                    state.final_status = 'ask_info'
                    return self._reject(
                        trace, steps, state,
                        decision='ask_info',
                        reason='现场信息不足，无法可靠确定参考伤情',
                        candidates=candidates, evidence=evidence, situation=situation,
                        missing_information=situation.get('missing_information', []),
                    )
                state.failure_type = diagnose_failure(evidence, situation, candidates, current_query)
                state.final_status = 'reject'
                return self._reject(
                    trace, steps, state,
                    decision='reject',
                    reason=evidence.get('reason', '证据不足，拒绝给出不可靠建议'),
                    candidates=candidates, evidence=evidence, situation=situation,
                )

            # 4) GENERATION —— ActionPlan → verbalize（LLM 只表达白名单），否则 generate
            generation, source_map, action_plan = self._generate_for(
                matched, evidence_text, generation_mode, with_judge, trace, tick,
                risk_flags=situation.get('risk_flags'))
            state.action_plan = action_plan

            # 5) VERIFICATION + 失败驱动重规划（上限 MAX_REPLAN）
            tick()
            verdict = self._verify(generation.get('steps', []), source_map,
                                   generation.get('faithfulness'))
            trace.record('verification', verdict)

            # _handle_verification 可能 re_retrieve 改 matched/source_map/action_plan，统一取回保证同源
            final_decision, generation, matched, source_map, action_plan, verdict, replan = \
                self._handle_verification(
                    verdict, generation, matched, source_map, action_plan, trace, tick,
                    current_query=current_query, visual_candidates=visual_candidates,
                    evidence_text=evidence_text, generation_mode=generation_mode, with_judge=with_judge,
                    budget=budget, situation=situation,
                )

            state.repair_count = replan
            state.action_plan = action_plan
            state.validation_result = verdict
            state.safety_result = {
                "blocked": verdict.get('safety_blocked', False),
                "forbidden_actions": verdict.get('forbidden_actions', []),
            }
            if verdict.get('failure_type'):
                state.failure_type = verdict.get('failure_type')
            state.final_status = final_decision
            state.step_count = steps
            state.matched_injury = matched

            trace.set_final(final_decision, steps)
            trace.record('generation', {
                "injury": matched, "mode": generation.get('mode'),
                "steps_count": len(generation.get('steps', [])),
                "degraded": generation.get('degraded', False),
            })
            if generation.get('error'):
                trace.record('generation_error', generation['error'])

            response = {
                "success": final_decision == 'return',
                "pipeline": "agentic",
                "query": query,
                # matched_injury 是知识库匹配结果（knowledge-base matching result），非医学诊断；
                # 对外文案用「参考伤情 / 相关知识候选」，避免被解读为诊断结论。
                "matched_injury": matched,
                "candidate_conditions": [matched] if matched else [],
                "similarity_score": evidence.get('confidence'),
                "retrieval_mode": evidence.get('signals', {}).get('retrieval_mode', 'hybrid'),
                "mode": generation.get('mode', generation_mode),
                "degraded": generation.get('degraded', False),
                "steps": generation.get('steps', []),
                "sources": generation.get('sources', []),
                "faithfulness": generation.get('faithfulness', {}),
                "verification": verdict,
                "situation": situation,
                "evidence": evidence,
                "final_decision": final_decision,
                "state": state.to_dict(),
            }
            if generation.get('error'):
                response['generation_error'] = generation['error']
            if situation.get('status') == 'insufficient':
                response['needs_more_info'] = True
                response['missing_information'] = situation.get('missing_information', [])
                response['risk_flags'] = situation.get('risk_flags', [])
            if situation.get('safety_critical_missing'):
                # 检索有结果但缺安全关键信息（如头部伤未提供意识状态）→ 透出并标记，不静默放行
                response['needs_more_info'] = True
                response['safety_critical_missing'] = situation.get('safety_critical_missing')
            response["trace"] = trace.to_dict()
            return response
        except StepLimitExceeded:
            # 步数预算在「执行下一步之前」被击穿 → 已记录 step_limit_exceeded，安全中止
            state.step_count = steps
            state.final_status = 'reject'
            return self._reject(
                trace, steps, state,
                decision='reject',
                reason=f'达到最大 agent 步数上限（{MAX_AGENT_STEPS}），为安全中止',
            )

    # ---------- 自适应检索循环（FailureType 驱动） ----------
    def _adaptive_retrieve(self, query, visual_candidates, trace, tick, budget, situation=None):
        candidates = []
        evidence = {"decision": "insufficient", "confidence": 0.0, "reason": "检索预算已耗尽",
                    "matched_injury": None, "need_retry": False, "retry_strategy": None,
                    "candidate_conflict": False, "needs_review": False, "signals": {}}
        current_query = query
        rewrite_used = False

        while budget['retrieval_attempts'] < budget['max_retrieval_attempts']:
            tick()
            candidates = self._retrieve(current_query)
            budget['retrieval_attempts'] += 1
            dense_top = float(candidates[0].get('score', 0.0)) if candidates else 0.0
            trace.add_retrieval_attempt({
                "attempt": budget['retrieval_attempts'], "query": current_query,
                "candidate_count": len(candidates), "dense_top_score": dense_top,
                "top_candidates": [c["injury"] for c in candidates[:3]],
            })

            retries_left = budget['max_retrieval_attempts'] - budget['retrieval_attempts']
            tick()
            retrieval_mode = candidates[0].get('retrieval_mode', 'hybrid') if candidates else 'unknown'
            evidence = self.evidence.assess(candidates, current_query,
                                            visual_candidates=visual_candidates,
                                            retries_left=retries_left,
                                            retrieval_mode=retrieval_mode)
            trace.record('evidence_assessment', evidence)

            if evidence.get('decision') == 'sufficient':
                break
            if not evidence.get('need_retry') or retries_left <= 0:
                break

            # FailureType 决定恢复策略：lexical_gap→术语改写，semantic_gap→语义扩展；
            # missing_information / candidate_conflict / low_evidence 禁止 rewrite（安全优先）。
            failure_type = diagnose_failure(evidence, situation, candidates, current_query)
            strategy = RECOVERY_STRATEGY.get(failure_type)
            trace.record('failure_diagnosis', {"failure_type": failure_type, "strategy": strategy})
            if strategy not in ('terminology_rewrite', 'semantic_expansion'):
                break  # 不 rewrite（ask_info / conflict_analysis / safe_fallback）

            tick()
            rewritten, via_llm = self.rewriter.rewrite(current_query, evidence.get('reason'),
                                                       strategy=strategy)
            trace.record('query_rewrite', {"from": current_query, "to": rewritten,
                                           "via_llm": via_llm, "strategy": strategy})
            if rewritten and rewritten != current_query:
                current_query = rewritten
                rewrite_used = True
            else:
                break  # 改写无进展，停止重试

        if rewrite_used:
            trace.record('retrieval_retry', True)
        return candidates, evidence

    # ---------- 失败驱动重规划 ----------
    def _handle_verification(self, verdict, generation, matched, source_map, action_plan, trace, tick,
                             current_query, visual_candidates, evidence_text,
                             generation_mode, with_judge, budget, situation=None):
        """验证失败 → 根据失败原因处理（revise / re_retrieve / block / reject），上限 MAX_REPLAN。

        返回 (final_decision, generation, matched, source_map, action_plan, verdict, replan)。
        re_retrieve 改写命中新伤情时，matched/source_map/action_plan/generation/verdict 同步更新，
        保证最终 response 全部来自同一轮结果，杜绝「generation 是 injury B、matched_injury 是 injury A」。
        """
        replan = 0
        final_decision = None
        # max_replan 语义：最多允许重新规划多少次（不是最多执行多少轮）。
        # 用 < 而非 <=：MAX_REPLAN=0 → 不 replan；=1 → 最多一次。
        while verdict.get('decision') == 'fail' and replan < MAX_REPLAN:
            rec = verdict.get('recommended_action')

            if rec == 'block':
                # 高危/禁忌 → 直接阻断，禁止自动重生成（blocked 不进 repair）
                final_decision = 'blocked'
                break

            if rec == 'revise':
                # 受限修复（delete_claim / replace_wording / attach_citation，不新增动作）
                repair = self.repairer.repair(generation.get('steps', []), source_map, verdict)
                safe_steps = repair['steps']
                if not safe_steps:
                    final_decision = 'reject'
                    break
                generation = dict(generation, steps=safe_steps)
                tick()
                verdict = self._verify(safe_steps, source_map,
                                       generation.get('faithfulness'))
                trace.record('verification', verdict)
                replan += 1
                continue

            if rec == 're_retrieve':
                # 证据不足 → 改写重检索（若有请求级预算），否则拒答
                if budget['retrieval_attempts'] >= budget['max_retrieval_attempts'] or not current_query:
                    final_decision = 'reject'
                    break
                tick()
                rewritten, via_llm = self.rewriter.rewrite(current_query, '证据不足，重新检索')
                trace.record('query_rewrite', {"from": current_query, "to": rewritten, "via_llm": via_llm})
                if not rewritten or rewritten == current_query:
                    final_decision = 'reject'
                    break
                candidates, evidence = self._adaptive_retrieve(
                    rewritten, visual_candidates, trace, tick, budget, situation)
                if evidence.get('decision') != 'sufficient' or not evidence.get('matched_injury'):
                    final_decision = 'reject'
                    break
                new_matched = evidence['matched_injury']
                generation, source_map, action_plan = self._generate_for(
                    new_matched, evidence_text, generation_mode, with_judge, trace, tick,
                    risk_flags=(situation or {}).get('risk_flags'))
                matched = new_matched
                tick()
                verdict = self._verify(
                    generation.get('steps', []), source_map,
                    generation.get('faithfulness'))
                trace.record('verification', verdict)
                replan += 1
                continue

            # 其余（reject 等）→ 直接拒答
            final_decision = 'reject'
            break

        if final_decision is None:
            final_decision = 'return' if verdict.get('decision') == 'pass' else 'reject'

        trace.record('replan_count', replan)
        return final_decision, generation, matched, source_map, action_plan, verdict, replan

    # ---------- 拒答响应 ----------
    def _reject(self, trace, steps, state, decision, reason, candidates=None, evidence=None,
                situation=None, missing_information=None):
        trace.set_final(decision, steps)
        resp = {
            "success": False,
            "pipeline": "agentic",
            "error": reason,
            "final_decision": decision,
            "candidates": candidates or [],
            "state": state.to_dict(),
        }
        if missing_information:
            resp["needs_more_info"] = True
            resp["missing_information"] = missing_information
        if situation:
            resp["risk_flags"] = situation.get("risk_flags", [])
            if situation.get('safety_critical_missing'):
                resp["safety_critical_missing"] = situation.get('safety_critical_missing')
        resp["trace"] = trace.to_dict()
        return resp
