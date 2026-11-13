# -*- coding: utf-8 -*-
"""
VectorStore 抽象 + FAISS 实现
============================================
设计目标：业务层只依赖 VectorStore 抽象，生产切换 Milvus/Qdrant 时不改业务代码。

FAISS 是"库"不是"数据库"：
  - 只存向量，不存文本/元数据 → 这里用 id_to_meta 补充维护，并一起落盘
  - 持久化手动 write_index/read_index → save/load 封装

当前量级（100 类伤情）用 IndexFlatIP（暴力精确，归一化后点积=余弦）足够；
语料上万再切 IndexHNSW，接口不变。
"""
import json

import numpy as np


class VectorStore:
    """向量检索抽象接口。"""

    def add(self, ids, vectors, metas):
        raise NotImplementedError

    def search(self, query_vec, top_k):
        raise NotImplementedError

    def save(self, path):
        raise NotImplementedError

    @classmethod
    def load(cls, path):
        raise NotImplementedError


class FaissStore(VectorStore):
    """基于 FAISS 的实现：IndexFlatIP + id→元数据映射。"""

    def __init__(self, dim):
        import faiss
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)  # 内积；向量需先归一化
        self.ids = []                        # 与 index 行序严格一致
        self.id_to_meta = {}

    def add(self, ids, vectors, metas):
        import faiss
        vectors = np.asarray(vectors, dtype=np.float32)
        faiss.normalize_L2(vectors)  # 归一化后内积 = 余弦相似度
        self.index.add(vectors)
        for i, id_ in enumerate(ids):
            self.id_to_meta[id_] = metas[i]
        self.ids.extend(ids)

    def search(self, query_vec, top_k):
        import faiss
        q = np.asarray([query_vec], dtype=np.float32)
        faiss.normalize_L2(q)
        scores, indices = self.index.search(q, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            id_ = self.ids[idx]
            results.append({
                "id": id_,
                "score": float(score),
                "meta": self.id_to_meta[id_],
            })
        return results

    def save(self, path):
        import faiss
        faiss.write_index(self.index, path + ".index")
        with open(path + ".meta.json", "w", encoding="utf-8") as f:
            json.dump({"ids": self.ids, "meta": self.id_to_meta}, f, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        import faiss
        store = cls.__new__(cls)
        store.index = faiss.read_index(path + ".index")
        store.dim = store.index.d
        data = json.load(open(path + ".meta.json", encoding="utf-8"))
        store.ids = data["ids"]
        store.id_to_meta = data["meta"]
        return store
