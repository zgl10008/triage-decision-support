# -*- coding: utf-8 -*-
"""
阶段2：混合检索器
============================================
链路：query → (可选 HyDE) → BGE-M3 dense 召回 → RRF 融合 → (可选重排) → Top-K

- dense 路：语义相似（解决"口语→术语"鸿沟）
- char-TF-IDF 路：字符级词法重叠（默认启用；对中文短医学文本比分词式 sparse/BM25 更鲁棒）
- sparse(BM25) 路：词级稀疏重叠（默认关闭，保留开关仅作消融对比）
- RRF：无参排名融合，异构分数免归一化
- 重排：bge-reranker-v2-m3 交叉编码器精排（可选，CPU 慢，GPU 快）

与基线(app)接口对齐：retrieve() 返回 [{"injury","score"}, ...]
"""
import json
import os

import numpy as np

from vector_store import FaissStore

# 字符级 TF-IDF 通道的“名称通道”权重（与基线 app 保持一致）
NAME_WEIGHT = 0.3
TFIDF_NGRAM = (1, 2)


def sparse_dot(a, b):
    """稀疏词权重点积：只在交集 token 上累加权重乘积。"""
    s = 0.0
    if len(a) > len(b):
        a, b = b, a
    for tok, w in a.items():
        if tok in b:
            s += w * b[tok]
    return s


def rrf_fuse(ranked_lists, k=60):
    """RRF 无参融合：输入多路'按分数降序的 id 列表'，输出按融合分降序的 id。"""
    score = {}
    for ranked in ranked_lists:
        for rank, id_ in enumerate(ranked):
            score[id_] = score.get(id_, 0.0) + 1.0 / (k + rank + 1)
    return sorted(score, key=score.get, reverse=True), score


