# 文件：tests/test_web_search.py
# 功能：联网兜底链路回归（全部 mock，不发起真实网络请求）

from types import SimpleNamespace

import pytest

from src.tools import web_search as ws
from src.tools.web_search import WebSearchEngine, WebSearchError


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        if self.payload is None:
            raise ValueError("not json")
        return self.payload


class _FakeClient:
    """SDK 通道：可配置成功或抛异常"""

    def __init__(self, exc=None, payload=None):
        self.exc = exc
        self.payload = payload
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.payload or {"results": []}


def _payload(n=1):
    return {
        "results": [
            {"title": f"教程 {i}", "url": f"https://example.com/{i}",
             "content": "内容", "score": 0.9 - i * 0.1}
            for i in range(n)
        ]
    }


@pytest.fixture
def engine(monkeypatch):
    """一个只走 REST 通道、key 已配置的引擎（避免依赖真实 SDK 行为）"""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.setattr(ws, "TAVILY_AVAILABLE", False)
    return WebSearchEngine()


def _stub_rest(monkeypatch, response):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(ws, "requests", SimpleNamespace(post=fake_post))
    return calls


def test_switch_off_blocks_search_without_request(monkeypatch):
    """WEB_SEARCH_ENABLED=false 时明确报原因，不发请求也不返回空列表"""
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    monkeypatch.setattr(ws, "TAVILY_AVAILABLE", False)
    calls = _stub_rest(monkeypatch, _FakeResponse(payload=_payload()))

    engine = WebSearchEngine()
    assert engine.is_available() is False
    assert "WEB_SEARCH_ENABLED" in engine.status()["reason"]
    with pytest.raises(WebSearchError):
        engine.search("Python 教程")
    assert calls == []


def test_missing_key_blocks_search_with_reason(monkeypatch):
    """没填 key 时给出明确原因，而不是静默返回空结果"""
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.setattr(ws, "TAVILY_AVAILABLE", False)

    engine = WebSearchEngine()
    assert engine.status()["api_key_configured"] is False
    with pytest.raises(WebSearchError, match="TAVILY_API_KEY"):
        engine.search("Python 教程")


def test_rest_channel_returns_results(engine, monkeypatch):
    """REST 直连可用，且不依赖 tavily-python 是否安装"""
    calls = _stub_rest(monkeypatch, _FakeResponse(payload=_payload(2)))

    results = engine.search("Python 教程", max_results=2)

    assert len(results) == 2
    assert results[0].url == "https://example.com/0"
    assert engine.status()["channel"] == "tavily-rest"
    assert engine.status()["last_error"] == ""
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0][1]["timeout"] == ws.WEB_SEARCH_TIMEOUT


def test_sdk_failure_falls_back_to_rest(engine, monkeypatch):
    """SDK 抛异常时自动切 REST，最终仍有结果"""
    engine.client = _FakeClient(exc=RuntimeError("sdk down"))
    _stub_rest(monkeypatch, _FakeResponse(payload=_payload()))

    results = engine.search("Python 教程")

    assert len(results) == 1
    assert engine.status()["channel"] == "tavily-rest"


def test_all_channels_fail_raises_instead_of_empty(engine, monkeypatch):
    """两条通道都失败时抛带原因的异常，绝不返回空列表"""
    engine.client = _FakeClient(exc=RuntimeError("sdk down"))
    _stub_rest(monkeypatch, _FakeResponse(status_code=401, payload={"detail": "bad key"}))

    with pytest.raises(WebSearchError) as exc:
        engine.search("Python 教程")

    message = str(exc.value)
    assert "sdk down" in message and "401" in message
    assert "联网搜索全部通道失败" in engine.status()["last_error"]


def test_fallback_search_never_returns_empty(engine, monkeypatch):
    """旧的备用函数不再 return []：要么有结果，要么抛异常"""
    _stub_rest(monkeypatch, _FakeResponse(status_code=500, text="server error"))

    with pytest.raises(WebSearchError):
        engine._fallback_search("Python 教程", 3)


def test_search_learning_resources_raises_when_every_query_fails(engine, monkeypatch):
    """三条查询全失败时不返回空资源列表"""
    monkeypatch.setattr(engine, "search", lambda *a, **kw: (_ for _ in ()).throw(
        WebSearchError("未配置 TAVILY_API_KEY")))

    with pytest.raises(WebSearchError, match="未获得可用资源"):
        engine.search_learning_resources("量子计算", max_results=3)


