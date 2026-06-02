# -*- coding: utf-8 -*-
"""
Chroma向量数据库管理模块
负责学习资源的存储、检索和管理

核心功能：
- 初始化向量数据库
- 添加学习资源到知识库
- 基于相似度检索资源
- 支持用户反馈资源入库
"""

import os
import json
import uuid
from typing import List, Dict, Optional, Any
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
except ImportError:
    CHROMA_AVAILABLE = False
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


def _tokenize_for_bm25(text: str) -> List[str]:
    """
    BM25 分词函数：优先使用 jieba 中文分词，回退到字符级分词
    """
    if not text:
        return []
    text = text.replace("\n", " ")
    if JIEBA_AVAILABLE:
        return [w for w in jieba.lcut(text) if w.strip()]
    return list(text)


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
    Chroma向量数据库管理器
    
    负责学习资源的持久化存储和相似度检索
    """
    
    COLLECTION_NAME = "learning_resources"
    DEFAULT_DB_PATH = "./chroma_db"
    RRF_K = 60  # RRF 融合常数
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化向量数据库管理器
        
        Args:
            db_path: 数据库存储路径
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.client = None
        self.collection = None
        self._initialized = False

        # ---- BM25 稀疏检索相关 ----
        self.bm25 = None
        self._bm25_docs = []
        self._bm25_ids = []
        self._bm25_stale = True

        if not CHROMA_AVAILABLE:
            print("[vector_store] ChromaDB不可用，请运行: pip install chromadb")
            return
        
        try:
            self._init_client()
            self._init_collection()
            self._initialized = True
            print(f"[vector_store] 向量数据库初始化完成，路径: {self.db_path}")
        except Exception as e:
            print(f"[vector_store] 初始化失败: {e}")
    
    def _init_client(self):
        """初始化Chroma客户端"""
        os.makedirs(self.db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
    
    def _init_collection(self):
        """初始化或获取资源集合（使用中文 Embedding 模型）"""
        try:
            emb_fn = self._create_embedding_function()
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=emb_fn,
                metadata={"description": "学习资源知识库"}
            )
            print(f"[vector_store] Embedding: {getattr(emb_fn, '_model_name', 'default')}")
        except Exception as e:
            print(f"[vector_store] 创建集合失败: {e}")
            raise

    def _create_embedding_function(self):
        """创建 Embedding 函数，优先使用中文 BGE 模型（镜像下载）"""
        model_name = "BAAI/bge-small-zh-v1.5"

        # 方案1: sentence-transformers 加载中文 BGE
        try:
            from sentence_transformers import SentenceTransformer
            from chromadb.api.types import EmbeddingFunction

            class BGEEmbeddingFunction(EmbeddingFunction):
                def __init__(self, model_name):
                    self._model_name = model_name
                    self._model = SentenceTransformer(model_name)

                def __call__(self, input):
                    return self._model.encode(input).tolist()

            emb_fn = BGEEmbeddingFunction(model_name)
            emb_fn._model_name = model_name  # type: ignore
            print(f"[vector_store] Embedding: {model_name} (中文)")
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
        created_at = datetime.now().isoformat()
        
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
            created_at=created_at
        )
        
        try:
            document = f"{title}\n{description}"
            self.collection.add(
                ids=[resource_id],
                documents=[document],
                metadatas=[resource.to_metadata()]
            )
            
            print(f"[vector_store] 资源已添加: {title} (ID: {resource_id})")
            self._bm25_stale = True
            return resource_id

        except Exception as e:
            print(f"[vector_store] 添加资源失败: {e}")
            return None
    
    def add_resources_batch(self, resources: List[Dict]) -> List[str]:
        """
        批量添加资源
        
        Args:
            resources: 资源字典列表
            
        Returns:
            成功添加的资源ID列表
        """
        added_ids = []
        for res in resources:
            rid = self.add_resource(
                title=res.get("title", ""),
                description=res.get("description", ""),
                resource_type=res.get("resource_type", "文档资料"),
                field=res.get("field", "其他"),
                level=res.get("level", "intermediate"),
                url=res.get("url", ""),
                tags=res.get("tags", []),
                source=res.get("source", "system")
            )
            if rid:
                added_ids.append(rid)
        
        return added_ids
    
    def search(self,
               query: str,
               field: Optional[str] = None,
               level: Optional[str] = None,
               top_k: int = 5,
               mode: str = "hybrid") -> List[Dict]:
        """
        增强搜索：dense | sparse | hybrid

        Args:
            query: 查询文本
            field: 可选领域过滤
            level: 可选难度过滤
            top_k: 返回结果数量
            mode: 检索模式 (dense / sparse / hybrid)

        Returns:
            匹配的资源列表
        """
        if not self._initialized:
            return []

        dense_results = []
        if mode in ("dense", "hybrid"):
            try:
                where_filter = {}
                if field:
                    where_filter["field"] = field
                if level:
                    where_filter["level"] = level
                if where_filter:
                    raw = self.collection.query(query_texts=[query], n_results=top_k, where=where_filter)
                else:
                    raw = self.collection.query(query_texts=[query], n_results=top_k)
                dense_results = self._format_search_results(raw)
            except Exception as e:
                print(f"[vector_store] 稠密检索失败: {e}")

        sparse_results = []
        if mode in ("sparse", "hybrid"):
            if self._bm25_stale:
                self._rebuild_bm25_index()
            sparse_results = self._sparse_search(query, top_k)

        if mode == "hybrid" and dense_results and sparse_results:
            return self._rrf_merge(dense_results, sparse_results, top_k)
        elif mode == "sparse":
            return sparse_results[:top_k]
        return dense_results[:top_k]
    
    def _format_search_results(self, results: Dict) -> List[Dict]:
        """格式化搜索结果"""
        formatted = []
        
        if not results or "documents" not in results:
            return formatted
        
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results.get("distances") else []
        ids = results["ids"][0] if results["ids"] else []
        
        for i in range(len(documents)):
            metadata = metadatas[i] if i < len(metadatas) else {}
            formatted.append({
                "id": ids[i] if i < len(ids) else "",
                "title": metadata.get("title", ""),
                "description": documents[i],
                "resource_type": metadata.get("resource_type", ""),
                "field": metadata.get("field", ""),
                "level": metadata.get("level", ""),
                "url": metadata.get("url", ""),
                "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                "source": metadata.get("source", ""),
                "rating": float(metadata.get("rating", 0)),
                "similarity": 1 - distances[i] if i < len(distances) else 0.0
            })
        
        return formatted

    def _rebuild_bm25_index(self):
        """从 Chroma 集合重建 BM25 索引"""
        if not BM25_AVAILABLE:
            return
        try:
            all_data = self.collection.get()
            if not all_data or not all_data["documents"]:
                self._bm25_stale = False
                return
            tokenized = [_tokenize_for_bm25(doc) for doc in all_data["documents"]]
            self.bm25 = BM25Okapi(tokenized)
            self._bm25_docs = all_data["documents"]
            self._bm25_ids = all_data["ids"][0] if all_data["ids"] else []
            self._bm25_stale = False
            tokenizer_info = "jieba中文分词" if JIEBA_AVAILABLE else "字符级分词"
            print(f"[vector_store] BM25索引已重建（{len(self._bm25_ids)}个文档, {tokenizer_info}）")
        except Exception as e:
            print(f"[vector_store] BM25索引重建失败: {e}")

    def _sparse_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """BM25 关键词稀疏检索"""
        if not BM25_AVAILABLE or self.bm25 is None:
            return []
        query_tokens = _tokenize_for_bm25(query)
        scores = self.bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        ranked = [(i, s) for i, s in ranked if s > 0]
        results = []
        for idx, score in ranked[:top_k]:
            doc_id = self._bm25_ids[idx] if idx < len(self._bm25_ids) else ""
            doc_text = self._bm25_docs[idx] if idx < len(self._bm25_docs) else ""
            results.append({
                "id": doc_id,
                "similarity": float(score),
                "bm25_score": float(score),
                "description": doc_text,
                "rank": len(results) + 1,
                "source": "bm25"
            })
        return results

    def _rrf_merge(self, dense_results: List[Dict], sparse_results: List[Dict], top_k: int = 5) -> List[Dict]:
        """RRF 融合稠密和稀疏检索结果"""
        dense_rank = {r["id"]: i + 1 for i, r in enumerate(dense_results)}
        sparse_rank = {r["id"]: i + 1 for i, r in enumerate(sparse_results)}
        all_ids = set(dense_rank.keys()) | set(sparse_rank.keys())
        scored = []
        for doc_id in all_ids:
            rrf_score = 0.0
            rrf_score += 1.0 / (self.RRF_K + dense_rank.get(doc_id, 999))
            rrf_score += 1.0 / (self.RRF_K + sparse_rank.get(doc_id, 999))
            raw = next((r for r in dense_results if r["id"] == doc_id), None)
            if raw is None:
                raw = next((r for r in sparse_results if r["id"] == doc_id), {})
            scored.append({**raw, "similarity": round(rrf_score, 5)})
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

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
            
            self.collection.update(
                ids=[resource_id],
                metadatas=[metadata]
            )
            
            print(f"[vector_store] 资源评分更新: {old_rating:.1f} -> {new_rating:.1f} ({new_count}条反馈)")
            return True
            
        except Exception as e:
            print(f"[vector_store] 更新反馈失败: {e}")
            return False
    
    def get_all_resources(self) -> List[Dict]:
        """获取所有资源"""
        if not self._initialized:
            return []
        
        try:
            results = self.collection.get()
            return self._format_search_results({"documents": [results["documents"]], 
                                                "metadatas": [results["metadatas"]],
                                                "ids": [results["ids"]]})
        except Exception as e:
            print(f"[vector_store] 获取资源失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        if not self._initialized:
            return {"error": "数据库未初始化"}
        
        try:
            all_resources = self.get_all_resources()
            fields = {}
            types = {}
            sources = {}
            
            for r in all_resources:
                field = r.get("field", "未知")
                fields[field] = fields.get(field, 0) + 1
                
                rtype = r.get("resource_type", "未知")
                types[rtype] = types.get(rtype, 0) + 1
                
                source = r.get("source", "未知")
                sources[source] = sources.get(source, 0) + 1
            
            return {
                "total_count": len(all_resources),
                "fields": fields,
                "types": types,
                "sources": sources
            }
        except Exception as e:
            return {"error": str(e)}
    
    def reset_database(self):
        """重置数据库（谨慎使用）"""
        if not self._initialized:
            return
        
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
            self._init_collection()
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


def init_vector_store_with_seed_data() -> VectorStoreManager:
    """初始化向量数据库并加载预设资源"""
    store = VectorStoreManager()
    
    if store._initialized:
        stats = store.get_stats()
        if stats.get("total_count", 0) == 0:
            print("[vector_store] 加载预设学习资源...")
            added = store.add_resources_batch(PREDEFINED_RESOURCES)
            print(f"[vector_store] 已加载 {len(added)} 个预设资源")
    
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
