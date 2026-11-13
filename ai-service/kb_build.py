# -*- coding: utf-8 -*-
"""
阶段0：急救知识库数据治理脚本
============================================
目标：把原始 CSV（3 列扁平表）治理成"分层标注 + 带 source_id + 受控词表"的结构化知识库。

分层口径（决定检索字段，回应"救援人员会描述哪些字段"）：
  - 召回键 recall     ：救援人员会输入的字段，参与检索索引
                       {临床特点, 伤部, 伤类, 伤型}
  - 输出键 output     ：系统要输出的处置内容，仅作生成上下文，不参与检索打分
                       {现场急救, 紧急救治, 早期治疗}
  - 推断键 inference  ：需要系统推断/用于结构化过滤的字段
                       {伤势, 并发症}

产出（写入 kb/ 目录）：
  - kb_records.json   带 source_id + field_type 的全部有效记录
  - kb_vocab.json     受控词表（伤部/伤类/伤型/伤势）
  - 控制台打印数据质量与分层统计报告

用法：python kb_build.py
"""
import json
import os
from collections import Counter, OrderedDict

import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(CURRENT_DIR, "data", "emergency_injuries.csv")
OUT_DIR = os.path.join(CURRENT_DIR, "kb")

# 字段 -> 分层 映射（未在表中的分类会进入 unknown，便于暴露新字段）
FIELD_TYPE_MAP = {
    "临床特点": "recall",
    "伤部": "recall",
    "伤类": "recall",
    "伤型": "recall",
    "现场急救": "output",
    "紧急救治": "output",
    "早期治疗": "output",
    "伤势": "inference",
    "并发症": "inference",
}

# 受控词表字段（取值离散、可用于结构化过滤/query 抽取）
VOCAB_FIELDS = ["伤部", "伤类", "伤型", "伤势"]


def clean_kb_text(value):
    """字段清洗：去 BOM、空白、空值占位、历史合并残留的元组引号。"""
    if value is None:
        return ""
    text = str(value).replace("﻿", "").strip()
    if text == "nan":
        return ""
    if text.startswith("('"):
        text = text[2:]
    if text.endswith("')"):
        text = text[:-2]
    return text.strip()


def is_blank_text(text):
    """判断清洗后的文本是否只剩标点/空壳（用于丢弃无效行）。"""
    return text.strip("()'，。、, ") == ""


def build_kb():
    raw = pd.read_csv(CSV_PATH, header=0, encoding="utf-8")
    raw.columns = ["injury_type", "category", "detail"]

    # 1) 全字段清洗
    cleaned = pd.DataFrame({
        col: raw[col].map(clean_kb_text) for col in raw.columns
    })

    # 2) 丢弃无效行：伤情名或描述为空/空壳
    before = len(cleaned)
    valid = cleaned[
        (cleaned["injury_type"] != "")
        & (~cleaned["injury_type"].map(is_blank_text))
        & (~cleaned["detail"].map(is_blank_text))
    ].reset_index(drop=True)
    after = len(valid)
    dropped = before - after

    # 3) 分层标注 + source_id
    valid["field_type"] = valid["category"].map(
        lambda c: FIELD_TYPE_MAP.get(c, "unknown")
    )
    valid["source_id"] = ["kb_{:05d}".format(i + 1) for i in range(len(valid))]

    # 4) 受控词表（清洗后去重，过滤空壳）
    vocab = {}
    for field in VOCAB_FIELDS:
        vals = (
            valid.loc[valid["category"] == field, "detail"]
            .map(clean_kb_text)
            .dropna()
        )
        vals = [v for v in vals.unique() if v and not is_blank_text(v)]
        vocab[field] = sorted(vals)

    # 5) 写盘
    os.makedirs(OUT_DIR, exist_ok=True)
    records = valid[
        ["source_id", "injury_type", "category", "field_type", "detail"]
    ].to_dict(orient="records")

    with open(os.path.join(OUT_DIR, "kb_records.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT_DIR, "kb_vocab.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)

    return {
        "raw_rows": before,
        "valid_rows": after,
        "dropped_rows": dropped,
        "injury_types": valid["injury_type"].nunique(),
        "field_type_dist": Counter(valid["field_type"]),
        "category_dist": Counter(valid["category"]),
        "vocab": vocab,
        "unknown_categories": [
            c for c in valid["category"].unique() if c not in FIELD_TYPE_MAP
        ],
    }


def print_report(stats):
    print("=" * 60)
    print("急救知识库数据治理报告（阶段0）")
    print("=" * 60)
    print(f"原始行数：{stats['raw_rows']}")
    print(f"有效行数：{stats['valid_rows']}（丢弃 {stats['dropped_rows']} 行）")
    print(f"去重伤情类型：{stats['injury_types']}")
    print()
    print("分层分布：")
    for ft in ["recall", "output", "inference", "unknown"]:
        print(f"  {ft:10s}: {stats['field_type_dist'].get(ft, 0)} 行")
    print()
    print("受控词表规模：")
    for field, vals in stats["vocab"].items():
        print(f"  {field}: {len(vals)} 种")
    if stats["unknown_categories"]:
        print(f"\n⚠️ 未分层的分类（需补进 FIELD_TYPE_MAP）：{stats['unknown_categories']}")
    print("\n产出文件：kb/kb_records.json, kb/kb_vocab.json")


if __name__ == "__main__":
    stats = build_kb()
    print_report(stats)
