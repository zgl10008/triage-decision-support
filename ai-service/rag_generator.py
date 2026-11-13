# -*- coding: utf-8 -*-
"""
阶段3：Grounded 生成模块（引用溯源 + 结构化输出 + 忠实度校验）
================================================================
在检索(阶段2)召回伤情后，本模块负责"生成"环节的三大升级：

1. 引用溯源（citation）：知识条目编号注入 [1][2]…，生成步骤必须携带 citations，
   最终把局部编号映射回 source_id，实现"每句建议 → 知识库源头"可追溯。
2. 结构化输出（structured）：约束 LLM 输出 JSON Schema（steps/action/citations），
   并对解析结果做字段级校验（action 非空、citations 编号合法）。
3. 忠实度校验（faithfulness）：双层校验——
   (a) 字符级 lexical grounding（确定性，高精度捕获"编造知识库没有的词"）
   (b) LLM-as-judge 语义蕴含（处理同义改写，如"止痛"="镇痛"）
   两层互补：lexical 抓明显幻觉，judge 抓语义漂移。

关键设计（字段分层语义的延伸）：
- 只有 output 键（现场急救/紧急救治/早期治疗）是可引用的"步骤来源"；
  recall(临床特点) / inference(伤势/并发症) 只作为"伤情背景"喂给模型做判断，不编号、不可引用。
- 提供两种生成模式：
  * grounded（确定性基线）：步骤直接取 output 键动作，按救治阶段排序+去重，忠实度天然=1.0
  * llm（LLM 合成，默认）：从候选动作中选取/排序/融合并引用，再由忠实度校验兜底

与基线 app.call_deepseek_model 对齐：同样走 config.ini 动态读取
Ollama 地址，无硬编码；但输出从"自由文本分行"升级为"结构化 + 引用 + 校验"。
"""
import configparser
import json
import os
import re
import sys
import traceback

import requests

# // ------------------------------
# // 动态读取配置
# // ------------------------------
config = configparser.ConfigParser()
current_file_dir = os.path.dirname(os.path.abspath(__file__))
config.read(os.path.join(current_file_dir, 'config.ini'), encoding='utf-8')

OLLAMA_HOST = config.get('ollama_service', 'ipAddress')
OLLAMA_PORT = config.getint('ollama_service', 'port')
OLLAMA_API_PATH = config.get('ollama_service', 'api_path')
OLLAMA_MODEL_NAME = config.get('ollama_service', 'model_name')
OLLAMA_TIMEOUT = config.getint('ollama_service', 'request_timeout')
NETWORK_HTTP_SCHEME = config.get('network_defaults', 'http_scheme')
OLLAMA_FULL_API_URL = f"{NETWORK_HTTP_SCHEME}://{OLLAMA_HOST}:{OLLAMA_PORT}{OLLAMA_API_PATH}"

# // 生成步骤上限：与基线 max_advice_lines 对齐，避免弱模型"整表倒出"
MAX_ADVICE_LINES = config.getint('match_service', 'max_advice_lines')

# // 知识库记录（阶段0 已打平为 kb_records.json，含 source_id + field_type 分层）
KB_RECORDS_PATH = os.path.join(current_file_dir, 'kb', 'kb_records.json')

# // 救治阶段排序：现场急救(现场最急) > 紧急救治 > 早期治疗
STAGE_ORDER = {'现场急救': 0, '紧急救治': 1, '早期治疗': 2}

# // grounded 生成要求低随机性；忠实度校验用最低温度求稳定判定
GENERATION_TEMPERATURE = 0.2
FAITHFULNESS_TEMPERATURE = 0.0

# // 忠实度决策融合阈值（lexical 为主 gate，judge 仅作灰区语义佐证）：
# //   lexical >= 0.9（近逐字复制）→ 直接判忠实
# //   0.5 <= lexical < 0.9 且 judge=True → 同义改写，语义佐证后判忠实
# //   其余 → 不忠实（引用无法支撑：编造 / 错引 / 空引用）
LEXICAL_GROUNDED_THRESHOLD = 0.9
LEXICAL_FALLBACK_THRESHOLD = 0.5


