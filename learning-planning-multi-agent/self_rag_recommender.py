# -*- coding: utf-8 -*-
"""
Self-RAG智能资源推荐工作流
基于LangGraph实现智能检索、评估和改写闭环

工作流程：
1. 检索判断：是否需要检索？知识库有吗？
2. 相似度检索：从知识库搜索
3. 结果评估：检索结果是否够用？
4. 查询改写：不够则优化查询
5. 网络搜索：知识库不够则调用网络
6. 生成推荐：整合所有资源输出
"""

import os
import json
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime


try:
    from vector_store import VectorStoreManager, init_vector_store_with_seed_data
    VECTOR_STORE_AVAILABLE = True
except ImportError as e:
    VECTOR_STORE_AVAILABLE = False
    print(f"[SelfRAG] 向量数据库模块未加载: {e}")

try:
    from web_search import WebSearchEngine, init_web_search
    WEB_SEARCH_AVAILABLE = True
except ImportError as e:
    WEB_SEARCH_AVAILABLE = False
    print(f"[SelfRAG] 网络搜索模块未加载: {e}")


@dataclass
class RAGState:
    """Self-RAG状态机状态"""
    query: str = ""
    learning_objective: str = ""
    current_foundation: str = "零基础"
    field: str = "其他"
    
    kb_results: List[Dict] = dataclass_field(default_factory=list)
    kb_search_count: int = 0
    kb_relevance_score: float = 0.0
    
    web_results: List[Dict] = dataclass_field(default_factory=list)
    web_search_count: int = 0
    
    rewritten_query: str = ""
    rewrite_count: int = 0
    
    final_resources: List[Dict] = dataclass_field(default_factory=list)
    source_info: str = ""
    
    error: str = ""


