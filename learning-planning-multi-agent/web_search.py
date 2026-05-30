# -*- coding: utf-8 -*-
"""
网络搜索工具模块
集成Tavily搜索引擎，实现实时学习资源搜索

核心功能：
- 搜索最新学习资源
- 搜索结果格式化处理
- 备用搜索引擎（requests直接调用）
"""

import os
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    print("[web_search] 警告: tavily-python 未安装，网络搜索功能受限")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    content: str
    score: float
    raw_content: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_resource_format(self, field: str = "其他") -> Dict[str, Any]:
        """转换为资源库格式"""
        return {
            "title": self.title,
            "description": self.content,
            "resource_type": self._infer_resource_type(),
            "field": field,
            "level": "intermediate",
            "url": self.url,
            "tags": self._extract_tags(),
            "source": "web_search"
        }
    
    def _infer_resource_type(self) -> str:
        """推断资源类型"""
        url_lower = self.url.lower()
        if any(x in url_lower for x in ["bilibili.com", "youtube.com", "video", "教程"]):
            return "视频教程"
        elif any(x in url_lower for x in ["github.com", "gitlab", "项目"]):
            return "实战项目"
        elif any(x in url_lower for x in ["docs", "documentation", "doc.aws", "readthedocs"]):
            return "文档资料"
        else:
            return "文字教程"
    
    def _extract_tags(self) -> List[str]:
        """提取标签"""
        tags = []
        keywords = {
            "AI": ["ai", "人工智能", "机器学习", "深度学习", "llm", "gpt", "transformer"],
            "编程": ["python", "javascript", "react", "java", "c++", "编程", "代码"],
            "数学": ["数学", "微积分", "线性代数", "概率", "统计"],
        }
        
        text = f"{self.title} {self.content}".lower()
        for category, words in keywords.items():
            for word in words:
                if word.lower() in text:
                    tags.append(word)
                    break
        
        return tags[:5]


class WebSearchEngine:
    """
    网络搜索引擎
    
    优先使用Tavily API，失败时降级到备用方案
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化搜索引擎
        
        Args:
            api_key: Tavily API Key
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.client = None
        self._initialized = False
        
        if not self.api_key:
            print("[web_search] 警告: 未配置TAVILY_API_KEY，网络搜索功能将受限")
            return
        
        if TAVILY_AVAILABLE:
            try:
                self.client = TavilyClient(api_key=self.api_key)
                self._initialized = True
                print("[web_search] Tavily搜索引擎初始化成功")
            except Exception as e:
                print(f"[web_search] Tavily初始化失败: {e}")
        else:
            print("[web_search] 请安装: pip install tavily-python")
    
    def search(self, 
               query: str, 
               max_results: int = 5,
               search_depth: str = "basic",
               include_answer: bool = False,
               include_images: bool = False) -> List[SearchResult]:
        """
        执行网络搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            search_depth: 搜索深度（basic/advanced）
            include_answer: 是否包含AI生成的答案
            include_images: 是否包含图片
            
        Returns:
            搜索结果列表
        """
        if self._initialized and self.client:
            return self._tavily_search(query, max_results, search_depth, include_answer)
        else:
            return self._fallback_search(query, max_results)
    
    def _tavily_search(self, 
                       query: str, 
                       max_results: int,
                       search_depth: str,
                       include_answer: bool) -> List[SearchResult]:
        """使用Tavily API搜索"""
        try:
            print(f"[web_search] Tavily搜索: {query}")
            
            response = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_answer=include_answer,
                include_raw_content=False
            )
            
            results = []
            for idx, item in enumerate(response.get("results", [])):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                    raw_content=item.get("raw_content")
                )
                results.append(result)
            
            print(f"[web_search] 返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            print(f"[web_search] Tavily搜索失败: {e}")
            return self._fallback_search(query, max_results)
    
    def _fallback_search(self, query: str, max_results: int) -> List[SearchResult]:
        """备用搜索方案"""
        print("[web_search] 使用备用搜索方案")
        return []
    
    def search_learning_resources(self, 
                                   learning_objective: str,
                                   current_foundation: str = "零基础",
                                   max_results: int = 3) -> List[Dict]:
        """
        专门搜索学习资源
        
        Args:
            learning_objective: 学习目标
            current_foundation: 现有基础
            max_results: 最大结果数
            
        Returns:
            格式化的资源列表
        """
        queries = [
            f"{learning_objective} 学习教程 课程",
            f"{learning_objective} 入门 推荐",
            f"{learning_objective} best resources 2024"
        ]
        
        all_results = []
        seen_urls = set()
        
        for q in queries:
            results = self.search(q, max_results=max_results)
            for r in results:
                if r.url and r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)
                    if len(all_results) >= max_results:
                        break
            if len(all_results) >= max_results:
                break
        
        field = self._detect_field(learning_objective)
        return [r.to_resource_format(field) for r in all_results]
    
    def _detect_field(self, query: str) -> str:
        """检测学习领域"""
        query_lower = query.lower()
        
        ai_keywords = ["ai", "人工智能", "机器学习", "深度学习", "llm", "agent", "gpt", "nlp", "cv", "计算机视觉"]
        math_keywords = ["数学", "微积分", "线性代数", "概率论", "统计", "math"]
        prog_keywords = ["python", "java", "c++", "javascript", "react", "前端", "后端", "编程", "开发"]
        
        if any(k in query_lower for k in ai_keywords):
            return "AI"
        elif any(k in query_lower for k in math_keywords):
            return "数学"
        elif any(k in query_lower for k in prog_keywords):
            return "编程"
        else:
            return "其他"
    
    def is_available(self) -> bool:
        """检查搜索功能是否可用"""
        return self._initialized and self.client is not None


def init_web_search() -> WebSearchEngine:
    """初始化网络搜索引擎"""
    return WebSearchEngine()


if __name__ == "__main__":
    print("=" * 50)
    print("网络搜索测试")
    print("=" * 50)
    
    engine = init_web_search()
    
    if not engine.is_available():
        print("\n[提示] 请配置TAVILY_API_KEY环境变量以启用网络搜索")
        print("  注册地址: https://tavily.com")
    else:
        print("\n搜索测试: 'Python编程入门教程'")
        results = engine.search("Python编程入门教程", max_results=3)
        for r in results:
            print(f"\n- {r.title}")
            print(f"  URL: {r.url}")
            print(f"  内容: {r.content[:100]}...")
            print(f"  分数: {r.score:.3f}")