def _print(*args, **kwargs):
    """控制台输出适配：Windows 下统一 UTF-8，避免中文乱码。"""
    console_encoding = getattr(getattr(sys, "stdout", None), "encoding", None) or "utf-8"
    safe_args = [str(a).encode(console_encoding, errors="replace").decode(console_encoding, errors="replace")
                 if isinstance(a, str) else a for a in args]
    print(*safe_args, **kwargs)


class GroundedGenerator:
    """阶段3 grounded 生成器：引用溯源 + 结构化 + 双层忠实度校验。"""

    def __init__(self, records_path=None, model_name=None):
        self.records_path = records_path or KB_RECORDS_PATH
        self.model_name = model_name or OLLAMA_MODEL_NAME
        self._records = None

    # ---------- 知识库加载 ----------
    def _load_records(self):
        if self._records is None:
            with open(self.records_path, encoding='utf-8') as f:
                self._records = json.load(f)
        return self._records

    # ---------- 上下文构造：背景(不编号) + 候选动作(编号，唯一可引用来源) ----------
    def build_context(self, injury_type):
        """拆分为伤情背景与候选动作，返回 (context_text, source_map)。

        source_map 只映射 output 键动作（编号 [1..N]）；recall/inference 只作背景，不可引用。
        """
        records = [r for r in self._load_records() if r['injury_type'] == injury_type]
        if not records:
            return "", {}

        actions = [r for r in records if r['field_type'] == 'output']
        background = [r for r in records if r['field_type'] in ('inference', 'recall')]
        if not actions:
            return "", {}

        # 动作按救治阶段排序：现场急救 → 紧急救治 → 早期治疗
        actions.sort(key=lambda r: STAGE_ORDER.get(r['category'], 99))

        bg_lines = [f"- （{r['category']}）{r['detail']}" for r in background]
        lines = []
        source_map = {}
        for i, r in enumerate(actions, 1):
            lines.append(f"[{i}]（{r['category']}）{r['detail']}")
            source_map[i] = {
                "source_id": r['source_id'],
                "category": r['category'],
                "field_type": r['field_type'],
                "detail": r['detail'],
            }

        parts = []
        if bg_lines:
            parts.append("【伤情背景】（仅供参考判断，不作为步骤来源）\n" + "\n".join(bg_lines))
        parts.append("【候选处置动作】（唯一可作为步骤内容的来源，[编号] 为引用编号）\n" + "\n".join(lines))
        return "\n\n".join(parts), source_map

    # ---------- 确定性 grounded 基线 ----------
    def grounded_steps(self, injury_type):
        """确定性基线：直接取 output 键动作，按阶段排序 + 去重，忠实度天然=1.0。"""
        context, source_map = self.build_context(injury_type)
        if not source_map:
            return []
        seen = set()
        steps = []
        for ref in sorted(source_map):
            detail = source_map[ref]["detail"]
            if detail in seen:
                continue  # 去重：同一动作跨阶段重复（如"常规后送"），保留最早阶段
            seen.add(detail)
            steps.append({"step": len(steps) + 1, "action": detail, "citations": [ref]})
        return steps

    # ---------- Verbalization（LLM 只表达 ActionPlan，不选动作） ----------
    def _build_verbalization_prompt(self, action_plan, visual_evidence=None):
        """把 ActionPlan 组织成「白名单 + 升级 + 禁忌 + 危险信号」约束提示词。

        核心约束：LLM 只能从白名单动作里表达，不得新增动作、不得删除安全必需动作、
        不得改变语义、不得添加 KB 未支持的医学判断。
        """
        def fmt(actions):
            lines = []
            for a in actions:
                refs = ",".join(str(r) for r in a.citations)
                head = f"[{refs}]（{a.stage}）" if a.stage else f"[{refs}] "
                lines.append(f"{head}[action_id={a.action_id}] {a.action}")
            return "\n".join(lines)

        parts = ["【处置动作白名单】（你只能从中选取动作表达，编号为引用编号）\n" + fmt(action_plan.supported_actions)]
        if action_plan.escalation_conditions:
            parts.append("【升级处置】（出现危险信号时，以“若出现XX需立即XX”形式条件性表达）\n"
                         + fmt(action_plan.escalation_conditions))
        if action_plan.red_flags:
            parts.append("【危险信号】（需警惕的恶化表现，仅作提示，不是处置动作）\n"
                         + "、".join(a.action for a in action_plan.red_flags))
        if action_plan.contraindicated_actions:
            parts.append("【禁忌事项】（只能以“避免/禁止XX”形式提示，不得作为处置步骤）\n"
                         + fmt(action_plan.contraindicated_actions))
        if visual_evidence:
            parts.append(f"【现场观察证据】\n{visual_evidence}")
        parts.append(
            "【任务】把白名单动作组织成现场急救处置步骤的自然语言表达。\n"
            "【硬性要求】\n"
            "1. 只能使用白名单里的动作，不得新增任何白名单之外的动作；\n"
            "2. 可排序、合并相近动作、改写成更自然的措辞、增加连接词；\n"
            "3. 不得删除安全必需动作（白名单动作都是安全必需）；\n"
            "4. 禁忌事项只能以“避免XX”形式提示，不得作为处置步骤；\n"
            "5. 升级处置配合危险信号条件性表达；\n"
            "6. 每条 action 引用对应编号。\n"
            "【输出格式】严格输出 JSON，不要输出任何其他文字：\n"
            '{"steps":[{"step":1,"action_id":"act_xxx"}]}'
        )
        return "\n\n".join(parts)

    def _validate_verbalized_steps(self, data, action_plan):
        """校验 verbalized steps 只能来自 ActionPlan 白名单/升级动作（字符级覆盖）。

        每个 step 的 action 必须能被某个白名单/升级动作在字符级覆盖（>= LEXICAL_FALLBACK_THRESHOLD），
        否则丢弃——这是「LLM 不得新增医学动作」的硬约束。citations 只保留 ActionPlan 内合法编号。
        """
        allowed = {
            a.action_id: a
            for a in action_plan.supported_actions + action_plan.escalation_conditions
        }
        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError("steps 字段必须是列表")
        valid = []
        for s in raw_steps[:MAX_ADVICE_LINES]:
            if not isinstance(s, dict):
                continue
            action_id = str(s.get("action_id", "")).strip()
            selected = allowed.get(action_id)
            if selected is None:
                continue
            # The model may choose and order IDs, but server-side data owns the
            # final action text and citations.
            valid.append({
                "step": len(valid) + 1,
                "action_id": selected.action_id,
                "action": selected.action,
                "citations": list(selected.citations),
            })
        return valid

    def _plan_grounded_steps(self, action_plan):
        """grounded fallback：白名单动作按阶段顺序直接转步骤（忠实度天然 1.0）。"""
        steps = []
        for a in action_plan.supported_actions:
            steps.append({
                "step": len(steps) + 1,
                "action_id": a.action_id,
                "action": a.action,
                "citations": list(a.citations),
            })
        return steps

    def verbalize(self, action_plan, visual_evidence=None, with_judge=True):
        """把 ActionPlan 转成自然语言处置步骤（LLM 只做措辞，不选动作）。

        LLM 失败或输出全被白名单过滤 → grounded fallback（白名单直出，不重新让 LLM 自由生成）。
        """
        injury = action_plan.candidate_conditions[0] if action_plan.candidate_conditions else None
        if not action_plan or not action_plan.supported_actions:
            return {"injury": injury, "mode": "verbalize", "steps": [],
                    "error": "ActionPlan 无白名单动作"}

        source_map = {c.ref: {"source_id": c.source_id, "category": c.category,
                              "field_type": "output", "detail": c.detail}
                      for c in action_plan.citations}

        degraded = False
        try:
            prompt = self._build_verbalization_prompt(action_plan, visual_evidence)
            raw = self._call_ollama(prompt, temperature=GENERATION_TEMPERATURE)
            data = self._parse_json(raw)
            steps = self._validate_verbalized_steps(data, action_plan)
            if not steps:
                steps = self._plan_grounded_steps(action_plan)
                degraded = True
        except Exception:
            steps = self._plan_grounded_steps(action_plan)
            degraded = True

        result = {
            "injury": injury,
            "mode": "verbalize",
            "steps": steps,
            "sources": self._collect_sources(steps, source_map),
            "degraded": degraded,
        }
        result["faithfulness"] = self.check_faithfulness(None, steps, source_map, with_judge=with_judge)
        return result

    # ---------- 提示词构造 ----------
    def _build_generation_prompt(self, injury_type, context, visual_evidence=None):
        prompt = f"""你是一名拥有丰富现场救援经验的灾害现场医疗急救专家。

【伤情名称】{injury_type}

{context}
"""
        if visual_evidence:
            prompt += f"\n【现场观察证据】\n{visual_evidence}\n"
        prompt += f"""
【任务】从【候选处置动作】中选取最关键的动作，组织成现场急救处置步骤。

【硬性要求】
1. 步骤内容只能来自【候选处置动作】，每条 action 必须与候选动作一致或忠实改写，并引用对应 [编号]
2. 按现场急救优先级排序：优先保命、止血、防感染；结合【伤情背景】取舍（如伤势轻微则不必后送/输血）
3. 每条 action 必须是"动词开头的中文处置动作"，直接给出可执行动作
4. 严禁输出"根据…选择…"、"如…等"这类元描述；严禁输出步骤标题、解释或客套话
5. 最多输出 {MAX_ADVICE_LINES} 条步骤，可把相近动作合并为一条并同时引用多个编号
6. 严禁编造【候选处置动作】之外的内容

【输出格式】严格输出 JSON，不要输出任何其他文字：
{{"steps":[{{"step":1,"action":"...","citations":[2,4]}},{{"step":2,"action":"...","citations":[3]}}]}}
"""
        return prompt

    def _build_faithfulness_prompt(self, cited_context, steps):
        steps_json = json.dumps(steps, ensure_ascii=False)
        return f"""【被引用的知识条目】（[编号] 为引用编号）
{cited_context}

【待校验的生成步骤】
{steps_json}

【任务】逐条判断下面每个 step 的 action 是否被其 citations 指向的知识条目支撑：
- faithful=true 表示 action 内容完全由 citations 条目支撑（允许同义改写，如"止痛"="镇痛"）
- faithful=false 表示 action 存在编造、与条目矛盾、或引用条目与 action 无关

【硬性要求】必须对【待校验步骤】中的每一个 step 都输出一条判定，results 数组长度必须等于 step 总数，不要遗漏。

【输出格式】严格输出 JSON，不要输出任何其他文字：
{{"results":[{{"step":1,"faithful":true,"reason":"..."}},{{"step":2,"faithful":false,"reason":"..."}}]}}
"""

    # ---------- Ollama 调用 ----------
    def _call_ollama(self, prompt, temperature=GENERATION_TEMPERATURE):
        """调用 Ollama /api/generate，format=json 约束输出，返回模型 response 文本。"""
        request_payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }
        response = requests.post(
            OLLAMA_FULL_API_URL,
            json=request_payload,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    @staticmethod
    def _parse_json(text):
        """尽力从模型输出中解析 JSON：先直接解析，失败则做 {..} 区间提取兜底。"""
        if not text:
            raise ValueError("模型返回为空")
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"无法从输出中提取 JSON：{text[:200]}")
        return json.loads(text[start:end + 1])

    # ---------- 结构化校验 ----------
    def _validate_steps(self, data, source_map):
        """校验并规范化 steps：过滤空 action、清理非法/越界 citations 编号。"""
        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError("steps 字段必须是列表")
        max_ref = max(source_map.keys()) if source_map else 0
        valid = []
        for s in raw_steps[:MAX_ADVICE_LINES]:
            if not isinstance(s, dict):
                continue
            action = str(s.get("action", "")).strip()
            if not action:
                continue
            citations = s.get("citations", [])
            if not isinstance(citations, list):
                citations = [citations]
            clean = []
            for c in citations:
                try:
                    ci = int(c)
                except (TypeError, ValueError):
                    continue
                if 1 <= ci <= max_ref:
                    clean.append(ci)
            valid.append({
                "step": len(valid) + 1,
                "action": action,
                "citations": sorted(set(clean)),
            })
        return valid

    @staticmethod
    def _collect_sources(steps, source_map):
        """收集被引用到的知识条目，输出 source_id 溯源列表。"""
        used = set()
        for s in steps:
            used.update(s["citations"])
        return [dict(ref=r, **source_map[r]) for r in sorted(used)]

    # ---------- 忠实度校验（双层） ----------
    @staticmethod
    def _char_grams(text, ns=(1, 2)):
        """去掉空白后提取字符级 n-gram（1,2），用于 lexical grounding。"""
        t = re.sub(r'\s+', '', text)
        if not t:
            return set()
        grams = set()
        for n in ns:
            grams.update(t[i:i + n] for i in range(len(t) - n + 1))
        return grams

    @staticmethod
    def lexical_grounding(action, cited_details):
        """字符级 grounded 分数：action 的 n-gram 被引用条目覆盖的比例 ∈ [0,1]。

        作用：确定性、高精度捕获"编造知识库没有的词"（如凭空出现'截肢'），
        但会把同义改写误判为不忠实——因此需与 LLM-as-judge 语义层互补。
        """
        if not cited_details:
            return 0.0
        joined = "\n".join(cited_details)
        grams = GroundedGenerator._char_grams(action)
        if not grams:
            return 1.0
        covered = sum(1 for g in grams if g in joined)
        return round(covered / len(grams), 3)

    @staticmethod
    def _cited_context(source_map, refs):
        """构造只含被引用条目的紧凑上下文，供 LLM-as-judge 校验，缩小 prompt 降低超时风险。"""
        return "\n".join(f"[{r}]（{source_map[r]['category']}）{source_map[r]['detail']}"
                         for r in sorted(refs) if r in source_map)

    @staticmethod
    def _fuse_faithful(lexical, judge):
        """忠实度决策融合：lexical 为主 gate，judge 仅作灰区语义佐证。

        - lexical >= 0.9：近逐字复制，直接判忠实（不依赖 judge）
        - 0.5 <= lexical < 0.9 且 judge=True：同义改写，语义佐证后判忠实
        - 其余：引用无法支撑（编造/错引/空引用），判不忠实
        """
        if lexical >= LEXICAL_GROUNDED_THRESHOLD:
            return True
        if judge is True and lexical >= LEXICAL_FALLBACK_THRESHOLD:
            return True
        return False

    def check_faithfulness(self, context, steps, source_map, with_judge=True):
        """双层忠实度校验：逐条输出 (lexical_grounding, judge_faithful, reason)。

        with_judge=False 时跳过 LLM-as-judge（grounded 模式 lexical 天然=1.0，无需慢速 judge）。
        """
        if not steps:
            return {"overall_lexical": None, "overall_judge": None, "results": [], "note": "无步骤可校验"}

        # (a) 确定性 lexical grounding，不依赖弱模型的判断质量
        lexical = []
        all_refs = set()
        for s in steps:
            refs = [c for c in s["citations"] if c in source_map]
            all_refs.update(refs)
            details = [source_map[c]["detail"] for c in refs]
            lexical.append(self.lexical_grounding(s["action"], details))

        # (b) LLM-as-judge 语义蕴含（只用被引用条目作上下文，缩小 prompt）
        judge_map = {}
        judge_err = None
        if with_judge:
            try:
                cited_ctx = self._cited_context(source_map, all_refs)
                raw = self._call_ollama(self._build_faithfulness_prompt(cited_ctx, steps),
                                        temperature=FAITHFULNESS_TEMPERATURE)
                data = self._parse_json(raw)
                raw_results = data.get("results", [])
                if isinstance(raw_results, list):
                    for r in raw_results:
                        if not isinstance(r, dict):
                            continue
                        raw_step = str(r.get("step", "")).strip()
                        step = int(raw_step) if raw_step.isdigit() else 0
                        faithful = r.get("faithful")
                        if isinstance(faithful, str):
                            faithful = faithful.strip().lower() in ("true", "是", "yes", "1")
                        judge_map[step] = {
                            "faithful": bool(faithful),
                            "reason": str(r.get("reason", "")).strip(),
                        }
            except Exception as e:
                judge_err = f"LLM-as-judge 失败：{e}"

        results = []
        for i, s in enumerate(steps):
            j = judge_map.get(s["step"])
            judge_faithful = j["faithful"] if j else None
            results.append({
                "step": s["step"],
                "action": s["action"],
                "citations": s["citations"],
                "lexical_grounding": lexical[i],
                "judge_faithful": judge_faithful,
                "judge_reason": j["reason"] if j else (judge_err or "未返回该步判定"),
                "faithful": self._fuse_faithful(lexical[i], judge_faithful),
            })

        overall_lexical = round(sum(lexical) / len(lexical), 3) if lexical else None
        judged = [r["judge_faithful"] for r in results if r["judge_faithful"] is not None]
        overall_judge = round(sum(judged) / len(judged), 3) if judged else None
        fused = [r["faithful"] for r in results]
        overall_faithful = round(sum(fused) / len(fused), 3) if fused else None
        return {
            "overall_lexical": overall_lexical,
            "overall_judge": overall_judge,
            "overall_faithful": overall_faithful,
            "results": results,
        }

    # ---------- 主入口 ----------
    def generate(self, injury_type, visual_evidence=None, mode='llm', with_judge=True):
        """端到端 grounded 生成。

        mode='grounded'：确定性基线（无 LLM，忠实度天然=1.0）
        mode='llm'（默认）：LLM 从候选动作选取/排序/融合并引用，双层忠实度兜底
        with_judge：是否启用 LLM-as-judge 语义校验（grounded 模式可关，避免慢速 judge）
        """
        context, source_map = self.build_context(injury_type)
        if not source_map:
            return {"injury": injury_type, "steps": [], "error": "知识库中无该伤情的处置动作记录"}

        if mode == 'grounded':
            steps = self.grounded_steps(injury_type)
            result = {
                "injury": injury_type,
                "mode": "grounded",
                "steps": steps,
                "sources": self._collect_sources(steps, source_map),
            }
            result["faithfulness"] = self.check_faithfulness(context, steps, source_map, with_judge=with_judge)
            return result

        try:
            prompt = self._build_generation_prompt(injury_type, context, visual_evidence)
            raw = self._call_ollama(prompt, temperature=GENERATION_TEMPERATURE)
            data = self._parse_json(raw)
            steps = self._validate_steps(data, source_map)
        except Exception as e:
            return {
                "injury": injury_type,
                "mode": "llm",
                "steps": [],
                "error": f"结构化生成失败：{e}",
                "traceback": traceback.format_exc(),
            }

        result = {
            "injury": injury_type,
            "mode": "llm",
            "steps": steps,
            "sources": self._collect_sources(steps, source_map),
        }
        result["faithfulness"] = self.check_faithfulness(context, steps, source_map, with_judge=with_judge)
        return result


