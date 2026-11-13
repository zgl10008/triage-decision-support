# -*- coding: utf-8 -*-
# // ============================================================
# // 检索评测脚本
# // 功能：
# // 1. 按当前配置跑完整评测集，输出各分类准确率与失败明细；
# // 2. 对 similarity_threshold × match_margin 做网格调参，
# //    以“总正确数最多、无关输入误接受最少”为选参目标。
# // 用法：python eval/eval_retrieval.py
# // ============================================================
import os
import sys
import json
import warnings

warnings.filterwarnings('ignore')

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(EVAL_DIR, '..'))

# // 评测仅需要检索核心逻辑，不需要启动 Web 服务：
# // 用空壳模块替换 flask / flask_cors / gevent，避免依赖完整运行环境。
import types  # noqa: E402


def _install_web_stubs():
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


_install_web_stubs()
import app as svc  # noqa: E402

CATEGORIES = ['exact', 'paraphrase', 'symptom', 'offtopic']


def load_cases():
    with open(os.path.join(EVAL_DIR, 'eval_queries.json'), encoding='utf-8') as f:
        return json.load(f)


def run_case(case, threshold=None, margin=None):
    if threshold is not None:
        svc.SIMILARITY_THRESHOLD = threshold
    if margin is not None:
        svc.MATCH_MARGIN = margin
    candidates = svc.retrieve_candidates(case['query'], top_k=svc.TOP_K)
    decision = svc.decide_match(candidates)
    predicted = decision.get('injury', '') if decision['matched'] else ''
    expected = case.get('expected', '')
    if expected:
        ok = predicted == expected
        in_top3 = expected in [c['injury'] for c in candidates]
    else:
        ok = not decision['matched']
        in_top3 = None
    return {
        'id': case['id'],
        'category': case['category'],
        'query': case['query'],
        'expected': expected,
        'predicted': predicted,
        'ok': ok,
        'in_top3': in_top3,
        'score': decision.get('score'),
        'reason': decision.get('reason'),
        'top3': [c['injury'] for c in candidates],
    }


def print_report(results, title):
    print(f"\n===== {title} =====")
    total = len(results)
    ok_n = sum(1 for r in results if r['ok'])
    print(f"总正确率：{ok_n}/{total} = {ok_n / total:.1%}")
    for cat in CATEGORIES:
        cat_results = [r for r in results if r['category'] == cat]
        if not cat_results:
            continue
        cat_ok = sum(1 for r in cat_results if r['ok'])
        print(f"  {cat:10s}: {cat_ok}/{len(cat_results)} = {cat_ok / len(cat_results):.1%}")
    failed = [r for r in results if not r['ok']]
    if failed:
        print("\n失败明细：")
        for r in failed:
            exp = r['expected'] if r['expected'] else '(应拒答)'
            print(f"  [{r['id']}] {r['query']}")
            print(f"      期望: {exp} | 实际: {r['predicted'] or '(拒答)'} | score={r['score']} reason={r['reason']}")
            print(f"      top3: {r['top3']}")


def grid_search(cases):
    print("\n===== 网格调参 (threshold × margin × name_weight) =====")
    best = None
    best_metrics = None
    for w in [0.30, 0.40, 0.50, 0.60]:
        svc.NAME_WEIGHT = w
        for t in [0.10, 0.12, 0.15, 0.18, 0.20, 0.25]:
            for m in [0.00, 0.02, 0.03, 0.04, 0.05, 0.08]:
                results = [run_case(c, threshold=t, margin=m) for c in cases]
                ok_n = sum(1 for r in results if r['ok'])
                false_accept = sum(
                    1 for r in results
                    if r['category'] == 'offtopic' and not r['expected'] and not r['ok']
                )
                wrong_accept = sum(
                    1 for r in results
                    if r['category'] != 'offtopic' and r['expected'] and r['predicted'] and not r['ok']
                )
                # 医疗安全优先：总正确数 > 无关误接受 > 答错伤情
                key = (ok_n, -false_accept, -wrong_accept)
                if best is None or key > best:
                    best = key
                    best_metrics = (w, t, m, ok_n, false_accept, wrong_accept, results)
    w, t, m, ok_n, false_accept, wrong_accept, results = best_metrics
    print(f"最优参数：name_weight={w}, threshold={t}, margin={m}")
    print(f"总正确数：{ok_n}/{len(cases)}，无关输入误接受：{false_accept}，答错伤情：{wrong_accept}")
    return w, t, m


def main():
    svc.load_model_and_knowledge()
    cases = load_cases()
    print(f"评测集：{len(cases)} 条，伤情类型数：{len(svc.injury_names)}")

    current = [run_case(c) for c in cases]
    print_report(current, f"当前配置 (threshold={svc.SIMILARITY_THRESHOLD}, margin={svc.MATCH_MARGIN}, name_weight={svc.NAME_WEIGHT}, top_k={svc.TOP_K})")

    best_w, best_t, best_m = grid_search(cases)
    svc.NAME_WEIGHT = best_w
    best_results = [run_case(c, threshold=best_t, margin=best_m) for c in cases]
    print_report(best_results, f"最优参数复验 (name_weight={best_w}, threshold={best_t}, margin={best_m})")

    # 保存一份当前结果供对比
    try:
        with open(os.path.join(EVAL_DIR, 'eval_result_current.json'), 'w', encoding='utf-8') as f:
            json.dump({
                'threshold': svc.SIMILARITY_THRESHOLD,
                'margin': svc.MATCH_MARGIN,
                'name_weight': svc.NAME_WEIGHT,
                'results': current,
            }, f, ensure_ascii=False, indent=2)
        print("\n结果已保存到 eval/eval_result_current.json")
    except Exception as e:
        print(f"\n结果文件保存失败（不影响评测）：{e}")


if __name__ == '__main__':
    main()
