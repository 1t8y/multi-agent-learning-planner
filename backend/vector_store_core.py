# -*- coding: utf-8 -*-
"""
Chroma 向量数据库管理模块
负责学习资源的存储、检索和管理

核心功能：
- 初始化向量数据库（Embedding 模型与 Chroma 客户端进程内共享）
- 添加学习资源到知识库
- Dense / Sparse / Hybrid 三种检索，Hybrid 使用标准 RRF 融合
- 元数据过滤在 dense 与 sparse 两条链路上同时生效
- 检索结果 LRU 缓存，写操作自动失效
- 支持用户反馈资源入库
"""

import os
import json
import uuid
import threading
import time
from collections import OrderedDict
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# ── 绕过 Windows SSL 证书问题 + 使用国内 HuggingFace 镜像 ──
os.environ.setdefault('HF_HUB_DISABLE_SSL_VERIFY', '1')
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('CURL_CA_BUNDLE', '')
os.environ.setdefault('REQUESTS_CA_BUNDLE', '')
try:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
    try:
        from chromadb.api.types import EmbeddingFunction as _EmbeddingFunctionBase
    except ImportError:  # 老版本 chromadb 没有该导出
        _EmbeddingFunctionBase = object
except ImportError:
    CHROMA_AVAILABLE = False
    _EmbeddingFunctionBase = object
    print("[vector_store] 警告: chromadb 未安装，向量数据库功能不可用")

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[vector_store] 警告: rank_bm25 未安装，稀疏检索功能不可用")

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("[vector_store] 警告: jieba 未安装，稀疏检索使用字符级分词（效果较差）")


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# 进程内共享缓存：避免每个 VectorStoreManager 实例重复加载模型和重复打开数据库
_CACHE_LOCK = threading.RLock()
_EMBEDDING_CACHE: Dict[str, Any] = {}
_CLIENT_CACHE: Dict[str, Any] = {}
_BM25_CACHE: Dict[Tuple[str, str, int], Tuple[Any, List[str], List[str], List[Dict]]] = {}
_GENERATION: Dict[str, int] = {}
_LOAD_STATS: Dict[str, int] = {"embedding_loads": 0, "client_opens": 0, "bm25_builds": 0}


def _bump_generation(store_key: str) -> None:
    """输入库标识，写入世代号使所有派生缓存（BM25、查询结果）失效"""
    _GENERATION[store_key] = _GENERATION.get(store_key, 0) + 1


def _generation(store_key: str) -> int:
    """输入库标识，返回当前世代号"""
    return _GENERATION.get(store_key, 0)


def _tokenize_for_bm25(text: str) -> List[str]:
    """BM25 分词函数：优先使用 jieba 中文分词，回退到字符级分词"""
    if not text:
        return []
    text = text.replace("\n", " ")
    if JIEBA_AVAILABLE:
        return [w for w in jieba.lcut(text) if w.strip()]
    return list(text)


class BGEEmbeddingFunction(_EmbeddingFunctionBase):
    """
    Chroma 兼容的中文 BGE Embedding 包装，底层模型进程内只加载一次。

    同时提供 __call__ / embed_documents / embed_query 三种入口：
    chromadb 不同版本分别走这三条路径，缺一个就会出现“检索静默失败”。
    """

    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = _get_embedding_model(model_name)

    def __call__(self, input):
        return self._model.encode(list(input), show_progress_bar=False).tolist()

    def embed_documents(self, input):
        """写入路径使用的批量编码接口"""
        return self.__call__(input)

    def embed_query(self, input):
        """查询路径使用的编码接口"""
        return self.__call__(input)

    def name(self) -> str:
        """返回稳定名称，供 Chroma 校验集合与 Embedding 的一致性"""
        return "bge-small-zh-v1.5"


def _get_embedding_model(model_name: str):
    """输入模型名，返回共享的 SentenceTransformer 实例（首次调用才加载）"""
    with _CACHE_LOCK:
        if model_name in _EMBEDDING_CACHE:
            return _EMBEDDING_CACHE[model_name]
        from model_loader import get_sentence_transformer

        model = get_sentence_transformer(model_name)
        _EMBEDDING_CACHE[model_name] = model
        _LOAD_STATS["embedding_loads"] += 1
        print(f"[vector_store] Embedding 模型已加载（进程内共享）: {model_name}")
        return model


