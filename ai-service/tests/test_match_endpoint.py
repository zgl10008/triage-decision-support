# -*- coding: utf-8 -*-
# /match 接口多模态融合端到端验证（Flask test_client）
# 用法：python tests/test_match_endpoint.py
import os
import sys
import types
import warnings

warnings.filterwarnings('ignore')
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def _ensure_stubs():
    """缺依赖时打桩（真实运行环境有 flask_cors/gevent 则自动跳过）。"""
    stubs = [
        ('flask_cors', {'CORS': lambda *a, **k: None}),
        ('gevent', {}),
        ('gevent.pywsgi', {'WSGIServer': object}),
    ]
    for name, attrs in stubs:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = []
            for k, v in attrs.items():
                setattr(mod, k, v)
            sys.modules[name] = mod


_ensure_stubs()
import app as svc  # noqa: E402


def main():
    svc.load_model_and_knowledge()
    # 打桩 LLM 调用，聚焦融合判定与响应组装
    svc.call_deepseek_model = lambda triples, visual_evidence=None: ["1. 测试处置步骤", "2. 测试止血"]
    client = svc.app.test_client()

    def check(name, payload, expect_status, expect_injury=None, expect_source=None, expect_review=None):
        resp = client.post('/match', json=payload)
        data = resp.get_json()
        assert resp.status_code == expect_status, f"{name}: 状态码 {resp.status_code} != {expect_status}，body={data}"
        if expect_injury is not None:
            assert data.get('matched_injury') == expect_injury, f"{name}: 匹配伤情 {data.get('matched_injury')} != {expect_injury}"
        fusion = data.get('fusion')
        if expect_source is not None:
            assert fusion and fusion['source'] == expect_source, f"{name}: source={fusion}"
        if expect_review is not None:
            assert fusion and fusion['needs_review'] is expect_review, f"{name}: needs_review={fusion}"
        print(f"✅ {name}")

    check('纯文本无视觉', {'text': '头皮裂伤'}, 200, '头皮裂伤')
    check('文本+视觉一致', {
        'text': '头皮裂伤',
        'visual': {'injury_candidates': [{'name': '头皮裂伤', 'confidence': 0.92}]},
    }, 200, '头皮裂伤', 'text', False)
    check('文本+视觉冲突', {
        'text': '头皮裂伤',
        'visual': {'injury_candidates': [{'name': '海蛇咬伤', 'confidence': 0.95}]},
    }, 200, '头皮裂伤', 'text', True)
    check('仅视觉高置信度', {
        'visual': {
            'scene': '灾害现场', 'location': '头部', 'severity': '重',
            'visible_symptoms': ['出血'],
            'injury_candidates': [{'name': '海蛇咬伤', 'confidence': 0.9}],
        },
    }, 200, '海蛇咬伤', 'visual', False)
    check('仅视觉低置信度', {
        'visual': {'injury_candidates': [{'name': '海蛇咬伤', 'confidence': 0.4}]},
    }, 404)
    check('无输入', {}, 400)
    print("\n全部通过：6 项")


if __name__ == '__main__':
    main()
