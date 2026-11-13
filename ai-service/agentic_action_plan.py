# -*- coding: utf-8 -*-
"""
阶段5：Action Planning Agent —— 确定性结构化处置计划
================================================================
把「LLM 自由决定医学动作」降级为「LLM 只表达证据约束出的 ActionPlan」。

核心原则（V5.0 红线）：
    retrieved KB evidence
            ↓
    deterministic ActionPlan（本模块：确定性分类，零 LLM）
            ↓
    LLM verbalization（rag_generator.verbalize，只做措辞）

ActionPlan 是「最终允许 LLM 表达的动作白名单」。它区别于 grounded_steps 的
「全量排序去重」：本模块做 Evidence filtering + risk filtering + action dedup +
citation binding，把 output 键动作按语义分成四类：

- supported_actions         常规处置白名单（LLM 只能从这里表达）
- escalation_conditions     升级处置（含「立即/紧急/加重」等，配合 red_flags 条件触发）
- contraindicated_actions   禁忌/约束（含「禁止/切勿/避免」等，不得作为常规建议）
- red_flags                 危险信号（来自 inference「并发症」非 benign 值，如昏迷/颅内血肿）

LLM 只允许：排序、合并表达、改写自然语言、增加连接词。
LLM 不允许：新增医学动作、删除安全必需动作、改变动作语义、添加 KB 未支持的医学判断。
"""
import json
import os
import hashlib
from dataclasses import dataclass, field, asdict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
KB_RECORDS_PATH = os.path.join(CURRENT_DIR, 'kb', 'kb_records.json')

# // 救治阶段排序：现场急救(现场最急) < 紧急救治 < 早期治疗
STAGE_ORDER = {'现场急救': 0, '紧急救治': 1, '早期治疗': 2}

# // 禁忌/约束词（确定性）：出现在 output 动作里 → 归入 contraindicated，不进白名单
CONTRAINDICATED_WORDS = ('禁止', '切勿', '严禁', '不可', '不宜', '避免')
# // 升级处置词（确定性）：出现在 output 动作里 → 归入 escalation_conditions
ESCALATION_WORDS = ('立即', '紧急', '加重', '恶化', '骤停', '必要时')
# // 并发症里不构成危险信号的值（无并发症 / 其他）
BENIGN_COMPLICATIONS = {'无', '其他'}


@dataclass
class Citation:
    """一条知识条目引用：局部编号 ref 映射回 source_id。"""
    ref: int
    source_id: str
    category: str
    detail: str


@dataclass
class Action:
    """一条处置动作 / 信号，绑定引用编号与语义类别。"""
    action: str
    action_id: str
    citations: list
    kind: str            # supported / escalation / contraindicated / red_flag
    stage: str = ''      # 救治阶段（output 动作有；red_flag 为空）


@dataclass
class ActionPlan:
    """确定性结构化处置计划：LLM verbalization 的唯一输入。"""
    candidate_conditions: list          # 相关知识候选（非诊断，见 candidate_conditions）
    supported_actions: list             # 常规处置白名单
    red_flags: list                     # 危险信号（并发症）
    escalation_conditions: list         # 升级处置
    contraindicated_actions: list       # 禁忌/约束
    citations: list                     # 统一引用表
    severity: str = ''                  # 伤势严重度（来自 inference「伤势」）

    def to_dict(self):
        return {
            'candidate_conditions': self.candidate_conditions,
            'supported_actions': [asdict(a) for a in self.supported_actions],
            'red_flags': [asdict(a) for a in self.red_flags],
            'escalation_conditions': [asdict(a) for a in self.escalation_conditions],
            'contraindicated_actions': [asdict(a) for a in self.contraindicated_actions],
            'citations': [asdict(c) for c in self.citations],
            'severity': self.severity,
        }

    def all_actions(self):
        """按「白名单优先、升级、禁忌」顺序合并，供 verbalize/校验使用。"""
        return self.supported_actions + self.escalation_conditions + self.contraindicated_actions


