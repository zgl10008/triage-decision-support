# -*- coding: utf-8 -*-
"""
阶段1：扩充评测集
============================================
策略：
  - exact 类别：由知识库全部伤情名自动生成，做到 100 类全覆盖；
  - paraphrase / symptom / offtopic：保留原有人工标注（这些需要领域知识，不自动生成）。

产出：eval/eval_queries_v2.json
用法：python eval/expand_eval_set.py
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
KB_RECORDS = os.path.join(BASE, "..", "kb", "kb_records.json")
OLD = os.path.join(BASE, "eval_queries.json")
NEW = os.path.join(BASE, "eval_queries_v2.json")


def main():
    records = json.load(open(KB_RECORDS, encoding="utf-8"))

    # 按原始顺序去重，得到 100 类伤情名
    injury_types = []
    seen = set()
    for r in records:
        t = r["injury_type"]
        if t not in seen:
            seen.add(t)
            injury_types.append(t)

    exact_cases = [
        {"id": "exact_{:03d}".format(i), "category": "exact", "query": t, "expected": t}
        for i, t in enumerate(injury_types)
    ]

    old = json.load(open(OLD, encoding="utf-8"))
    kept = [c for c in old if c["category"] != "exact"]

    new = exact_cases + kept
    with open(NEW, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=2)

    print("伤情类型数：", len(injury_types))
    print("exact 自动生成：", len(exact_cases))
    print("保留人工标注(para/symptom/offtopic)：", len(kept))
    print("评测集总数：", len(new))
    print("产出：", os.path.relpath(NEW, BASE))


if __name__ == "__main__":
    main()
