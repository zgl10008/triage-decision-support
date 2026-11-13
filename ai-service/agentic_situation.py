# -*- coding: utf-8 -*-
"""
阶段4：Situation Assessment Agent —— 信息充分性判断
================================================================
职责（不是解析输入，而是判断）：当前现场信息是否足够支持后续检索与处置决策。

设计（遵循「确定性优先」）：
- 快路径：query 长度足够 / 精确命中知识库伤情名 / 含受控词表（伤部/伤类/伤型/伤势）任一术语
  → 直接判 sufficient，零 LLM 调用（低延迟、可预测）。
- 慢路径：仅当 query 过短且无任何受控信号时才调 LLM，让模型列出「最关键缺失信息」，
  且最多列 3 项；LLM 失败 → 静态兜底（受伤部位 / 伤情性质）。
- 风险标识：用确定性关键词表扫出「大出血 / 意识 / 呼吸 / 中毒」等风险 flag，
  不依赖 LLM，供下游 verification / 严重度升级使用。

输出结构（任务书第 5 节）：
  {"status": "sufficient|insufficient", "reason": str,
   "missing_information": [str], "risk_flags": [str], "normalized_query": str}
"""
import json
import os

from agentic_config import call_ollama, parse_llm_json, AGENT_TIMEOUT
from multimodal_fusion import load_injury_names

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
VOCAB_PATH = os.path.join(CURRENT_DIR, 'kb', 'kb_vocab.json')

# // 长度阈值已废弃：文本长度不再作为 sufficient 的直接依据（"好疼啊怎么办" 等长度够但无实质信息）。
# // 仅保留作历史参考，不参与任何判定。
MIN_QUERY_LEN = 6  # noqa: F841 —— 保留作参考，不再用于充分性判定
# // 受控词表字段：伤类/伤型/伤势 任一术语命中视为「有伤情信号」（伤部单独作为部位信号）
SIGNAL_FIELDS = ('伤类', '伤型', '伤势')
# // 补充受伤部位关键词：vocab['伤部'] 来自 CSV 可能不全，补齐常见口语/解剖部位
LOCATION_KEYWORDS = [
    "头皮", "脑袋", "手臂", "前臂", "手部", "手掌", "手指", "皮肤", "眼睛", "眼球",
    "口腔", "牙齿", "膝盖", "肘部", "手腕", "脚踝", "肩部", "大腿", "小腿",
    "足部", "脚趾", "脚掌", "耳部", "鼻子", "肚子", "胸口",
]
# // 伤情性质关键词：既非完整伤情名、又非部位，但足以与部位组合判定「有实质性伤情」
NATURE_KEYWORDS = [
    "出血", "流血", "穿透", "刺伤", "割伤", "裂伤", "撕裂", "断裂", "挫伤",
    "骨折", "烧伤", "烫伤", "灼伤", "淤血", "肿胀", "疼痛", "剧痛",
    "昏迷", "休克", "窒息", "贯穿", "火烧",
]
# // 风险标识（确定性关键词，多字词避免过匹配）
RISK_KEYWORDS = [
    "大出血", "大量出血", "失血", "休克", "昏迷", "意识丧失", "意识模糊",
    "呼吸困难", "窒息", "心跳骤停", "心脏骤停", "中毒", "化学", "辐射",
    "贯穿伤", "多处伤", "开放性", "离断", "危重",
]

# // 条件式安全关键信息：每个维度 = (风险场景词, 安全信息维度)。
# // 只有「命中风险场景 且 用户未提供该维度信息」才追问——不是所有伤情都追问全部字段。
SAFETY_CRITICAL_DIMENSIONS = [
    (("头部", "头颅", "脑", "头皮", "颅"), "意识状态"),
    (("胸", "肺", "窒息", "淹溺", "呛水", "吸入性"), "呼吸状态"),
    (("贯穿", "穿透", "割", "刺", "裂", "撕", "血管"), "出血情况"),
    (("毒剂", "化学", "辐射", "毒气", "芥子气", "光气", "中毒"), "中毒途径与接触量"),
]
# // 用户「已提供」该维度信息的信号词（命中即不追问）
PROVIDED_MARKERS = {
    "意识状态": ["意识", "神志", "昏迷", "清醒", "昏睡"],
    "呼吸状态": ["呼吸", "气促", "喘", "憋气", "发绀", "咳"],
    "出血情况": ["出血", "流血", "失血", "止血", "渗血", "大出血"],
    "中毒途径与接触量": ["吸入", "接触", "误服", "口服", "注射", "皮肤"],
}

_SITUATION_PROMPT = """你是现场急救场景的现场信息评估专家。

【现场伤情描述】{query}

任务：判断该描述是否包含足够信息，用于检索匹配伤情类型并给出处置建议。

判定规则：
- 若已能定位「受伤部位 + 伤情性质」（例如"头部被坠物击中出血"），status=sufficient；
- 若只有单一信息（例如只说"受伤了"、"疼"，或只有部位无伤情/只有伤情无部位，如仅"头部"/仅"出血"），
  status=insufficient，并在 missing_information 列出最关键的缺失项（最多 3 项，如"受伤部位"、"伤情性质"、"出血情况"）。

【输出格式】严格输出 JSON，不要输出任何其他文字：
{{"status":"sufficient|insufficient","reason":"...","missing_information":["..."]}}
"""