class SelfRAGRecommender:
    """
    Self-RAG智能资源推荐器
    
    实现自主判断检索策略的Agentic RAG系统
    """
    
    SIMILARITY_THRESHOLD = 0.5
    MAX_REWRITE_TIMES = 2
    MAX_KB_RESULTS = 5
    MAX_WEB_RESULTS = 3
    
    def __init__(self):
        self.vector_store = None
        self.web_search = None
        self._initialized = False
        
        self._init_services()
    
    def _init_services(self):
        """初始化服务"""
        if VECTOR_STORE_AVAILABLE:
            try:
                self.vector_store = init_vector_store_with_seed_data()
                print(f"[SelfRAG] 向量数据库已连接")
            except Exception as e:
                print(f"[SelfRAG] 向量数据库初始化失败: {e}")
        
        if WEB_SEARCH_AVAILABLE:
            try:
                self.web_search = init_web_search()
                print(f"[SelfRAG] 网络搜索服务已连接")
            except Exception as e:
                print(f"[SelfRAG] 网络搜索初始化失败: {e}")
        
        self._initialized = True
        print("[SelfRAG] Self-RAG推荐器初始化完成")
    
    def _detect_field(self, query: str) -> str:
        """检测学习领域"""
        query_lower = query.lower()
        
        ai_keywords = ["ai", "人工智能", "机器学习", "深度学习", "llm", "agent", "gpt", "nlp", "cv", "计算机视觉", "大模型"]
        math_keywords = ["数学", "微积分", "线性代数", "概率论", "统计", "math"]
        prog_keywords = ["python", "java", "c++", "javascript", "react", "前端", "后端", "编程", "开发", "代码"]
        
        if any(k in query_lower for k in ai_keywords):
            return "AI"
        elif any(k in query_lower for k in math_keywords):
            return "数学"
        elif any(k in query_lower for k in prog_keywords):
            return "编程"
        else:
            return "其他"
    
    def _build_search_query(self, state: RAGState) -> str:
        """构建搜索查询"""
        if state.rewritten_query:
            return state.rewritten_query
        return f"{state.learning_objective} {state.current_foundation}"
    
    def _should_search_kb(self, state: RAGState) -> bool:
        """判断是否需要检索知识库"""
        if state.kb_search_count >= self.MAX_REWRITE_TIMES + 1:
            return False
        return self.vector_store and self.vector_store._initialized
    
    def _search_kb(self, state: RAGState) -> RAGState:
        """检索知识库"""
        if not self.vector_store or not self.vector_store._initialized:
            print("[SelfRAG] 知识库不可用，跳过")
            state.kb_results = []
            state.kb_relevance_score = 0
            return state
        
        query = self._build_search_query(state)
        field = self._detect_field(query)
        state.field = field
        
        print(f"[SelfRAG] 知识库检索: {query} (领域: {field})")
        
        try:
            results = self.vector_store.search(
                query=query,
                field=field if field != "其他" else None,
                top_k=self.MAX_KB_RESULTS
            )
            
            state.kb_results = results
            state.kb_search_count += 1
            
            if results:
                avg_similarity = sum(r.get("similarity", 0) for r in results) / len(results)
                state.kb_relevance_score = avg_similarity
                print(f"[SelfRAG] 找到 {len(results)} 个资源，平均相似度: {avg_similarity:.3f}")
            else:
                state.kb_relevance_score = 0
                print("[SelfRAG] 知识库未找到相关资源")
        except Exception as e:
            print(f"[SelfRAG] 知识库检索失败: {e}")
            state.kb_results = []
            state.kb_relevance_score = 0
        
        return state
    
    def _evaluate_results(self, state: RAGState) -> str:
        """
        评估检索结果是否足够
        
        Returns:
            "sufficient": 结果足够，直接推荐
            "insufficient": 结果不足，需要改写查询
            "kb_empty": 知识库为空，需要网络搜索
        """
        if not state.kb_results:
            print("[SelfRAG] 知识库无结果，尝试网络搜索")
            return "kb_empty"
        
        if state.kb_relevance_score >= self.SIMILARITY_THRESHOLD:
            print(f"[SelfRAG] 结果足够（相似度 {state.kb_relevance_score:.2f} >= {self.SIMILARITY_THRESHOLD}）")
            return "sufficient"
        
        if state.rewrite_count >= self.MAX_REWRITE_TIMES:
            print(f"[SelfRAG] 已达最大改写次数（{self.MAX_REWRITE_TIMES}），尝试网络搜索")
            return "kb_empty"
        
        print(f"[SelfRAG] 结果不足（相似度 {state.kb_relevance_score:.2f} < {self.SIMILARITY_THRESHOLD}），需要改写查询")
        return "insufficient"
    
    def _rewrite_query(self, state: RAGState) -> RAGState:
        """智能改写查询"""
        base_query = state.learning_objective
        foundation = state.current_foundation
        
        rewrite_strategies = [
            f"{base_query} 入门教程 课程",
            f"{base_query} {foundation} 学习指南",
            f"{base_query} 基础知识 资源推荐"
        ]
        
        idx = state.rewrite_count % len(rewrite_strategies)
        state.rewritten_query = rewrite_strategies[idx]
        state.rewrite_count += 1
        
        print(f"[SelfRAG] 查询改写 #{state.rewrite_count}: {state.rewritten_query}")
        return state
    
    def _search_web(self, state: RAGState) -> RAGState:
        """网络搜索补充资源"""
        if not self.web_search or not self.web_search.is_available():
            print("[SelfRAG] 网络搜索不可用，跳过")
            state.web_results = []
            return state
        
        query = self._build_search_query(state)
        print(f"[SelfRAG] 网络搜索: {query}")
        
        try:
            results = self.web_search.search_learning_resources(
                learning_objective=state.learning_objective,
                current_foundation=state.current_foundation,
                max_results=self.MAX_WEB_RESULTS
            )
            
            state.web_results = results
            state.web_search_count += 1
            
            print(f"[SelfRAG] 网络搜索返回 {len(results)} 个资源")
        except Exception as e:
            print(f"[SelfRAG] 网络搜索失败: {e}")
            state.web_results = []
        
        return state
    
    def _merge_and_select(self, state: RAGState) -> RAGState:
        """合并和选择最佳资源"""
        all_resources = []
        
        for kb in state.kb_results:
            resource = {
                "phase": "第一阶段：基础入门",
                "type": kb.get("resource_type", "文档资料"),
                "title": kb.get("title", ""),
                "description": kb.get("description", ""),
                "duration": "2-4小时",
                "difficulty": self._map_level(kb.get("level", "intermediate")),
                "recommendation_reason": f"来自本地知识库，相似度 {kb.get('similarity', 0):.2f}",
                "url": kb.get("url", ""),
                "source": "knowledge_base"
            }
            all_resources.append(resource)
        
        for web in state.web_results:
            resource = {
                "phase": "第一阶段：基础入门",
                "type": web.get("resource_type", "文档资料"),
                "title": web.get("title", ""),
                "description": web.get("description", ""),
                "duration": "2-4小时",
                "difficulty": "初级",
                "recommendation_reason": "来自网络搜索，最新优质资源",
                "url": web.get("url", ""),
                "source": "web_search"
            }
            all_resources.append(resource)
        
        seen_titles = set()
        unique_resources = []
        for r in all_resources:
            if r["title"] and r["title"] not in seen_titles:
                seen_titles.add(r["title"])
                unique_resources.append(r)
                if len(unique_resources) >= 6:
                    break
        
        state.final_resources = unique_resources
        
        sources = []
        if state.kb_results:
            sources.append(f"知识库{len(state.kb_results)}个")
        if state.web_results:
            sources.append(f"网络{len(state.web_results)}个")
        state.source_info = " + ".join(sources) if sources else "无结果"
        
        print(f"[SelfRAG] 最终推荐 {len(unique_resources)} 个资源 (来源: {state.source_info})")
        return state
    
    def _map_level(self, level: str) -> str:
        """映射难度等级"""
        mapping = {
            "beginner": "初级",
            "intermediate": "中级",
            "advanced": "高级"
        }
        return mapping.get(level, "中级")
    
    def recommend(self, 
                  learning_objective: str,
                  current_foundation: str = "零基础",
                  learning_plan: Optional[Dict] = None) -> Dict:
        """
        执行完整的Self-RAG推荐流程
        
        Args:
            learning_objective: 学习目标
            current_foundation: 现有基础
            learning_plan: 学习计划（可选）
            
        Returns:
            包含推荐资源的字典
        """
        state = RAGState(
            learning_objective=learning_objective,
            current_foundation=current_foundation
        )
        
        state = self._search_kb(state)
        decision = self._evaluate_results(state)
        
        if decision == "insufficient":
            state = self._rewrite_query(state)
            state = self._search_kb(state)
            decision = self._evaluate_results(state)
            
            if decision == "insufficient" and state.rewrite_count < self.MAX_REWRITE_TIMES:
                state = self._rewrite_query(state)
                state = self._search_kb(state)
                decision = self._evaluate_results(state)
        
        if decision == "kb_empty":
            state = self._search_web(state)
        
        state = self._merge_and_select(state)
        
        return {
            "resources": state.final_resources,
            "source_info": state.source_info,
            "kb_relevance": state.kb_relevance_score,
            "rewrite_count": state.rewrite_count,
            "used_web_search": len(state.web_results) > 0
        }