def _print_result(result):
    if result.get("error"):
        _print(f"❌ {result['error']}")
        return
    _print(f"生成步骤 {len(result['steps'])} 条（mode={result['mode']}）：")
    for s in result["steps"]:
        _print(f"  {s['step']}. {s['action']}  [citations={s['citations']}]")
    _print(f"引用溯源 source_id（{len(result['sources'])} 条）：")
    for src in result["sources"]:
        _print(f"  [{src['ref']}] {src['source_id']}（{src['category']}）{src['detail'][:24]}")
    f = result["faithfulness"]
    _print(f"忠实度：overall_faithful={f.get('overall_faithful')}  (lexical={f.get('overall_lexical')}  judge={f.get('overall_judge')})")
    for r in f.get("results", []):
        _print(f"  step{r['step']}  faithful={r['faithful']}  lexical={r['lexical_grounding']}  judge={r['judge_faithful']}  {r['judge_reason'][:40]}")


def _demo():
    """独立自测：LLM 合成模式 vs grounded 基线对比。"""
    gen = GroundedGenerator()
    cases = ["头皮裂伤", "股动脉损伤", "中度神经性毒剂中毒"]
    for name in cases:
        _print("\n" + "=" * 64)
        _print(f"伤情：{name}  [LLM 合成模式]")
        _print("=" * 64)
        _print_result(gen.generate(name, mode='llm'))

    _print("\n" + "=" * 64)
    _print("对照：grounded 确定性基线（无 LLM，忠实度天然=1.0）")
    _print("=" * 64)
    _print_result(gen.generate("头皮裂伤", mode='grounded'))


if __name__ == "__main__":
    _demo()
