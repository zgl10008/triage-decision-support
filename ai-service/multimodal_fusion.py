# -*- coding: utf-8 -*-
# // ==============================================================================
# // 多模态融合模块：视频/图片视觉证据 → RAG 检索与生成融合
# // 功能：
# // 1. 加载创伤知识库伤情名称（与 match 服务同一份 CSV）
# // 2. 实体归一化：VLM 自由文本候选 → 知识库标准伤情名
# // 3. RRF 无参融合：文本 Top-K 与视觉候选排序融合（避免两种分数尺度不一致）
# // 4. 冲突检测：文本 Top1 与视觉 Top1 一致性判定，冲突时标记人工复核
# // 5. 视觉证据 prompt 块构造：注入生成阶段
# // ==============================================================================

import configparser
import json
import os
import re

import pandas as pd
from difflib import SequenceMatcher

# // ------------------------------
# // 配置加载：与 match / analyzer 服务共用 config.ini
# // ------------------------------
config = configparser.ConfigParser()
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(CURRENT_FILE_DIR, 'config.ini')
config.read(CONFIG_FILE_PATH, encoding='utf-8')

VISUAL_HIT_THRESHOLD = config.getfloat('fusion_service', 'visual_hit_threshold', fallback=0.7)
RRF_K = config.getint('fusion_service', 'rrf_k', fallback=60)
NORMALIZE_THRESHOLD = config.getfloat('fusion_service', 'normalize_threshold', fallback=0.6)


# // ------------------------------
# // VLM 结构化输出提示词：约束通义千问 VL 只输出 JSON
# // ------------------------------
VLM_STRUCTURED_PROMPT = (
    "你是现场急救场景的伤情识别专家。请仔细观察提供的图片/视频帧，"
    "输出 JSON（不要输出任何其他文字），格式如下：\n"
    "{\n"
    '  "scene": "救治场景描述，一句话",\n'
    '  "location": "受伤部位，如：头部",\n'
    '  "severity": "轻/中/重",\n'
    '  "visible_symptoms": ["可见症状1", "可见症状2"],\n'
    '  "injury_candidates": [{"name": "最可能的伤情名称", "confidence": 0.9}]\n'
    "}\n"
    "要求：\n"
    "1. injury_candidates 给出 1~3 个最可能的伤情名称，按可能性从高到低排序；\n"
    "2. confidence 是 0~1 之间的数值，表示对该伤情的把握程度；\n"
    "3. 如果画面中没有伤员或伤情信息，scene 填\"无伤情信息\"，injury_candidates 为空数组；\n"
    "4. 只输出 JSON，不要输出任何解释或多余文字；\n"
    "5. 每个字段只出现一次，输出完闭合的 JSON 后立即停止，禁止重复输出任何字段。"
)


# // ------------------------------
# // 1. 加载知识库伤情名称
# // ------------------------------
def load_injury_names(knowledge_file_name=None):
    """读取知识库 CSV 第一列并去重，得到标准伤情名称集合。"""
    if knowledge_file_name is None:
        knowledge_file_name = config.get('match_service', 'knowledge_file_path', fallback='创伤100-合并.csv')
    knowledge_full_path = os.path.join(CURRENT_FILE_DIR, knowledge_file_name)
    if not os.path.exists(knowledge_full_path):
        raise FileNotFoundError(f"创伤知识库文件不存在：{knowledge_full_path}")
    df = pd.read_csv(knowledge_full_path, header=0, encoding='utf-8')
    names = df.iloc[:, 0].map(_clean_kb_text)
    names = names[(names != '') & (~names.map(_is_blank_text))]
    return names.drop_duplicates().tolist()


def _clean_kb_text(value):
    """与 match 服务一致的字段清洗：去 BOM、空白、元组引号残留。"""
    if value is None:
        return ''
    text = str(value).replace('\ufeff', '').strip()
    if text == 'nan':
        return ''
    if text.startswith("('"):
        text = text[2:]
    if text.endswith("')"):
        text = text[:-2]
    return text.strip()


def _is_blank_text(text):
    """判断规范化后的文本是否只剩标点/空壳。"""
    return text.strip("()'，。、, ") == ''


