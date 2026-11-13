# -*- coding: utf-8 -*-
"""
阶段2：离线建库脚本
============================================
从 kb/kb_records.json 读取清洗后的知识，只取"召回键"字段（临床特点/伤部/伤类/伤型），
按伤情类型聚合成检索文档，用 BGE-M3 生成 dense+sparse 向量，构建并落盘 FAISS 索引。

用法：python build_index.py
产出：kb/index/recall.{index, meta.json, sparse.json}

模型下载：首次运行会从 HuggingFace 下载 BAAI/bge-m3（约 2.2GB）。
国内网络慢时，取消下面 HF_ENDPOINT 那行的注释走镜像。
"""
import json
import os
from collections import defaultdict

# 国内镜像：HuggingFace 直连常被墙，走 hf-mirror.com 中转。
# 若你的网络能直连 HF，注释掉这行即可。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from FlagEmbedding import BGEM3FlagModel  # noqa: E402

from vector_store import FaissStore  # noqa: E402

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDS_PATH = os.path.join(CURRENT_DIR, "kb", "kb_records.json")
INDEX_PATH = os.path.join(CURRENT_DIR, "kb", "index", "recall")
LOCAL_MODEL_PATH = os.path.join(CURRENT_DIR, "models", "bge-m3")


def resolve_model_path():
    """本地已下载 bge-m3 则用本地路径（离线可用），否则用 HF id 在线加载。"""
    if os.path.exists(os.path.join(LOCAL_MODEL_PATH, "config.json")):
        return LOCAL_MODEL_PATH
    return "BAAI/bge-m3"

# 召回键：救援人员会描述的字段（输出键/推断键不参与检索，避免稀释信号）
RECALL_KEYS = {"临床特点", "伤部", "伤类", "伤型"}


def aggregate_recall_docs():
    """按伤情类型聚合召回键字段，得到 (injury_names, docs)。"""
    records = json.load(open(RECORDS_PATH, encoding="utf-8"))
    by_injury = defaultdict(list)
    for r in records:
        if r["field_type"] == "recall":
            by_injury[r["injury_type"]].append(r["detail"])

    injury_names = sorted(by_injury.keys())  # 排序保证索引顺序稳定
    docs = [name + " " + " ".join(by_injury[name]) for name in injury_names]
    return injury_names, docs


def build():
    injury_names, docs = aggregate_recall_docs()
    print("召回键聚合文档数：{}（伤情类型 {}）".format(len(docs), len(injury_names)))

    # 4060 GPU：use_fp16=True；纯 CPU 或无 CUDA 时改成 use_fp16=False
    model = BGEM3FlagModel(resolve_model_path(), use_fp16=True)
    out = model.encode(
        docs,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
        batch_size=16,
    )
    dense = out["dense_vecs"]
    sparse = out["lexical_weights"]

    # 建索引：dense 存 FAISS，sparse 单独存（与 store.ids 对齐）
    store = FaissStore(dense.shape[1])
    store.add(injury_names, dense, [{"text": t} for t in docs])

    # sparse 权重可能是 numpy float16，转成 Python float 才能 json 序列化
    sparse = [{int(k): float(v) for k, v in doc.items()} for doc in sparse]

    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    store.save(INDEX_PATH)  # 写 .index + .meta.json
    with open(INDEX_PATH + ".sparse.json", "w", encoding="utf-8") as f:
        json.dump(sparse, f, ensure_ascii=False)

    print("索引已保存到：{}".format(INDEX_PATH))
    print("向量维度：{}，文档数：{}".format(dense.shape[1], len(injury_names)))


if __name__ == "__main__":
    build()