def _get_chroma_client(db_path: str):
    """输入数据库路径，返回共享的 PersistentClient（同路径只打开一次）"""
    key = os.path.abspath(db_path)
    with _CACHE_LOCK:
        if key in _CLIENT_CACHE:
            return _CLIENT_CACHE[key]
        os.makedirs(key, exist_ok=True)
        client = chromadb.PersistentClient(
            path=key,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        _CLIENT_CACHE[key] = client
        _LOAD_STATS["client_opens"] += 1
        return client


def get_cache_stats() -> Dict[str, Any]:
    """返回模型加载与缓存统计，供健康检查和基准脚本使用"""
    with _CACHE_LOCK:
        return {
            "embedding_models": list(_EMBEDDING_CACHE.keys()),
            "chroma_clients": list(_CLIENT_CACHE.keys()),
            "bm25_indexes": len(_BM25_CACHE),
            **dict(_LOAD_STATS),
        }


@dataclass
class LearningResource:
    """学习资源数据结构"""
    id: str
    title: str
    description: str
    resource_type: str
    field: str
    level: str
    url: str
    tags: List[str]
    source: str
    rating: float
    feedback_count: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "resource_type": self.resource_type,
            "field": self.field,
            "level": self.level,
            "url": self.url,
            "tags": ",".join(self.tags),
            "source": self.source,
            "rating": str(self.rating),
            "feedback_count": str(self.feedback_count),
            "created_at": self.created_at
        }