# // ------------------------------
# // 2. VLM 输出解析：兼容 markdown 代码块围栏与多余文本
# // ------------------------------
def extract_json_object(text):
    """从 VLM 返回文本中提取 JSON 对象，失败返回 None。

    兼容三类真实模型输出：
      1. 纯净 JSON / markdown 代码块围栏
      2. 重复 key（qwen-vl 偶发重复输出，json.loads 默认取最后一个）
      3. 未闭合/重复尾部（模型重复到 max_tokens 被截断）——字段级正则兜底，取首次出现值
    """
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ``` 围栏
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    # 1) 直接解析（含重复 key：json.loads 取最后一个，通常仍是合法值）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 2) 截取第一个 { 到最后一个 }
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    # 3) raw_decode 解析首个完整 JSON 值（容忍前导杂文本）
    start = text.find('{')
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    # 4) 字段级正则兜底：按固定 schema 提取每个字段的首次出现值，容忍重复/未闭合
    parsed = _regex_extract_fields(text)
    # 若一个字段都没提取到，说明输入不含任何可用的 JSON 结构 → 按 docstring 约定返回 None
    # （否则 build_visual_evidence 会把垃圾文本误判为 structured=True 的空视觉证据）
    if not any(parsed.values()):
        return None
    return parsed


def _regex_extract_fields(text):
    """字段级正则兜底：对结构化输出的已知字段分别提取首个值。

    不依赖整段 JSON 合法，能扛住「重复 key + 未闭合截断」这类退化输出。
    """
    def _first_str(pattern):
        m = re.search(pattern, text)
        return m.group(1) if m else ''

    def _first_arr(pattern):
        m = re.search(pattern, text, re.DOTALL)
        if not m:
            return []
        return [x for x in re.findall(r'"([^"]*)"', m.group(1))]

    # injury_candidates：取第一个数组（含 name/confidence 对象），忽略后续重复段
    candidates = []
    m = re.search(r'"injury_candidates"\s*:\s*\[(.*?)\]', text, re.DOTALL)
    if m:
        for cm in re.finditer(r'"name"\s*:\s*"([^"]*)"\s*,\s*"confidence"\s*:\s*([0-9.]+)', m.group(1)):
            try:
                candidates.append({'name': cm.group(1), 'confidence': float(cm.group(2))})
            except ValueError:
                pass

    return {
        'scene': _first_str(r'"scene"\s*:\s*"([^"]*)"'),
        'location': _first_str(r'"location"\s*:\s*"([^"]*)"'),
        'severity': _first_str(r'"severity"\s*:\s*"([^"]*)"'),
        'visible_symptoms': _first_arr(r'"visible_symptoms"\s*:\s*\[(.*?)\]'),
        'injury_candidates': candidates,
    }


# // ------------------------------
# // 3. 实体归一化：VLM 候选名 → 知识库标准伤情名
# // ------------------------------
def _similarity(a, b):
    """字符级相似度：包含关系加权 + SequenceMatcher 兜底。"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.9 + 0.1 * (min(len(a), len(b)) / max(len(a), len(b)))
    return SequenceMatcher(None, a, b).ratio()


def normalize_candidates(raw_candidates, injury_names, threshold=None):
    """将 VLM 输出的候选伤情名映射到知识库标准名称。

    参数：
        raw_candidates: list，元素为 str 或 {"name": str, "confidence": float}
        injury_names: 知识库标准伤情名称列表
        threshold: 映射相似度阈值，默认取配置
    返回：
        list[{"name", "confidence", "raw", "ratio"}]，按置信度降序，仅保留映射成功的候选
    """
    if threshold is None:
        threshold = NORMALIZE_THRESHOLD
    injury_set = set(injury_names)
    mapped = {}
    for item in raw_candidates or []:
        if isinstance(item, str):
            raw_name = item.strip()
            conf = 0.9
        else:
            raw_name = str((item or {}).get('name', '')).strip()
            try:
                conf = float((item or {}).get('confidence', 0.9))
            except (TypeError, ValueError):
                conf = 0.9
        if not raw_name:
            continue

        if raw_name in injury_set:
            best_name, best_ratio = raw_name, 1.0
        else:
            best_name, best_ratio = None, 0.0
            for name in injury_names:
                ratio = _similarity(raw_name, name)
                if ratio > best_ratio:
                    best_name, best_ratio = name, ratio
            if best_ratio < threshold:
                continue

        adjusted_conf = round(conf * max(0.5, best_ratio), 3)
        if best_name not in mapped or mapped[best_name]['confidence'] < adjusted_conf:
            mapped[best_name] = {
                'name': best_name,
                'confidence': adjusted_conf,
                'raw': raw_name,
                'ratio': round(best_ratio, 3),
            }
    return sorted(mapped.values(), key=lambda x: x['confidence'], reverse=True)


# // ------------------------------
# // 4. 视觉证据组装：VLM JSON → 供检索融合与生成注入的 evidence
# // ------------------------------
def build_visual_evidence(parsed, injury_names, raw_text=None):
    """将 VLM 解析结果整理为结构化视觉证据。"""
    if not parsed:
        return {
            'scene': '', 'location': '', 'severity': '',
            'visible_symptoms': [], 'injury_candidates': [],
            'raw': raw_text or '', 'structured': False,
        }
    candidates = normalize_candidates(parsed.get('injury_candidates'), injury_names)
    return {
        'scene': str(parsed.get('scene', '')).strip(),
        'location': str(parsed.get('location', '')).strip(),
        'severity': str(parsed.get('severity', '')).strip(),
        'visible_symptoms': [str(s).strip() for s in (parsed.get('visible_symptoms') or []) if str(s).strip()],
        'injury_candidates': candidates,
        'raw': raw_text or '',
        'structured': True,
    }


# // ------------------------------
# // 5. RRF 无参融合：文本 Top-K 与视觉候选排序融合
# // ------------------------------
def fuse_by_rrf(text_candidates, visual_candidates, k=None):
    """Reciprocal Rank Fusion：对两种异构分数列表做无参融合排序。

    text_candidates: [{"injury": str, "score": float}]
    visual_candidates: [{"name": str, "confidence": float}]
    返回: [{"injury", "score", "rank_text", "rank_visual"}] 按融合分降序
    """
    if k is None:
        k = RRF_K
    text_rank = {c['injury']: idx + 1 for idx, c in enumerate(text_candidates or [])}
    vis_rank = {c['name']: idx + 1 for idx, c in enumerate(visual_candidates or [])}
    all_names = set(text_rank) | set(vis_rank)
    fused = []
    for name in all_names:
        score = 0.0
        if name in text_rank:
            score += 1.0 / (k + text_rank[name])
        if name in vis_rank:
            score += 1.0 / (k + vis_rank[name])
        fused.append({
            'injury': name,
            'score': round(score, 5),
            'rank_text': text_rank.get(name),
            'rank_visual': vis_rank.get(name),
        })
    fused.sort(key=lambda x: x['score'], reverse=True)
    return fused


# // ------------------------------
# // 6. 冲突检测：文本 Top1 与视觉 Top1 一致性判定
# // ------------------------------
def conflict_detect(text_candidates, visual_candidates):
    """判定文本检索与视觉识别的结论是否一致。

    返回: {"consistent": bool, "needs_review": bool, "reason": str}
    """
    if not text_candidates or not visual_candidates:
        return {'consistent': False, 'needs_review': False, 'reason': 'single_source'}
    text_top = text_candidates[0]['injury']
    vis_top = visual_candidates[0]['name']
    text_top3 = {c['injury'] for c in text_candidates[:3]}
    vis_top3 = {c['name'] for c in visual_candidates[:3]}
    if text_top == vis_top:
        return {'consistent': True, 'needs_review': False, 'reason': 'same_top1'}
    if vis_top in text_top3 or text_top in vis_top3:
        return {'consistent': True, 'needs_review': False, 'reason': 'in_top3'}
    return {'consistent': False, 'needs_review': True, 'reason': 'conflict'}


# // ------------------------------
# // 7. 视觉证据 prompt 块：注入生成阶段
# // ------------------------------
def build_visual_evidence_block(visual_evidence):
    """把结构化视觉证据转成 prompt 中的“现场观察证据”文本块。"""
    if not visual_evidence:
        return ''
    lines = []
    if visual_evidence.get('scene'):
        lines.append(f"- 救治场景：{visual_evidence['scene']}")
    if visual_evidence.get('location'):
        lines.append(f"- 受伤部位：{visual_evidence['location']}")
    if visual_evidence.get('severity'):
        lines.append(f"- 严重程度：{visual_evidence['severity']}")
    symptoms = visual_evidence.get('visible_symptoms') or []
    if symptoms:
        lines.append("- 可见症状：" + "、".join(symptoms))
    candidates = visual_evidence.get('injury_candidates') or []
    if candidates:
        cand_text = "、".join(f"{c['name']}(置信度{c['confidence']})" for c in candidates)
        lines.append(f"- 视觉初步判断：{cand_text}")
    if not lines:
        return ''
    return "【现场观察证据（视频/图像分析）】\n" + "\n".join(lines)
