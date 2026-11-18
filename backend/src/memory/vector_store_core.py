# -*- coding: utf-8 -*-
"""
Chroma 向量数据库管理模块（存储层）

本模块只负责「怎么存、怎么取回一批原始候选」，不负责排序与筛选决策：
- 初始化向量数据库（Embedding 模型与 Chroma 客户端进程内共享）
- 学习资源的增删改查、评分回写
- BM25 索引的构建与失效
- Dense / Sparse 两路召回（各返回按自身分数排好的候选）
- 把业务过滤条件翻译成 Chroma 的 where 语法

融合（RRF）、去重、多样性约束、查询缓存、检索计数都在 src/rag/retrieval.py，
那里才是「检索策略」。这样分层的好处是：换存储不影响排序策略，改排序也不碰数据库代码。
"""

import os
import json
import uuid
import threading
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
        """绑定一个 BGE 模型名；真正的模型实例由 _get_embedding_model 进程内复用。"""
        self._model_name = model_name
        self._model = _get_embedding_model(model_name)

    def __call__(self, input):
        """Chroma 调用本对象的默认入口：批量编码并返回 list[list[float]]。

        Chroma 只接受 Python 原生列表，不能返回 numpy 数组，所以这里 .tolist()。
        """
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
        from src.memory.model_loader import get_sentence_transformer

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
        """转成可 JSON 序列化的字典，用于接口返回与评测输出。"""
        return asdict(self)

    def to_metadata(self) -> Dict[str, Any]:
        """转成 Chroma 的 metadata 结构。

        注意两点：
        - tags 必须压成逗号分隔字符串，Chroma 的 metadata 不支持列表；
        - 这里写的键必须能被 _build_where 正确读回，否则过滤会静默失效。
        """
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

        # ---- 数据版本号 ----
        # 每次写库自增。检索层的缓存键里带着它，所以写完库旧缓存自然不命中，
        # 存储层不需要知道缓存的存在（反过来依赖就错了）。
        self.data_version = 0

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
        # 与稀疏检索取快照、写库失效共用同一把锁，避免「标记失效」和「读索引」交错
        with _CACHE_LOCK:
            self._bm25_loaded = not value
            if value:
                self.bm25 = None
                self._bm25_docs, self._bm25_ids, self._bm25_metas = [], [], []
                _bump_generation(self._store_key)
                for key in [k for k in _BM25_CACHE if k[:2] == (self._store_key, "v1")]:
                    _BM25_CACHE.pop(key, None)
            self._bump_version()

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
            # 写库与缓存失效必须连在一起，否则并发的 BM25 重建可能读到写之前的快照
            with _CACHE_LOCK:
                self.collection.add(
                    ids=[resource_id],
                    documents=[f"{title}\n{description}"],
                    metadatas=[resource.to_metadata()]
                )
                self._invalidate()
            print(f"[vector_store] 资源已添加: {title} (ID: {resource_id})")
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
            with _CACHE_LOCK:
                self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
                self._invalidate()
            return ids
        except Exception as e:
            print(f"[vector_store] 批量添加失败: {e}")
            return []

    def _bump_version(self) -> None:
        """标记数据版本已变化。

        检索层（src/rag/retrieval.py）的缓存键里带着这个版本号，
        所以写完库之后旧缓存自然不再命中，存储层不需要反过来操作缓存对象。
        """
        # 自增必须与「清空派生缓存」在同一临界区内完成，否则并发写会丢自增，
        # 检索缓存就会继续命中写库前的旧结果。
        with _CACHE_LOCK:
            self.data_version += 1

    def _invalidate(self) -> None:
        """写库后：失效 BM25 索引与共享缓存，并提升数据版本号让检索缓存失效"""
        with _CACHE_LOCK:
            _bump_generation(self._store_key)
            for key in [k for k in _BM25_CACHE if k[:2] == (self._store_key, "v1")]:
                _BM25_CACHE.pop(key, None)
            self._bm25_loaded = False
            self.bm25 = None
            self._bm25_docs, self._bm25_ids, self._bm25_metas = [], [], []
            self._bump_version()

    # ------------------------------------------------------------------
    # 原始召回：只负责「取回候选」，融合、去重、多样性在 src/rag/retrieval.py
    # ------------------------------------------------------------------

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
        # 查缓存 → 构建 → 写回 → 绑定本地字段必须是一次 check-then-set：
        # 拆成两段时写库可能夹在中间，把构建前的快照绑到新世代号上。
        with _CACHE_LOCK:
            cache_key = (self._store_key, "v1", _generation(self._store_key))
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
        with _CACHE_LOCK:
            if not self._bm25_loaded:
                self._rebuild_bm25_index()
            # 一次性取成局部快照：遍历过程中若写库替换了实例字段，
            # 也不会出现「A 的 BM25 分数配上 B 的 id/元数据」的错位。
            bm25 = self.bm25
            docs = self._bm25_docs
            ids = self._bm25_ids
            metas = self._bm25_metas
        if bm25 is None:
            return []
        scores = bm25.get_scores(_tokenize_for_bm25(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            meta = metas[idx] if idx < len(metas) else {}
            if field and meta.get("field") != field:
                continue
            if level and meta.get("level") != level:
                continue
            if resource_types and meta.get("resource_type") not in resource_types:
                continue
            document = docs[idx] if idx < len(docs) else ""
            title = meta.get("title", "")
            results.append({
                "id": ids[idx] if idx < len(ids) else "",
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
            # 读-改-写整段串行：并发反馈若都读到同一个 old_count，会互相覆盖评分
            with _CACHE_LOCK:
                existing = self.collection.get(ids=[resource_id])

                if not existing.get("metadatas"):
                    print(f"[vector_store] 资源不存在: {resource_id}")
                    return False

                metadata = existing["metadatas"][0] or {}
                old_rating = float(metadata.get("rating", 0) or 0)
                old_count = int(metadata.get("feedback_count", 0) or 0)

                new_count = old_count + 1
                new_rating = ((old_rating * old_count) + rating) / new_count

                metadata["rating"] = str(round(new_rating, 2))
                metadata["feedback_count"] = str(new_count)

                self.collection.update(ids=[resource_id], metadatas=[metadata])
                # 评分同样写进了 BM25 索引的元数据快照：只提升查询版本号会让稀疏通路
                # 一直返回旧评分，所以这里走完整失效流程，让下一次检索重建快照。
                self._invalidate()
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
        """获取知识库的资源分布统计。

        只描述「库里有什么」，不含检索调用计数——
        检索侧的命中率与延迟由 HybridRetriever.get_retrieval_stats() 提供，
        需要完整的 /api/stats 响应时由接口层把两者合并。
        """
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

            return {
                "total_count": len(all_resources),
                "fields": fields,
                "types": types,
                "levels": levels,
                "sources": sources,
            }
        except Exception as e:
            return {"error": str(e)}

    def reset_database(self):
        """重置数据库（谨慎使用）"""
        if not self._initialized:
            return

        try:
            with _CACHE_LOCK:
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
    # 仅作手动冒烟：这里的 import 只在直接运行本文件时发生，
    # 不构成 memory → rag 的运行时依赖（正常分层里依赖方向是 rag → memory）。
    from src.rag.retrieval import HybridRetriever

    print("=" * 50)
    print("向量数据库测试")
    print("=" * 50)

    store = init_vector_store_with_seed_data()
    retriever = HybridRetriever(store)

    print("\n数据库统计:")
    print(json.dumps(store.get_stats(), ensure_ascii=False, indent=2))

    print("\n搜索测试: 'Python编程入门'")
    results = retriever.search("Python编程入门", field="编程", top_k=3)
    for r in results:
        print(f"\n- {r['title']}")
        print(f"  类型: {r['resource_type']} | 相似度: {r['similarity']:.3f}")
        print(f"  URL: {r['url']}")
