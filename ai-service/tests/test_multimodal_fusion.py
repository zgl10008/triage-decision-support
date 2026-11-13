# -*- coding: utf-8 -*-
# 多模态融合模块单元验证
# 用法：python tests/test_multimodal_fusion.py
import os
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import multimodal_fusion as fusion  # noqa: E402


def test_extract_json_object():
    assert fusion.extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert fusion.extract_json_object('前缀 {"a": 1} 后缀') == {"a": 1}
    assert fusion.extract_json_object('{"a": 1, "b": [1, 2]}') == {"a": 1, "b": [1, 2]}
    assert fusion.extract_json_object('not json') is None


def test_normalize_candidates():
    names = ['头皮裂伤', '海蛇咬伤', '凹陷性颅骨骨折', '大面积烧伤']
    mapped = fusion.normalize_candidates([
        {'name': '头皮裂伤', 'confidence': 0.95},
        {'name': '头皮撕裂', 'confidence': 0.8},
        {'name': '完全无关词汇', 'confidence': 0.9},
    ], names, threshold=0.6)
    assert mapped[0]['name'] == '头皮裂伤'
    assert mapped[0]['confidence'] == 0.95
    assert all(c['name'] in names for c in mapped)
    assert len(mapped) == 1  # 无关词被相似度阈值丢弃


def test_fuse_by_rrf():
    text = [
        {'injury': '头皮裂伤', 'score': 0.5},
        {'injury': '脑挫裂伤', 'score': 0.3},
    ]
    vis = [
        {'name': '头皮裂伤', 'confidence': 0.6},
        {'name': '脑挫裂伤', 'confidence': 0.5},
    ]
    fused = fusion.fuse_by_rrf(text, vis)
    assert fused[0]['injury'] == '头皮裂伤'
    assert fused[0]['rank_text'] == 1
    assert fused[0]['rank_visual'] == 1
    assert fused[1]['injury'] == '脑挫裂伤'


def test_conflict_detect():
    text = [{'injury': '头皮裂伤', 'score': 0.5}]
    same = [{'name': '头皮裂伤', 'confidence': 0.9}]
    other = [{'name': '海蛇咬伤', 'confidence': 0.9}]
    assert fusion.conflict_detect(text, same)['consistent'] is True
    assert fusion.conflict_detect(text, other)['needs_review'] is True
    assert fusion.conflict_detect([], other)['reason'] == 'single_source'


def test_visual_evidence_block():
    ev = {
        'scene': '灾害现场', 'location': '头部', 'severity': '重',
        'visible_symptoms': ['出血', '裂口'],
        'injury_candidates': [{'name': '头皮裂伤', 'confidence': 0.9}],
    }
    block = fusion.build_visual_evidence_block(ev)
    assert '现场观察证据' in block
    assert '头皮裂伤' in block and '出血' in block and '头部' in block
    assert fusion.build_visual_evidence_block(None) == ''


def test_build_visual_evidence():
    parsed = {
        'scene': '现场急救现场', 'location': '头部', 'severity': '中',
        'visible_symptoms': ['大量出血'],
        'injury_candidates': [{'name': '头皮裂伤', 'confidence': 0.92}],
    }
    names = ['头皮裂伤', '海蛇咬伤']
    evidence = fusion.build_visual_evidence(parsed, names, raw_text='raw')
    assert evidence['structured'] is True
    assert evidence['injury_candidates'][0]['name'] == '头皮裂伤'
    assert evidence['raw'] == 'raw'
    empty = fusion.build_visual_evidence(None, names, raw_text='raw')
    assert empty['structured'] is False and empty['injury_candidates'] == []


def test_load_injury_names():
    names = fusion.load_injury_names()
    assert len(names) == 100
    assert '头皮裂伤' in names


def test_svc_fusion_paths():
    # //用空壳模块替换 web 依赖，仅测试检索/融合核心逻辑
    import types
    import warnings

    warnings.filterwarnings('ignore')
    for mod_name in ('flask', 'flask_cors', 'gevent', 'gevent.pywsgi'):
        mod = types.ModuleType(mod_name)
        mod.__path__ = []
        sys.modules[mod_name] = mod
    flask_mod = sys.modules['flask']
    flask_mod.Flask = type('FlaskStub', (), {
        '__init__': lambda self, *a, **k: None,
        'route': lambda self, *a, **k: (lambda f: f),
    })
    flask_mod.request = None
    flask_mod.jsonify = lambda *a, **k: None
    sys.modules['flask_cors'].CORS = lambda *a, **k: None
    sys.modules['gevent.pywsgi'].WSGIServer = object

    import app as svc
    svc.load_model_and_knowledge()

    # 1) 文本链路保持原行为
    text_candidates = svc.retrieve_candidates('头皮裂伤')
    assert text_candidates[0]['injury'] == '头皮裂伤'
    text_decision = svc.decide_match(text_candidates)
    assert text_decision['matched'] is True

    # 2) 视觉与文本一致 → source=text，不需要复核
    vis_same = {'injury_candidates': [{'name': '头皮裂伤', 'confidence': 0.92}]}
    fused = svc._fuse_visual(text_candidates, text_decision, vis_same)
    assert fused['decision']['matched'] is True
    assert fused['decision']['source'] == 'text'
    assert fused['fusion']['needs_review'] is False
    assert fused['fusion']['fused_ranking'][0]['injury'] == '头皮裂伤'

    # 3) 视觉与文本冲突 → 仍沿用文本 Top1，但标记人工复核
    vis_conflict = {'injury_candidates': [{'name': '海蛇咬伤', 'confidence': 0.93}]}
    fused = svc._fuse_visual(text_candidates, text_decision, vis_conflict)
    assert fused['decision']['matched'] is True
    assert fused['decision']['injury'] == '头皮裂伤'
    assert fused['fusion']['needs_review'] is True
    assert fused['fusion']['reason'] == 'conflict'

    # 4) 文本拒答 + 视觉高置信度 → 视觉兜底给出结论
    rejected = {'matched': False, 'reason': 'below_threshold', 'score': 0.05}
    vis_strong = {'injury_candidates': [{'name': '海蛇咬伤', 'confidence': 0.88}]}
    fused = svc._fuse_visual([], rejected, vis_strong)
    assert fused['decision']['matched'] is True
    assert fused['decision']['injury'] == '海蛇咬伤'
    assert fused['decision']['source'] == 'visual'
    assert fused['fusion']['source'] == 'visual'

    # 5) 文本拒答 + 视觉低置信度 → 维持拒答，带融合信息
    vis_weak = {'injury_candidates': [{'name': '海蛇咬伤', 'confidence': 0.5}]}
    fused = svc._fuse_visual([], rejected, vis_weak)
    assert fused['decision']['matched'] is False
    assert fused['fusion']['source'] == 'none'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    for t in tests:
        t()
        print(f"✅ {t.__name__}")
    print(f"\n全部通过：{len(tests)} 项")