def init_self_rag() -> SelfRAGRecommender:
    """初始化Self-RAG推荐器"""
    return SelfRAGRecommender()


if __name__ == "__main__":
    print("=" * 60)
    print("Self-RAG智能资源推荐测试")
    print("=" * 60)
    
    recommender = init_self_rag()
    
    test_cases = [
        ("Python编程", "零基础"),
        ("机器学习", "有数学基础"),
    ]
    
    for goal, foundation in test_cases:
        print(f"\n{'='*60}")
        print(f"测试: {goal} ({foundation})")
        print("=" * 60)
        
        result = recommender.recommend(
            learning_objective=goal,
            current_foundation=foundation
        )
        
        print(f"\n推荐结果 ({len(result['resources'])} 个资源):")
        print(f"来源: {result['source_info']}")
        print(f"知识库相似度: {result['kb_relevance']:.2f}")
        print(f"使用网络搜索: {'是' if result['used_web_search'] else '否'}")
        
        for i, r in enumerate(result['resources'], 1):
            print(f"\n{i}. [{r.get('type', 'N/A')}] {r.get('title', 'N/A')}")
            print(f"   难度: {r.get('difficulty', 'N/A')} | 来源: {r.get('source', 'unknown')}")
            print(f"   URL: {r.get('url', 'N/A')}")