class SituationAssessmentAgent:
    """信息充分性判断 Agent：确定性快路径优先，LLM 仅用于短/模糊输入的缺失项识别。"""

    def __init__(self, vocab_path=None, injury_names=None, llm_fn=None):
        self.vocab = self._load_vocab(vocab_path or VOCAB_PATH)
        self.injury_names = set(injury_names) if injury_names is not None else self._load_injury_names()
        self.llm_fn = llm_fn or call_ollama

    @staticmethod
    def _load_vocab(path):
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        return {}

    @staticmethod
    def _load_injury_names():
        try:
            return set(load_injury_names())
        except Exception:
            return set()

    # ---------- 确定性风险标识 ----------
    def _risk_flags(self, query):
        return [kw for kw in RISK_KEYWORDS if kw in query]

    # ---------- 确定性快路径 ----------
    def _is_fast_sufficient(self, q):
        """确定性快路径：只有「明确命中伤情名」或「部位 + 伤情信号」组合才判 sufficient。

        不再使用文本长度作为充分性依据（修复："好疼啊怎么办" 等长度够但无实质信息被误判）。
        - 情况 A：明确命中伤情名称（完整伤情名 / 伤类/伤型/伤势受控词，如"头皮裂伤""烧伤""骨折"）；
        - 情况 B：至少同时具备「受伤部位 + 伤情性质/伤类/伤型/伤势」→ 足以定位伤情；
        - 情况 C：只有单一信息（仅部位 / 仅伤情信号）→ 不判 sufficient，交 LLM 或兜底。
        """
        # 情况 A：明确命中伤情名称
        if q in self.injury_names:
            return True
        if any(q == term for field in SIGNAL_FIELDS for term in self.vocab.get(field, [])):
            return True

        # 情况 B：部位 + 伤情信号 组合
        has_location = any(term in q for term in self.vocab.get('伤部', [])) \
            or any(kw in q for kw in LOCATION_KEYWORDS)
        has_nature = any(term in q for field in SIGNAL_FIELDS
                         for term in self.vocab.get(field, [])) \
            or any(kw in q for kw in NATURE_KEYWORDS)
        return has_location and has_nature

    # ---------- 结构化字段抽取（确定性） ----------
    def _injury_location(self, q):
        """提取受伤部位：优先 vocab 伤部，其次 LOCATION_KEYWORDS（取第一个命中）。"""
        for term in self.vocab.get('伤部', []):
            if term and term in q:
                return term
        for kw in LOCATION_KEYWORDS:
            if kw in q:
                return kw
        return None

    def _injury_mechanism(self, q):
        """提取伤情机制：优先 vocab 伤类/伤型，其次 NATURE_KEYWORDS（取第一个命中）。"""
        for field in SIGNAL_FIELDS:
            for term in self.vocab.get(field, []):
                if term and term in q:
                    return term
        for kw in NATURE_KEYWORDS:
            if kw in q:
                return kw
        return None

    def _safety_critical_missing(self, q):
        """条件式缺失判断：只追问「命中风险场景 且 用户未提供」的安全关键信息。

        不是所有伤情都追问意识/呼吸/出血/中毒，而是根据命中部位/机制判断哪些维度
        真正影响安全处置；用户已提供的维度（PROVIDED_MARKERS 命中）不重复追问。
        """
        missing = []
        for scene_words, dim in SAFETY_CRITICAL_DIMENSIONS:
            if not any(w in q for w in scene_words):
                continue
            if any(m in q for m in PROVIDED_MARKERS.get(dim, [])):
                continue
            missing.append(dim)
        return missing

    # ---------- LLM 慢路径（仅短/模糊输入） ----------
    def _llm_assess(self, query):
        raw = self.llm_fn(_SITUATION_PROMPT.format(query=query), temperature=0.0, timeout=AGENT_TIMEOUT)
        return parse_llm_json(raw)

    # ---------- 主入口 ----------
    def assess(self, query, visual_evidence=None):
        normalized = (query or '').strip()
        risk_flags = self._risk_flags(normalized)
        location = self._injury_location(normalized)
        mechanism = self._injury_mechanism(normalized)
        safety_missing = self._safety_critical_missing(normalized)

        def _build(status, reason, missing, via_llm, retrieval_sufficient):
            return {
                "normalized_query": normalized,
                "risk_flags": risk_flags,
                "injury_location": location,
                "injury_mechanism": mechanism,
                "retrieval_sufficient": retrieval_sufficient,
                "safety_critical_missing": safety_missing,
                # decision_sufficient：检索够 且 安全关键信息无缺失
                "decision_sufficient": retrieval_sufficient and not safety_missing,
                "status": status,
                "reason": reason,
                "missing_information": missing,
                "via_llm": via_llm,
            }

        if not normalized:
            return _build("insufficient", "输入为空", ["伤情描述"], False, False)

        # 快路径：有实质性信号 → 直接 sufficient，零 LLM
        if self._is_fast_sufficient(normalized):
            return _build("sufficient",
                          "信息充分（含实质性描述或受控伤情术语）",
                          [], False, True)

        # 慢路径：短且无信号 → LLM 识别缺失项；失败则静态兜底
        try:
            data = self._llm_assess(normalized)
            status = str(data.get('status', 'insufficient')).strip().lower()
            missing = [str(m).strip() for m in (data.get('missing_information') or []) if str(m).strip()]
            reason = str(data.get('reason', '')).strip() or '信息不足'
            status = status if status in ('sufficient', 'insufficient') else 'insufficient'
            return _build(status, reason, missing[:3], True, status == 'sufficient')
        except Exception:
            return _build("insufficient", "信息过短且缺少受伤部位等关键信息",
                          ["受伤部位", "伤情性质"], False, False)
