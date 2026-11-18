# -*- coding: utf-8 -*-
"""
网络搜索工具模块
集成Tavily搜索引擎，实现实时学习资源搜索

核心功能：
- 搜索最新学习资源
- 搜索结果格式化处理
- SDK 主通道 + REST 直连备用通道；失败抛异常，不再静默返回空列表
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from src.paths import BACKEND_ROOT

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

if DOTENV_AVAILABLE:
    # .env 在 backend/ 根目录，不在本文件所在的 src/tools/；路径统一从 src.paths 取
    load_dotenv(str(BACKEND_ROOT / ".env"))


try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    print("[web_search] 警告: tavily-python 未安装，改用 REST 直连")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


TAVILY_API_URL = "https://api.tavily.com/search"
WEB_SEARCH_TIMEOUT = 15  # 秒：联网失败不能拖住整条规划链路


class WebSearchError(RuntimeError):
    """联网搜索不可用或全部通道失败。

    抛异常而不是返回空列表：上层要能区分「搜了但没有结果」和「根本没搜成」，
    否则失败会被当成空结果吞掉，前端只看到一片空白。
    """


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    content: str
    score: float
    raw_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转成可 JSON 序列化的字典，便于日志与评测落盘。"""
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
    """网络搜索引擎：SDK 优先，REST 直连备用，两条通道都不返回空值。"""

    def __init__(self, api_key: Optional[str] = None, enabled: Optional[bool] = None):
        """初始化搜索引擎。

        Args:
            api_key: Tavily API Key，不传则读环境变量 TAVILY_API_KEY
            enabled: 显式开关，不传则读 WEB_SEARCH_ENABLED（默认开启）
        """
        self.api_key = (api_key or os.getenv("TAVILY_API_KEY") or "").strip()
        self.enabled = self._read_enabled_flag() if enabled is None else bool(enabled)
        self.client = None
        self.last_error = ""
        self.channel = "none"

        if not self.enabled:
            self.last_error = "WEB_SEARCH_ENABLED=false，联网兜底已关闭"
            print(f"[web_search] {self.last_error}")
            return
        if not self.api_key:
            self.last_error = "未配置 TAVILY_API_KEY"
            print(f"[web_search] {self.last_error}，联网兜底不可用")
            return
        if not TAVILY_AVAILABLE and not REQUESTS_AVAILABLE:
            self.last_error = "tavily-python 与 requests 均不可用"
            print(f"[web_search] {self.last_error}")
            return

        if TAVILY_AVAILABLE:
            try:
                self.client = TavilyClient(api_key=self.api_key)
                print("[web_search] Tavily SDK 初始化成功")
            except Exception as e:
                self.last_error = f"Tavily SDK 初始化失败: {e}"
                print(f"[web_search] {self.last_error}，改用 REST 直连")
        else:
            print("[web_search] tavily-python 未安装，使用 REST 直连")

    @staticmethod
    def _read_enabled_flag() -> bool:
        """读取 WEB_SEARCH_ENABLED；只有明确写 0/false/no/off 才算关闭。"""
        raw = os.getenv("WEB_SEARCH_ENABLED", "true").strip().lower()
        return raw not in ("0", "false", "no", "off")

    def _availability_error(self) -> str:
        """返回不可用原因；可用时返回空字符串。"""
        if not self.enabled:
            return "WEB_SEARCH_ENABLED=false，联网兜底已关闭"
        if not self.api_key:
            return "未配置 TAVILY_API_KEY"
        if not (self.client or REQUESTS_AVAILABLE):
            return "tavily-python 与 requests 均不可用"
        return ""

    def is_available(self) -> bool:
        """检查搜索功能是否可用（REST 直连也算可用，不依赖 SDK 是否安装）"""
        return self._availability_error() == ""

    def status(self) -> Dict[str, Any]:
        """诊断信息：开关、key 是否配置、当前通道、最近一次错误。"""
        return {
            "enabled": self.enabled,
            "api_key_configured": bool(self.api_key),
            "channel": self.channel,
            "available": self.is_available(),
            "reason": self._availability_error(),
            "last_error": self.last_error,
        }

    def search(self,
               query: str,
               max_results: int = 5,
               search_depth: str = "basic",
               include_answer: bool = False,
               include_images: bool = False) -> List[SearchResult]:
        """执行网络搜索。

        SDK 失败或返回 0 条时自动切 REST 直连；两条通道都失败抛 WebSearchError，
        绝不返回空列表冒充成功。include_images 保留参数兼容，当前不返回图片。
        """
        reason = self._availability_error()
        if reason:
            raise WebSearchError(reason)

        errors: List[str] = []
        if self.client:
            try:
                results = self._tavily_search(query, max_results, search_depth, include_answer)
                if results:
                    self.channel = "tavily-sdk"
                    self.last_error = ""
                    print(f"[web_search] SDK 返回 {len(results)} 个结果")
                    return results
                errors.append("Tavily SDK 返回 0 条结果")
            except Exception as e:
                errors.append(f"Tavily SDK: {e}")
                print(f"[web_search] SDK 搜索失败，切换 REST 直连: {e}")

        if REQUESTS_AVAILABLE:
            try:
                results = self._rest_search(query, max_results, search_depth, include_answer)
                if results:
                    self.channel = "tavily-rest"
                    self.last_error = ""
                    print(f"[web_search] REST 返回 {len(results)} 个结果")
                    return results
                errors.append("Tavily REST 返回 0 条结果")
            except Exception as e:
                errors.append(f"Tavily REST: {e}")
                print(f"[web_search] REST 搜索失败: {e}")

        self.last_error = "联网搜索全部通道失败: " + " | ".join(errors)
        raise WebSearchError(self.last_error)

    def _tavily_search(self,
                       query: str,
                       max_results: int,
                       search_depth: str,
                       include_answer: bool) -> List[SearchResult]:
        """主通道：tavily-python SDK。异常向上抛，由 search() 决定降级。"""
        print(f"[web_search] Tavily SDK 搜索: {query}")
        response = self.client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=include_answer,
            include_raw_content=False,
            timeout=WEB_SEARCH_TIMEOUT,
        )
        return self._parse_results(response)

    def _rest_search(self,
                     query: str,
                     max_results: int,
                     search_depth: str = "basic",
                     include_answer: bool = False) -> List[SearchResult]:
        """备用通道：不依赖 SDK，直接 POST Tavily REST /search。"""
        print(f"[web_search] Tavily REST 搜索: {query}")
        payload = {
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": False,
        }
        response = requests.post(
            TAVILY_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=WEB_SEARCH_TIMEOUT,
        )
        if response.status_code != 200:
            detail = ""
            try:
                body = response.json()
                detail = body.get("detail") or body.get("error") or ""
            except Exception:
                detail = (response.text or "")[:200]
            raise WebSearchError(f"Tavily REST HTTP {response.status_code}: {detail}")
        return self._parse_results(response.json())

    @staticmethod
    def _parse_results(payload: Dict[str, Any]) -> List[SearchResult]:
        """把 Tavily 响应统一转成 SearchResult；无 URL/标题的条目直接丢弃。"""
        results = []
        for item in (payload.get("results") or []):
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            title = item.get("title") or ""
            if not url or not title:
                continue
            try:
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            results.append(SearchResult(
                title=title,
                url=url,
                content=item.get("content") or "",
                score=score,
                raw_content=item.get("raw_content"),
            ))
        return results

    def _fallback_search(self, query: str, max_results: int) -> List[SearchResult]:
        """兼容旧调用名：备用通道即 REST 直连，不再返回空列表。"""
        return self._rest_search(query, max_results)

    def search_learning_resources(self,
                                  learning_objective: str,
                                  current_foundation: str = "零基础",
                                  max_results: int = 3) -> List[Dict]:
        """按多条查询搜索学习资源。

        任一查询拿到结果就返回；全部失败抛 WebSearchError，
        不返回空列表让上层误以为「联网兜底已正常工作」。
        """
        year = datetime.now().year
        queries = [
            f"{learning_objective} 学习教程 课程",
            f"{learning_objective} 入门 推荐",
            f"{learning_objective} best resources {year}",
        ]

        all_results = []
        seen_urls = set()
        errors: List[str] = []

        for q in queries:
            try:
                results = self.search(q, max_results=max_results)
            except WebSearchError as e:
                errors.append(str(e))
                continue
            for r in results:
                if r.url and r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)
                    if len(all_results) >= max_results:
                        break
            if len(all_results) >= max_results:
                break

        if not all_results:
            detail = errors[0] if errors else "所有查询都没有返回结果"
            self.last_error = f"联网搜索未获得可用资源: {detail}"
            raise WebSearchError(self.last_error)

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


def init_web_search() -> WebSearchEngine:
    """初始化网络搜索引擎"""
    return WebSearchEngine()


if __name__ == "__main__":
    print("=" * 50)
    print("网络搜索测试")
    print("=" * 50)

    engine = init_web_search()
    print(f"状态: {engine.status()}")

    if not engine.is_available():
        print("\n[提示] 在 backend/.env 填入 TAVILY_API_KEY，并保持 WEB_SEARCH_ENABLED=true")
        print("  注册地址: https://tavily.com")
    else:
        print("\n搜索测试: 'Python编程入门教程'")
        try:
            results = engine.search("Python编程入门教程", max_results=3)
            for r in results:
                print(f"\n- {r.title}")
                print(f"  URL: {r.url}")
                print(f"  内容: {r.content[:100]}...")
                print(f"  分数: {r.score:.3f}")
        except WebSearchError as e:
            print(f"\n搜索失败: {e}")