class VectorStoreManager:
    """
    Chroma 向量数据库管理器

    负责学习资源的持久化存储和相似度检索。
    同一进程内的多个实例共享 Embedding 模型、Chroma 客户端和 BM25 索引。
    """

    COLLECTION_NAME = "learning_resources"
    DEFAULT_DB_PATH = "./chroma_db"
    RRF_K = 60                  # RRF 平滑常数，业界常用 60
    RRF_DENSE_WEIGHT = 1.0      # RRF 中 dense 通路权重
    RRF_SPARSE_WEIGHT = 1.0     # RRF 中 sparse 通路权重
    QUERY_CACHE_SIZE = 256      # 单实例检索结果 LRU 容量

    def __init__(self, db_path: Optional[str] = None,
                 collection_name: Optional[str] = None):
        """
        初始化向量数据库管理器

        Args:
            db_path: 数据库存储路径
            collection_name: 集合名，默认 learning_resources
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.collection_name = collection_name or self.COLLECTION_NAME
        self._store_key = f"{os.path.abspath(self.db_path)}::{self.collection_name}"
        self.client = None
        self.collection = None
        self._initialized = False

        # ---- BM25 稀疏检索相关 ----
        self.bm25 = None
        self._bm25_docs: List[str] = []
        self._bm25_ids: List[str] = []
        self._bm25_metas: List[Dict] = []
        self._bm25_loaded = False

        # ---- 检索缓存与统计 ----
        self._query_cache: "OrderedDict[Tuple, List[Dict]]" = OrderedDict()
        self._stats = {
            "dense_calls": 0, "sparse_calls": 0, "hybrid_calls": 0,
            "cache_hits": 0, "cache_misses": 0, "latency_ms_total": 0.0,
        }

        if not CHROMA_AVAILABLE:
            print("[vector_store] ChromaDB不可用，请运行: pip install chromadb")
            return

        try:
            self._init_client()
            self._init_collection()
            self._initialized = True
        except Exception as e:
            print(f"[vector_store] 初始化失败: {e}")

    # ------------------------------------------------------------------
    # 兼容属性：外部脚本通过 `store._bm25_stale = True` 标记索引失效，
    # 这里接手后同时失效共享 BM25 缓存与本地查询缓存。
    # ------------------------------------------------------------------
    @property
    def _bm25_stale(self) -> bool:
        """BM25 索引是否与库内容不同步"""
        return not self._bm25_loaded

    @_bm25_stale.setter
    def _bm25_stale(self, value: bool) -> None:
        """外部置 True 时，标记本地索引失效并清空共享缓存与查询缓存"""
        self._bm25_loaded = not value
        if value:
            self.bm25 = None
            self._bm25_docs, self._bm25_ids, self._bm25_metas = [], [], []
            with _CACHE_LOCK:
                _bump_generation(self._store_key)
                for key in [k for k in _BM25_CACHE if k[:2] == (self._store_key, "v1")]:
                    _BM25_CACHE.pop(key, None)
        self._query_cache.clear()

    def _init_client(self):
        """初始化 Chroma 客户端（进程内按路径共享）"""
        self.client = _get_chroma_client(self.db_path)
        print(f"[vector_store] 向量数据库初始化完成，路径: {self.db_path}")

    def _init_collection(self):
        """初始化或获取资源集合（使用中文 Embedding 模型）"""
        try:
            emb_fn = self._create_embedding_function()
            if emb_fn is None:
                self.collection = self.client.get_or_create_collection(name=self.collection_name)
            else:
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=emb_fn,
                    metadata={"description": "学习资源知识库"},
                )
            print(f"[vector_store] Embedding: {getattr(emb_fn, '_model_name', 'default')}")
        except Exception as e:
            print(f"[vector_store] 创建集合失败: {e}")
            raise

    def _create_embedding_function(self):
        """创建 Embedding 函数，优先使用中文 BGE 模型（镜像下载）"""
        try:
            emb_fn = BGEEmbeddingFunction(DEFAULT_EMBEDDING_MODEL)
            print(f"[vector_store] Embedding: {DEFAULT_EMBEDDING_MODEL} (中文)")
            return emb_fn
        except Exception as e:
            print(f"[vector_store] BGE 加载失败: {e}")

        # 方案2: ONNX 版本（无需 PyTorch）
        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            print("[vector_store] Embedding: ONNX (英文)")
            return ONNXMiniLM_L6_V2()
        except Exception:
            pass

        # 方案3: Chroma 默认
        print("[vector_store] Embedding: Chroma 默认")
        return None

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def add_resource(self,
                     title: str,
                     description: str,
                     resource_type: str,
                     field: str,
                     level: str,
                     url: str,
                     tags: List[str],
                     source: str = "user") -> Optional[str]:
        """
        添加学习资源到知识库

        Args:
            title: 资源标题
            description: 资源描述
            resource_type: 资源类型（视频教程/文字教程/实战项目/文档资料）
            field: 领域（AI/数学/编程/其他）
            level: 难度等级（beginner/intermediate/advanced）
            url: 资源链接
            tags: 标签列表
            source: 来源（user/system/web_search）

        Returns:
            资源ID，添加失败返回None
        """
        if not self._initialized:
            print("[vector_store] 数据库未初始化")
            return None

        resource_id = str(uuid.uuid4())
        resource = LearningResource(
            id=resource_id,
            title=title,
            description=description,
            resource_type=resource_type,
            field=field,
            level=level,
            url=url,
            tags=tags,
            source=source,
            rating=0.0,
            feedback_count=0,
            created_at=datetime.now().isoformat()
        )

        try:
            self.collection.add(
                ids=[resource_id],
                documents=[f"{title}\n{description}"],
                metadatas=[resource.to_metadata()]
            )
            print(f"[vector_store] 资源已添加: {title} (ID: {resource_id})")
            self._invalidate()
            return resource_id
        except Exception as e:
            print(f"[vector_store] 添加资源失败: {e}")
            return None

    def add_resources_batch(self, resources: List[Dict]) -> List[str]:
        """批量添加资源：一次编码写入，避免逐条调用 embedding"""
        if not self._initialized or not resources:
            return []
        ids, documents, metadatas = [], [], []
        for res in resources:
            resource = LearningResource(
                id=str(res.get("id") or uuid.uuid4()),
                title=res.get("title", ""),
                description=res.get("description", ""),
                resource_type=res.get("resource_type", "文档资料"),
                field=res.get("field", "其他"),
                level=res.get("level", "intermediate"),
                url=res.get("url", ""),
                tags=[str(t) for t in res.get("tags", [])],
                source=res.get("source", "system"),
                rating=float(res.get("rating", 0.0)),
                feedback_count=int(res.get("feedback_count", 0)),
                created_at=str(res.get("created_at", "")),
            )
            ids.append(resource.id)
            documents.append(f"{resource.title}\n{resource.description}")
            metadatas.append(resource.to_metadata())
        try:
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
            self._invalidate()
            return ids
        except Exception as e:
            print(f"[vector_store] 批量添加失败: {e}")
            return []

    def _invalidate(self) -> None:
        """写操作后失效 BM25 索引与查询缓存"""
        with _CACHE_LOCK:
            _bump_generation(self._store_key)
            for key in [k for k in _BM25_CACHE if k[:2] == (self._store_key, "v1")]:
                _BM25_CACHE.pop(key, None)
        self._bm25_loaded = False
        self.bm25 = None
        self._query_cache.clear()

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def search(self,
               query: str,
               field: Optional[str] = None,
               level: Optional[str] = None,
               top_k: int = 5,
               mode: str = "hybrid",
               resource_types: Optional[List[str]] = None,
               candidate_k: Optional[int] = None,
               min_types: int = 0) -> List[Dict]:
        """
        增强搜索：dense | sparse | hybrid

        Args:
            query: 查询文本
            field: 可选领域过滤
            level: 可选难度过滤
            top_k: 返回结果数量
            mode: 检索模式 (dense / sparse / hybrid)
            resource_types: 可选资源类型过滤
            candidate_k: 每路召回数量，默认等于 top_k
            min_types: 结果中最少覆盖的资源类型数，0 表示不做多样性约束

        Returns:
            匹配的资源列表。字段含义：
            - similarity: dense 余弦相似度（仅 sparse 命中时为该批次归一化 BM25）
            - bm25_score: 原始 BM25 分数
            - fused_score: RRF 融合分数（hybrid 模式用于排序）
            - rank_dense / rank_sparse: 两条通路各自的原始排名
        """
        if not self._initialized or not query:
            return []

        pool = max(int(candidate_k or top_k), top_k)
        cache_key = (query, field, level, int(top_k), mode,
                     tuple(sorted(resource_types or ())), pool, int(min_types))
        cached = self._query_cache.get(cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            self._query_cache.move_to_end(cache_key)
            return [dict(item) for item in cached]
        self._stats["cache_misses"] += 1

        started = time.perf_counter()
        dense_results: List[Dict] = []
        if mode in ("dense", "hybrid"):
            dense_results = self._dense_search(query, field, level, resource_types, pool)
            self._stats["dense_calls"] += 1

        sparse_results: List[Dict] = []
        if mode in ("sparse", "hybrid"):
            sparse_results = self._sparse_search(query, pool, field, level, resource_types)
            self._stats["sparse_calls"] += 1

        if mode == "hybrid":
            self._stats["hybrid_calls"] += 1
            results = self._rrf_merge(dense_results, sparse_results, pool)
        elif mode == "sparse":
            results = self._normalize_sparse(sparse_results)
        else:
            results = dense_results

        results = self._dedupe(results)[:pool]
        if min_types > 0:
            results = self._diversify(results, min_types)
        results = results[:top_k]

        self._stats["latency_ms_total"] += (time.perf_counter() - started) * 1000
        self._query_cache[cache_key] = [dict(item) for item in results]
        while len(self._query_cache) > self.QUERY_CACHE_SIZE:
            self._query_cache.popitem(last=False)
        return results

    def _build_where(self, field: Optional[str], level: Optional[str],
                     resource_types: Optional[List[str]]) -> Dict[str, Any]:
        """输入过滤条件，返回 Chroma 的 where 子句"""
        conditions = []
        if field:
            conditions.append({"field": field})
        if level:
            conditions.append({"level": level})
        if resource_types:
            conditions.append({"resource_type": {"$in": list(resource_types)}})
        if not conditions:
            return {}
        return {"$and": conditions} if len(conditions) > 1 else conditions[0]

    def _dense_search(self, query: str, field: Optional[str], level: Optional[str],
                      resource_types: Optional[List[str]], top_k: int) -> List[Dict]:
        """Dense 向量召回，带元数据过滤"""
        where_filter = self._build_where(field, level, resource_types)
        try:
            if where_filter:
                raw = self.collection.query(query_texts=[query], n_results=top_k,
                                            where=where_filter)
            else:
                raw = self.collection.query(query_texts=[query], n_results=top_k)
            return self._format_search_results(raw)
        except Exception as e:
            print(f"[vector_store] 稠密检索失败: {e}")
            return []

    def _format_search_results(self, results: Dict) -> List[Dict]:
        """格式化搜索结果，description 只保留正文不重复标题"""
        formatted = []

        if not results or "documents" not in results or not results["documents"]:
            return formatted

        documents = results["documents"][0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []
        ids = (results.get("ids") or [[]])[0] or []

        for i, document in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            title = metadata.get("title", "")
            formatted.append({
                "id": ids[i] if i < len(ids) else "",
                "title": title,
                "description": self._strip_title(document, title),
                "resource_type": metadata.get("resource_type", ""),
                "field": metadata.get("field", ""),
                "level": metadata.get("level", ""),
                "url": metadata.get("url", ""),
                "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                "source": metadata.get("source", ""),
                "rating": float(metadata.get("rating", 0)),
                "feedback_count": int(metadata.get("feedback_count", 0)),
                "similarity": 1 - distances[i] if i < len(distances) else 0.0
            })

        return formatted

    @staticmethod
    def _strip_title(document: str, title: str) -> str:
        """输入入库文档，返回去掉标题前缀的纯描述"""
        if not document:
            return ""
        if title and document.startswith(title + "\n"):
            return document[len(title) + 1:]
        return document

    def _rebuild_bm25_index(self):
        """从 Chroma 集合重建 BM25 索引，索引在多实例间共享"""
        if not BM25_AVAILABLE:
            return
        cache_key = (self._store_key, "v1", _generation(self._store_key))
        with _CACHE_LOCK:
            hit = _BM25_CACHE.get(cache_key)
        if hit is not None:
            self.bm25, self._bm25_docs, self._bm25_ids, self._bm25_metas = hit
            self._bm25_loaded = True
            return
        try:
            all_data = self.collection.get()
            if not all_data or not all_data["documents"]:
                self._bm25_loaded = True
                return
            tokenized = [_tokenize_for_bm25(doc) for doc in all_data["documents"]]
            bm25 = BM25Okapi(tokenized)
            payload = (bm25, list(all_data["documents"]), list(all_data["ids"] or []),
                       list(all_data["metadatas"] or []))
            with _CACHE_LOCK:
                _BM25_CACHE[cache_key] = payload
                _LOAD_STATS["bm25_builds"] += 1
            self.bm25, self._bm25_docs, self._bm25_ids, self._bm25_metas = payload
            self._bm25_loaded = True
            tokenizer_info = "jieba中文分词" if JIEBA_AVAILABLE else "字符级分词"
            print(f"[vector_store] BM25索引已重建（{len(self._bm25_ids)}个文档, {tokenizer_info}）")
        except Exception as e:
            print(f"[vector_store] BM25索引重建失败: {e}")

    def _sparse_search(self, query: str, top_k: int = 5,
                       field: Optional[str] = None,
                       level: Optional[str] = None,
                       resource_types: Optional[List[str]] = None) -> List[Dict]:
        """BM25 关键词稀疏检索，元数据过滤与 dense 通路保持一致"""
        if not BM25_AVAILABLE:
            return []
        if not self._bm25_loaded:
            self._rebuild_bm25_index()
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(_tokenize_for_bm25(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            meta = self._bm25_metas[idx] if idx < len(self._bm25_metas) else {}
            if field and meta.get("field") != field:
                continue
            if level and meta.get("level") != level:
                continue
            if resource_types and meta.get("resource_type") not in resource_types:
                continue
            document = self._bm25_docs[idx] if idx < len(self._bm25_docs) else ""
            title = meta.get("title", "")
            results.append({
                "id": self._bm25_ids[idx] if idx < len(self._bm25_ids) else "",
                "title": title,
                "description": self._strip_title(document, title),
                "resource_type": meta.get("resource_type", ""),
                "field": meta.get("field", ""),
                "level": meta.get("level", ""),
                "url": meta.get("url", ""),
                "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
                "source": "bm25",
                "rating": float(meta.get("rating", 0) or 0),
                "similarity": float(score),
                "bm25_score": float(score),
            })
            if len(results) >= top_k:
                break
        return results

    def _normalize_sparse(self, sparse_results: List[Dict]) -> List[Dict]:
        """把 BM25 分数按批次最大值缩放到 0 到 1，保持下游相似度语义一致"""
        if not sparse_results:
            return []
        top = max(item.get("bm25_score", 0.0) for item in sparse_results) or 1.0
        return [{**item, "similarity": round(item.get("bm25_score", 0.0) / top, 5)}
                for item in sparse_results]

    def _rrf_merge(self, dense_results: List[Dict], sparse_results: List[Dict],
                   top_k: int = 5) -> List[Dict]:
        """
        标准 Reciprocal Rank Fusion：score = Σ w_i / (k + rank_i)

        只使用名次，不使用原始分数，因此不需要对 dense 余弦和 BM25 做归一化。
        原始分数保存在 similarity / bm25_score 中，排序依据单独记在 fused_score。
        """
        fused: Dict[str, Dict[str, Any]] = {}
        for rank, item in enumerate(dense_results, start=1):
            doc_id = item.get("id") or f"dense-{rank}"
            entry = fused.setdefault(doc_id, {**item, "rank_dense": rank, "rank_sparse": None})
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + \
                self.RRF_DENSE_WEIGHT / (self.RRF_K + rank)

        top_bm25 = max((item.get("bm25_score", 0.0) for item in sparse_results), default=1.0) or 1.0
        for rank, item in enumerate(sparse_results, start=1):
            doc_id = item.get("id") or f"sparse-{rank}"
            entry = fused.get(doc_id)
            if entry is None:
                entry = {**item, "rank_dense": None, "rank_sparse": rank,
                         "similarity": round(item.get("bm25_score", 0.0) / top_bm25, 5)}
                fused[doc_id] = entry
            else:
                entry["rank_sparse"] = rank
                entry["bm25_score"] = item.get("bm25_score")
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + \
                self.RRF_SPARSE_WEIGHT / (self.RRF_K + rank)

        merged = list(fused.values())
        for item in merged:
            item["fused_score"] = round(item.get("rrf_score", 0.0), 6)
            item["similarity"] = round(float(item.get("similarity", 0.0) or 0.0), 5)
        merged.sort(key=lambda x: (-x.get("fused_score", 0.0),
                                   x.get("rank_dense") or 10 ** 6))
        return merged[:top_k]

    @staticmethod
    def _dedupe(results: List[Dict]) -> List[Dict]:
        """按 URL 去重，URL 为空时回退到标题"""
        seen, unique = set(), []
        for item in results:
            key = (item.get("url") or "").strip() or (item.get("title") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    @staticmethod
    def _diversify(results: List[Dict], min_types: int) -> List[Dict]:
        """在保持首位不变的前提下，让结果至少覆盖 min_types 种资源类型"""
        if len(results) < 2:
            return results
        chosen, used = [], set()
        chosen.append(results[0])
        used.add(results[0].get("resource_type", ""))
        for item in results[1:]:
            rtype = item.get("resource_type", "")
            if rtype not in used:
                chosen.append(item)
                used.add(rtype)
                if len(used) >= min_types:
                    break
        picked = {id(x) for x in chosen}
        chosen.extend(item for item in results if id(item) not in picked)
        return chosen

    # ------------------------------------------------------------------
    # 反馈与统计
    # ------------------------------------------------------------------
    def update_feedback(self, resource_id: str, rating: float) -> bool:
        """
        更新资源反馈评分

        Args:
            resource_id: 资源ID
            rating: 用户评分（1-5分）

        Returns:
            是否更新成功
        """
        if not self._initialized:
            return False

        try:
            existing = self.collection.get(ids=[resource_id])

            if not existing["metadatas"]:
                print(f"[vector_store] 资源不存在: {resource_id}")
                return False

            metadata = existing["metadatas"][0]
            old_rating = float(metadata.get("rating", 0))
            old_count = int(metadata.get("feedback_count", 0))

            new_count = old_count + 1
            new_rating = ((old_rating * old_count) + rating) / new_count

            metadata["rating"] = str(round(new_rating, 2))
            metadata["feedback_count"] = str(new_count)

            self.collection.update(ids=[resource_id], metadatas=[metadata])
            self._query_cache.clear()
            print(f"[vector_store] 资源评分更新: {old_rating:.1f} -> {new_rating:.1f} ({new_count}条反馈)")
            return True

        except Exception as e:
            print(f"[vector_store] 更新反馈失败: {e}")
            return False

    def get_resource_stats(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        输入资源 ID，返回该资源的评分与反馈数。

        反馈提交后前端靠这个接口回填展示，页面刷新后也能拿到最新值。
        资源不存在返回 None，由调用方决定映射成 404 还是空结果。
        """
        if not self._initialized or not resource_id:
            return None

        try:
            existing = self.collection.get(ids=[resource_id])
            if not existing.get("metadatas"):
                return None

            metadata = existing["metadatas"][0] or {}
            return {
                "id": resource_id,
                "title": metadata.get("title", ""),
                "rating": float(metadata.get("rating", 0) or 0),
                "feedback_count": int(metadata.get("feedback_count", 0) or 0),
            }
        except Exception as exc:
            print(f"[vector_store] 读取资源统计失败: {exc}")
            return None

    def get_all_resources(self) -> List[Dict]:
        """获取所有资源"""
        if not self._initialized:
            return []

        try:
            results = self.collection.get()
            return self._format_search_results({
                "documents": [results["documents"]],
                "metadatas": [results["metadatas"]],
                "ids": [results["ids"]],
            })
        except Exception as e:
            print(f"[vector_store] 获取资源失败: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息（含检索缓存命中率）"""
        if not self._initialized:
            return {"error": "数据库未初始化"}

        try:
            all_resources = self.get_all_resources()
            fields, types, sources = {}, {}, {}
            levels: Dict[str, int] = {}

            for r in all_resources:
                field = r.get("field", "未知")
                fields[field] = fields.get(field, 0) + 1
                rtype = r.get("resource_type", "未知")
                types[rtype] = types.get(rtype, 0) + 1
                lvl = r.get("level", "未知")
                levels[lvl] = levels.get(lvl, 0) + 1
                src = r.get("source", "未知")
                sources[src] = sources.get(src, 0) + 1

            total_calls = self._stats["cache_hits"] + self._stats["cache_misses"]
            return {
                "total_count": len(all_resources),
                "fields": fields,
                "types": types,
                "levels": levels,
                "sources": sources,
                "retrieval": {
                    **self._stats,
                    "cache_hit_rate": round(self._stats["cache_hits"] / total_calls, 4)
                    if total_calls else 0.0,
                    "avg_latency_ms": round(
                        self._stats["latency_ms_total"] / max(self._stats["cache_misses"], 1), 2),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    def reset_database(self):
        """重置数据库（谨慎使用）"""
        if not self._initialized:
            return

        try:
            self.client.delete_collection(self.collection_name)
            self._init_collection()
            self._invalidate()
            print("[vector_store] 数据库已重置")
        except Exception as e:
            print(f"[vector_store] 重置失败: {e}")


PREDEFINED_RESOURCES = [
    {
        "title": "Python基础教程",
        "description": "系统学习Python编程基础，包括变量、数据类型、控制流、函数等核心概念",
        "resource_type": "视频教程",
        "field": "编程",
        "level": "beginner",
        "url": "https://www.bilibili.com/video/BV1wD4y1o7AS/",
        "tags": ["Python", "编程基础", "入门"],
        "source": "system"
    },
    {
        "title": "机器学习实战",
        "description": "从理论到实践，掌握机器学习核心算法和应用",
        "resource_type": "文字教程",
        "field": "AI",
        "level": "intermediate",
        "url": "https://scikit-learn.org/stable/",
        "tags": ["机器学习", "AI", "sklearn"],
        "source": "system"
    },
    {
        "title": "Transformer原理详解",
        "description": "深入理解Transformer架构和注意力机制",
        "resource_type": "文档资料",
        "field": "AI",
        "level": "intermediate",
        "url": "https://jalammar.github.io/illustrated-transformer/",
        "tags": ["Transformer", "大模型", "NLP"],
        "source": "system"
    },
    {
        "title": "高等数学核心概念",
        "description": "微积分、线性代数、概率论等数学基础课程",
        "resource_type": "视频教程",
        "field": "数学",
        "level": "beginner",
        "url": "https://www.bilibili.com/video/BV1HW411H7Wv/",
        "tags": ["数学", "微积分", "线性代数"],
        "source": "system"
    },
    {
        "title": "React官方文档",
        "description": "React前端框架官方学习资源",
        "resource_type": "文档资料",
        "field": "编程",
        "level": "intermediate",
        "url": "https://react.dev/",
        "tags": ["React", "前端", "TypeScript"],
        "source": "system"
    }
]


def load_catalog_seed_resources() -> List[Dict[str, Any]]:
    """读取 approved 资源 JSONL，失败时回退旧版预设资源"""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data", "knowledge_base", "learning_resources.jsonl"
    )
    if not os.path.exists(path):
        return PREDEFINED_RESOURCES
    resources = []
    try:
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("review_status") == "approved":
                    resources.append(item)
    except Exception as exc:
        print(f"[vector_store] 资源目录读取失败，使用预设资源: {exc}")
        return PREDEFINED_RESOURCES
    return resources or PREDEFINED_RESOURCES


def seed_catalog_resources(store: VectorStoreManager, resources: List[Dict[str, Any]]) -> int:
    """将资源以原始稳定 ID 批量写入 ChromaDB，返回成功数量"""
    if not resources or not store._initialized:
        return 0
    ids, documents, metadatas = [], [], []
    for item in resources:
        resource = LearningResource(
            id=str(item["id"]),
            title=str(item["title"]),
            description=str(item["description"]),
            resource_type=str(item["resource_type"]),
            field=str(item["field"]),
            level=str(item["level"]),
            url=str(item["url"]),
            tags=[str(tag) for tag in item.get("tags", [])],
            source=str(item.get("source", "system")),
            rating=float(item.get("rating", 0.0)),
            feedback_count=int(item.get("feedback_count", 0)),
            created_at=str(item.get("created_at", "")),
        )
        ids.append(resource.id)
        documents.append(f"{resource.title}\n{resource.description}")
        metadatas.append(resource.to_metadata())
    store.collection.add(ids=ids, documents=documents, metadatas=metadatas)
    store._invalidate()
    return len(ids)


def init_vector_store_with_seed_data(db_path: Optional[str] = None) -> VectorStoreManager:
    """初始化向量数据库；集合为空时加载资源目录种子数据"""
    store = VectorStoreManager(db_path=db_path)

    if store._initialized:
        stats = store.get_stats()
        if stats.get("total_count", 0) == 0:
            resources = load_catalog_seed_resources()
            print(f"[vector_store] 加载资源目录种子数据 ({len(resources)} 条)...")
            added = seed_catalog_resources(store, resources)
            print(f"[vector_store] 已加载 {added} 个资源")

    return store


if __name__ == "__main__":
    print("=" * 50)
    print("向量数据库测试")
    print("=" * 50)

    store = init_vector_store_with_seed_data()

    print("\n数据库统计:")
    print(json.dumps(store.get_stats(), ensure_ascii=False, indent=2))

    print("\n搜索测试: 'Python编程入门'")
    results = store.search("Python编程入门", field="编程", top_k=3)
    for r in results:
        print(f"\n- {r['title']}")
        print(f"  类型: {r['resource_type']} | 相似度: {r['similarity']:.3f}")
        print(f"  URL: {r['url']}")
