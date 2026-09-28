# 文件：vector_store.py
# 功能：兼容原 vector_store_core，并修正领域过滤、字段保留和 RRF 分数语义
# 输入：查询、领域和难度；输出：结构完整且已过滤的学习资源

from __future__ import annotations

from typing import Dict, List, Optional

from vector_store_core import *  # noqa: F401,F403
from vector_store_core import VectorStoreManager, _tokenize_for_bm25


_ORIGINAL_SEARCH = VectorStoreManager.search


def _patched_search(self, query: str, field: Optional[str] = None,
                    level: Optional[str] = None, top_k: int = 5,
                    mode: str = "hybrid",
                    resource_types: Optional[List[str]] = None) -> List[Dict]:
    """输入查询和过滤条件，返回统一应用过滤规则的检索结果"""
    self._request_field, self._request_level = field, level
    self._request_resource_types = resource_types
    try:
        return _ORIGINAL_SEARCH(self, query, field, level, top_k, mode, resource_types)
    finally:
        self.__dict__.pop("_request_field", None)
        self.__dict__.pop("_request_level", None)
        self.__dict__.pop("_request_resource_types", None)


def _patched_sparse_search(self, query: str, top_k: int = 5) -> List[Dict]:
    """输入查询和数量，返回过滤后且元数据完整的 BM25 结果"""
    if self.bm25 is None:
        return []
    field = getattr(self, "_request_field", None)
    level = getattr(self, "_request_level", None)
    resource_types = getattr(self, "_request_resource_types", None)
    scores = self.bm25.get_scores(_tokenize_for_bm25(query))
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    results: List[Dict] = []
    for index, score in ranked:
        if score <= 0:
            continue
        meta = self._bm25_metas[index] if index < len(self._bm25_metas) else {}
        if (field and meta.get("field") != field) or (level and meta.get("level") != level):
            continue
        if resource_types and meta.get("resource_type") not in resource_types:
            continue
        results.append({
            "id": self._bm25_ids[index] if index < len(self._bm25_ids) else "",
            "title": meta.get("title", ""),
            "description": self._bm25_docs[index],
            "resource_type": meta.get("resource_type", ""),
            "field": meta.get("field", ""),
            "level": meta.get("level", ""),
            "url": meta.get("url", ""),
            "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
            "source": "bm25",
            "rating": float(meta.get("rating", 0)),
            "similarity": float(score),
            "bm25_score": float(score),
            "rank": len(results) + 1,
        })
        if len(results) >= top_k:
            break
    return results


def _patched_rrf_merge(self, dense_results: List[Dict],
                       sparse_results: List[Dict], top_k: int = 5) -> List[Dict]:
    """输入两路结果，返回保留原字段并单独记录 rrf_score 的融合结果"""
    sparse_map = {item["id"]: item for item in sparse_results}
    dense_ids = {item["id"] for item in dense_results}
    merged: List[Dict] = []
    for position, dense in enumerate(dense_results, start=1):
        sparse = sparse_map.get(dense["id"], {})
        sparse_score = float(sparse.get("bm25_score", 0))
        boost = 0.1 if sparse_score > 0.3 else 0.05 if sparse_score > 0.1 else 0.0
        similarity = float(dense.get("similarity", 0))
        merged.append({
            **dense,
            "similarity": round(similarity, 5),
            "rrf_score": round(similarity + boost + 1.0 / (self.RRF_K + position), 5),
        })
    for sparse in sparse_results:
        if sparse["id"] in dense_ids or sparse.get("bm25_score", 0) <= 0.5:
            continue
        merged.append({
            **sparse,
            "similarity": round(sparse["bm25_score"] * 0.3, 5),
            "rrf_score": round(1.0 / (self.RRF_K + len(merged) + 1), 5),
        })
    merged.sort(key=lambda item: item.get("rrf_score", 0), reverse=True)
    return merged[:top_k]


VectorStoreManager.search = _patched_search
VectorStoreManager._sparse_search = _patched_sparse_search
VectorStoreManager._rrf_merge = _patched_rrf_merge