class ActionPlanningAgent:
    """从 KB 证据确定性提取 ActionPlan。零 LLM，可注入 records 供单测。"""

    def __init__(self, records_path=None):
        self.records_path = records_path or KB_RECORDS_PATH
        self._records = None

    def _load(self):
        if self._records is None:
            with open(self.records_path, encoding='utf-8') as f:
                self._records = json.load(f)
        return self._records

    @staticmethod
    def _classify_output(detail):
        """确定性分类一条 output 动作：contraindicated / escalation / supported。"""
        for w in CONTRAINDICATED_WORDS:
            if w in detail:
                return 'contraindicated'
        for w in ESCALATION_WORDS:
            if w in detail:
                return 'escalation'
        return 'supported'

    @staticmethod
    def _action_id(injury_type, source_id, kind):
        """Stable, opaque ID used as the LLM's only selectable action token."""
        raw = f"{injury_type}|{source_id}|{kind}".encode('utf-8')
        return f"act_{hashlib.sha256(raw).hexdigest()[:12]}"

    def plan(self, injury_type, risk_flags=None):
        """从 injury_type 的 KB 记录提取 ActionPlan。

        risk_flags（可选）：SituationAssessment 的风险标识，暂只作透传参考，
        不影响确定性分类（保持 ActionPlan 与 KB 证据严格同源）。
        """
        records = [r for r in self._load() if r['injury_type'] == injury_type]
        if not records:
            return ActionPlan([injury_type], [], [], [], [], [], '')

        citations = []          # 统一引用表（ref 从 1 开始）
        citation_index = {}     # source_id -> ref（去重）
        supported, red_flags, escalation, contraindicated = [], [], [], []
        severity = ''

        def bind(rec):
            sid = rec['source_id']
            if sid not in citation_index:
                citation_index[sid] = len(citations) + 1
                citations.append(Citation(citation_index[sid], sid, rec['category'], rec['detail']))
            return citation_index[sid]

        # // output 键 → 三类处置动作。
        # // action dedup：同一 detail 文本跨阶段重复（如「常规后送」在现场急救/紧急救治都出现），
        # // 只保留最早阶段（records 已按 KB 原始顺序，现场急救在前），与 grounded_steps 同口径。
        seen_details = set()
        for r in records:
            if r['field_type'] != 'output':
                continue
            if r['detail'] in seen_details:
                continue
            seen_details.add(r['detail'])
            kind = self._classify_output(r['detail'])
            ref = bind(r)
            action = Action(
                r['detail'],
                self._action_id(injury_type, r['source_id'], kind),
                [ref], kind, r['category']
            )
            if kind == 'contraindicated':
                contraindicated.append(action)
            elif kind == 'escalation':
                escalation.append(action)
            else:
                supported.append(action)

        # // inference 键：并发症 → red_flags；伤势 → severity（并发症同样去重）
        red_seen = set()
        for r in records:
            if r['field_type'] != 'inference':
                continue
            if r['category'] == '并发症' and r['detail'] not in BENIGN_COMPLICATIONS:
                if r['detail'] in red_seen:
                    continue
                red_seen.add(r['detail'])
                ref = bind(r)
                red_flags.append(Action(
                    r['detail'],
                    self._action_id(injury_type, r['source_id'], 'red_flag'),
                    [ref], 'red_flag', ''
                ))
            elif r['category'] == '伤势':
                severity = r['detail']

        # // 按救治阶段排序（red_flag 无阶段，保持 KB 顺序）
        supported.sort(key=lambda a: (STAGE_ORDER.get(a.stage, 99), a.action))
        escalation.sort(key=lambda a: (STAGE_ORDER.get(a.stage, 99), a.action))

        return ActionPlan(
            candidate_conditions=[injury_type],
            supported_actions=supported,
            red_flags=red_flags,
            escalation_conditions=escalation,
            contraindicated_actions=contraindicated,
            citations=citations,
            severity=severity,
        )
