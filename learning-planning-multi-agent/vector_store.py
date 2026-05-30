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

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("[vector_store] 警告: chromadb 未安装，向量数据库功能不可用")


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
        """初始化或获取资源集合"""
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "学习资源知识库"}
            )
        except Exception as e:
            print(f"[vector_store] 创建集合失败: {e}")
            raise
    
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
               top_k: int = 5) -> List[Dict]:
        """
        基于相似度搜索资源
        
        Args:
            query: 查询文本
            field: 可选领域过滤
            level: 可选难度过滤
            top_k: 返回结果数量
            
        Returns:
            匹配的资源列表
        """
        if not self._initialized:
            return []
        
        try:
            where_filter = {}
            if field:
                where_filter["field"] = field
            if level:
                where_filter["level"] = level
            
            if where_filter:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where_filter
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k
                )
            
            return self._format_search_results(results)
            
        except Exception as e:
            print(f"[vector_store] 搜索失败: {e}")
            return []
    
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
