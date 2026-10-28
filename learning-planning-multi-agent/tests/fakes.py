# 文件：tests/fakes.py
# 功能：提供不依赖 torch / chromadb 的轻量假集合，用于快速单测检索链路
# 输入：资源字典列表；输出：行为与 Chroma 查询返回结构一致的对象

from __future__ import annotations

import itertools
import re
from typing import Any, Dict, List, Optional

from vector_store_core import VectorStoreManager

_SEQ = itertools.count()
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> List[str]:
    """把文本切成英文单词与中文单字，用于假集合的朴素匹配"""
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def matches(metadata: Dict[str, Any], where: Optional[Dict[str, Any]]) -> bool:
    """输入元数据与 Chroma 风格 where 子句，返回是否命中"""
    if not where:
        return True
    if "$and" in where:
        return all(matches(metadata, clause) for clause in where["$and"])
    for key, expected in where.items():
        value = metadata.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
        elif value != expected:
            return False
    return True


class FakeCollection:
    """内存版集合：query 用词重叠度打分，结构对齐 Chroma 返回格式"""

    def __init__(self, resources: List[Dict[str, Any]]):
        self.resources = {str(r["id"]): dict(r) for r in resources}

    def add(self, ids, documents, metadatas):
        """写入资源，已存在的 id 直接覆盖"""
        for rid, doc, meta in zip(ids, documents, metadatas):
            self.resources[str(rid)] = {"document": doc, "metadata": dict(meta), "id": rid}

    def update(self, ids, metadatas):
        """更新元数据"""
        for rid, meta in zip(ids, metadatas):
            if str(rid) in self.resources:
                self.resources[str(rid)]["metadata"] = dict(meta)

    def get(self, ids=None):
        """返回全部或指定 id 的资源，结构对齐 Chroma"""
        items = list(self.resources.values())
        if ids is not None:
            wanted = {str(i) for i in ids}
            items = [i for i in items if str(i["id"]) in wanted]
        return {
            "ids": [str(i["id"]) for i in items],
            "documents": [i["document"] for i in items],
            "metadatas": [i["metadata"] for i in items],
        }

    def query(self, query_texts, n_results=5, where=None):
        """按词重叠度倒序返回 n_results 条，结构对齐 Chroma"""
        query = tokenize(query_texts[0])
        scored = []
        for item in self.resources.values():
            meta = item["metadata"]
            if not matches(meta, where):
                continue
            doc_tokens = set(tokenize(item["document"]))
            overlap = len(set(query) & doc_tokens)
            score = overlap / (len(set(query)) or 1)
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        scored = scored[:n_results]
        return {
            "ids": [[str(item["id"]) for _, item in scored]],
            "documents": [[item["document"] for _, item in scored]],
            "metadatas": [[item["metadata"] for _, item in scored]],
            # 假集合用 1 - score 充当距离，还原后 similarity 即重叠度
            "distances": [[round(1.0 - score, 6) for score, _ in scored]],
        }

    def count(self) -> int:
        return len(self.resources)


def make_resource(rid: str, title: str, description: str, field: str = "编程",
                  level: str = "beginner", resource_type: str = "视频教程",
                  url: Optional[str] = None) -> Dict[str, Any]:
    """构造一条测试资源元数据"""
    return {
        "id": rid,
        "title": title,
        "description": description,
        "resource_type": resource_type,
        "field": field,
        "level": level,
        "url": url or f"https://example.com/{rid}",
    }


def make_store(resources: List[Dict[str, Any]]) -> VectorStoreManager:
    """
    构造绕过 __init__ 的 VectorStoreManager 实例。

    只注入检索所需的最小状态，避免加载 Embedding 模型，使单测秒级完成。
    """
    collection = FakeCollection([])
    for res in resources:
        collection.add(
            ids=[res["id"]],
            documents=[f"{res['title']}\n{res['description']}"],
            metadatas=[{
                **{k: v for k, v in res.items() if k != "document"},
                "tags": ",".join(res.get("tags", [])),
                "source": res.get("source", "test"),
                "rating": str(res.get("rating", 0.0)),
                "feedback_count": "0",
                "created_at": "2026-10-26T00:00:00+08:00",
            }],
        )

    store = object.__new__(VectorStoreManager)
    store.db_path = "./fake_db"
    store.collection_name = VectorStoreManager.COLLECTION_NAME
    # 每个假实例独立世代号，避免共享的 BM25 缓存串库
    import itertools

    store._store_key = f"fake::{id(store)}::{next(_SEQ)}"
    store.client = None
    store.collection = collection
    store._initialized = True
    store.bm25 = None
    store._bm25_docs = []
    store._bm25_ids = []
    store._bm25_metas = []
    store._bm25_loaded = False
    from collections import OrderedDict

    store._query_cache = OrderedDict()
    store._stats = {
        "dense_calls": 0, "sparse_calls": 0, "hybrid_calls": 0,
        "cache_hits": 0, "cache_misses": 0, "latency_ms_total": 0.0,
    }
    return store