def test_search_learning_resources_dedupes_and_marks_source(engine, monkeypatch):
    """部分查询有结果就返回，去重且标注 web_search 来源"""
    monkeypatch.setattr(
        engine, "search",
        lambda *a, **kw: engine._parse_results(_payload(2)),
    )

    resources = engine.search_learning_resources("Python 编程", max_results=3)

    assert len(resources) == 2
    assert {r["source"] for r in resources} == {"web_search"}
    assert resources[0]["field"] == "编程"


def test_parse_results_drops_items_without_url_or_title(engine):
    """脏结果不会变成空壳资源"""
    payload = {"results": [
        {"title": "有链接", "url": "https://example.com/a", "content": "x"},
        {"title": "没链接", "url": "", "content": "x"},
        {"url": "https://example.com/b", "content": "x"},
    ]}

    results = engine._parse_results(payload)

    assert len(results) == 1 and results[0].url == "https://example.com/a"


def test_default_result_is_non_empty_and_marked_degraded():
    """最终兜底不再返回空 resources，且带 degraded 标记"""
    from src.core.resource_recommender import ResourceRecommenderAgent

    agent = object.__new__(ResourceRecommenderAgent)
    result = agent._get_default_result("联网与 LLM 均失败")

    assert len(result["resources"]) == 1
    assert result["resources"][0]["source"] == "fallback_notice"
    assert result["rag_info"]["degraded"] is True
    assert "联网与 LLM 均失败" in result["rag_info"]["reason"]


def test_recommend_without_objective_returns_notice():
    """缺少学习目标时也返回降级说明，而不是空列表"""
    from src.core.resource_recommender import ResourceRecommenderAgent

    agent = object.__new__(ResourceRecommenderAgent)
    result = agent.recommend({}, {})

    assert result["resources"] and result["rag_info"]["degraded"] is True


def test_search_web_records_reason_when_unavailable(monkeypatch):
    """Self-RAG 里联网不可用时留下原因，不再只打一行日志就吞掉"""
    from src.rag.self_rag_recommender import RAGState, SelfRAGRecommender

    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    monkeypatch.setattr(ws, "TAVILY_AVAILABLE", False)

    recommender = object.__new__(SelfRAGRecommender)
    recommender.web_search = WebSearchEngine()
    recommender.MAX_WEB_RESULTS = 3
    state = RAGState(learning_objective="量子计算")

    result = recommender._search_web(state)

    assert result.web_results == []
    assert "WEB_SEARCH_ENABLED" in result.web_error


def test_search_web_success_clears_error():
    """联网成功后结果进入 state，且不残留失败原因"""
    from src.rag.self_rag_recommender import RAGState, SelfRAGRecommender

    fake = SimpleNamespace(
        is_available=lambda: True,
        status=lambda: {"available": True, "reason": ""},
        search_learning_resources=lambda **kwargs: [
            {"title": "网络教程", "url": "https://example.com/web", "source": "web_search"}
        ],
    )
    recommender = object.__new__(SelfRAGRecommender)
    recommender.web_search = fake
    recommender.MAX_WEB_RESULTS = 3
    state = RAGState(learning_objective="量子计算")

    result = recommender._search_web(state)

    assert len(result.web_results) == 1
    assert result.web_search_count == 1
    assert result.web_error == ""


def test_web_results_survive_low_kb_quality():
    """知识库质量分低时，联网拿到的资源不能被 LLM 兜底整体覆盖"""
    from src.core.resource_recommender import ResourceRecommenderAgent

    web_resource = {"title": "网络教程", "source": "web_search",
                    "url": "https://example.com/web", "resource_type": "文字教程"}
    agent = object.__new__(ResourceRecommenderAgent)
    agent.rag_recommender = SimpleNamespace(recommend=lambda **kwargs: {
        "resources": [web_resource],
        "quality": {"passed": False},
        "kb_relevance": 0.2,
        "source_info": "网络1个",
    })
    agent._rag_initialized = True
    llm_calls = []
    agent._recommend_with_llm = lambda *a, **kw: llm_calls.append(True) or {"resources": []}

    result = agent.recommend({"learning_objective": "量子计算"}, {})

    assert result["resources"] == [web_resource]
    assert result["rag_info"]["web_count"] == 1
    assert result["rag_info"]["degraded"] is False
    assert llm_calls == []