class HybridRetriever:
    """BGE-M3 双路 + RRF + 可选重排/HyDE 的检索器。"""

    def __init__(self, embed_model, store, sparse_list, injury_names,
                 reranker=None, hyde_fn=None):
        """
        embed_model : BGEM3FlagModel 实例
        store       : FaissStore（dense 索引）
        sparse_list : list[dict]，与 store.ids 对齐的稀疏词权重
        injury_names: list[str]，与 store.ids 对齐的伤情名
        reranker    : FlagReranker 实例（可选）
        hyde_fn     : callable(query)->str，HyDE 假设文档生成（可选）
        """
        self.embed_model = embed_model
        self.store = store
        self.sparse_list = sparse_list
        self.injury_names = injury_names
        self.reranker = reranker
        self.hyde_fn = hyde_fn
        self._tfidf = None  # 字符级 TF-IDF 通道懒加载缓存

    # ---------- 编码 ----------
    def _embed(self, texts):
        out = self.embed_model.encode(
            list(texts), return_dense=True, return_sparse=True, return_colbert_vecs=False
        )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        dense /= np.linalg.norm(dense, axis=1, keepdims=True)  # 归一化，点积=余弦
        # 稀疏词权重统一成 {int: float}，规避 fp16 无法 json 序列化 & 提升点积精度
        sparse = [{int(k): float(v) for k, v in doc.items()} for doc in out["lexical_weights"]]
        return dense, sparse

    # ---------- 字符级 TF-IDF 通道（保留字面匹配能力） ----------
    def _build_tfidf(self):
        """用 injury_names + 文档文本构建 char(1,2)-gram TF-IDF（名称/描述双通道）。"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        doc_texts = [self.store.id_to_meta[i]["text"] for i in self.injury_names]

        name_vec = TfidfVectorizer(analyzer="char", ngram_range=TFIDF_NGRAM, lowercase=False)
        name_vec.fit(self.injury_names)
        name_mat = name_vec.transform(self.injury_names)

        doc_vec = TfidfVectorizer(analyzer="char", ngram_range=TFIDF_NGRAM, lowercase=False)
        doc_vec.fit(doc_texts)
        doc_mat = doc_vec.transform(doc_texts)

        self._tfidf = (name_vec, name_mat, doc_vec, doc_mat)

    def _tfidf_order(self, query):
        """返回按 char-TF-IDF 双通道分数降序的 id 列表（与基线同口径）。"""
        if self._tfidf is None:
            self._build_tfidf()
        name_vec, name_mat, doc_vec, doc_mat = self._tfidf
        from sklearn.metrics.pairwise import cosine_similarity
        name_scores = cosine_similarity(name_vec.transform([query]), name_mat).flatten()
        doc_scores = cosine_similarity(doc_vec.transform([query]), doc_mat).flatten()
        combined = NAME_WEIGHT * name_scores + (1.0 - NAME_WEIGHT) * doc_scores
        order = sorted(range(len(combined)), key=lambda i: -combined[i])
        return [self.injury_names[i] for i in order]

    # ---------- 多路召回 ----------
    def _recall(self, q_dense, q_sparse, raw_query, recall_n, use_sparse, use_tfidf):
        # dense 路：FAISS 精确点积（归一化后=余弦）
        q_dense_n = q_dense / (np.linalg.norm(q_dense) + 1e-8)
        dense_res = self.store.search(q_dense_n, recall_n)
        dense_order = [r["id"] for r in dense_res]
        # 保留 dense 余弦值：RRF 只负责排序，dense 余弦作下游相似度（[0,1] 可解释）
        dense_score_map = {r["id"]: float(r["score"]) for r in dense_res}

        # sparse 路：BGE-M3 词级稀疏点积（词法重叠，替代原字符级 TF-IDF，即 BM25 语义通道）
        sparse_scores = [sparse_dot(q_sparse, doc) for doc in self.sparse_list]
        sparse_order = [self.injury_names[i] for i in
                        sorted(range(len(sparse_scores)), key=lambda i: -sparse_scores[i])]

        # RRF 融合：语义(dense) + 词级字面(sparse) + 字符级字面(char-TF-IDF)
        # use_sparse/use_tfidf 支持消融（Dense / Dense+Sparse / Dense+TF-IDF / Dense+Sparse+TF-IDF 四组）。
        # 默认 use_sparse=False（BM25 关，见 retrieve 注释），use_tfidf=True。
        ranked_lists = [dense_order]
        if use_sparse:
            ranked_lists.append(sparse_order)
        if use_tfidf:
            ranked_lists.append(self._tfidf_order(raw_query))

        fused_order, fused_score = rrf_fuse(ranked_lists)
        ranked = [
            {
                "injury": id_,
                "score": round(dense_score_map.get(id_, 0.0), 4),  # dense 余弦 = 判定相似度
                "rrf": round(fused_score[id_], 6),                 # RRF 融合分 = 排序依据
            }
            for id_ in fused_order
        ]
        return ranked

    # ---------- 重排 ----------
    def _rerank(self, query, ranked, top_n):
        pairs = [
            [query, self.store.id_to_meta[c["injury"]]["text"]]
            for c in ranked[:top_n]
        ]
        scores = self.reranker.compute_score(pairs, normalize=True)
        for c, s in zip(ranked[:top_n], scores):
            c["score"] = round(float(s), 6)
        return sorted(ranked[:top_n], key=lambda x: -x["score"])

    # ---------- 主入口 ----------
    # 默认两路：dense + char-TF-IDF。sparse(BM25) 通道默认关闭——
    # 消融(Phase3, 150 条)显示 BM25 在中文医学伤情词表上是负贡献
    # （Dense→Dense+BM25：paraphrase Recall@1 0.675→0.600、MRR@3 0.824→0.814），
    # 且与 char-TF-IDF 同为词法通道、被其覆盖；保留 use_sparse 开关仅作消融对比。
    def retrieve(self, query, top_k=3, use_hyde=False, use_rerank=False, recall_n=50,
                 use_tfidf=True, use_sparse=False):
        q_text = query
        if use_hyde and self.hyde_fn:
            q_text = self.hyde_fn(query)

        dense, sparse = self._embed([q_text])
        q_dense, q_sparse = dense[0], sparse[0]

        # 字符级 TF-IDF 通道用原始 query（而非 HyDE 假设文档），保留用户真实用词
        ranked = self._recall(q_dense, q_sparse, query, recall_n, use_sparse, use_tfidf)

        if use_rerank and self.reranker and len(ranked) > 1:
            ranked = self._rerank(query, ranked, top_n=min(recall_n, len(ranked)))

        return ranked[:top_k]

    # ---------- 落盘 ----------
    def save(self, path):
        self.store.save(path)
        with open(path + ".sparse.json", "w", encoding="utf-8") as f:
            json.dump(self.sparse_list, f, ensure_ascii=False)

    @classmethod
    def load(cls, path, embed_model, reranker=None, hyde_fn=None):
        store = FaissStore.load(path)
        sparse_list = json.load(open(path + ".sparse.json", encoding="utf-8"))
        # 稀疏权重 json 的 key 是字符串，转回 int；value 统一 float
        sparse_list = [{int(k): float(v) for k, v in d.items()} for d in sparse_list]
        injury_names = store.ids
        return cls(embed_model, store, sparse_list, injury_names, reranker, hyde_fn)
