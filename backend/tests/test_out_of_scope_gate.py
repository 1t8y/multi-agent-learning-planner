# 文件：tests/test_out_of_scope_gate.py
# 功能：验证库外查询识别——RRF 前置门槛、门控两级决策、重写/联网分支
# 输入：合成候选与内存假集合；输出：断言结果（不加载模型、不联网）
from __future__ import annotations

import pytest

from src.rag.advanced_self_rag import AdvancedSelfRAGRecommender
from src.rag.rag_quality import RAGQualityChecker
from src.rag.self_rag_recommender import RAGState
from tests.fakes import make_resource, make_retriever

RESOURCES = [
    make_resource("py-video", "Python基础教程", "Python 变量 数据类型 控制流 函数 入门"),
    make_resource("ml-video", "机器学习入门", "机器学习 分类 回归 模型 训练"),
]


# ── 一、RRF 融合前的绝对门槛 ──

def test_rrf_skips_fusion_when_dense_has_no_absolute_hit():
    """语义侧全灭时应跳过融合返回空，并记录可诊断的原因"""
    retriever = make_retriever(RESOURCES)
    results = retriever.search("法学期末知识产权法条", top_k=5, mode="hybrid",
                               min_dense_similarity=0.25)
    assert results == []
    assert "dense" in retriever.last_no_hit_reason


def test_rrf_threshold_filters_low_candidates():
    """低于绝对门槛的候选不参与融合，高分候选仍可返回"""
    retriever = make_retriever(RESOURCES)
    results = retriever.search("Python 变量 数据类型 控制流 函数 入门",
                               top_k=5, mode="hybrid", min_dense_similarity=0.5)
    assert results
    # sparse-only 条目本来就没有真实余弦，只检查参与融合的 dense 命中条目
    dense_hits = [r for r in results if r.get("dense_similarity") is not None]
    assert dense_hits
    assert all(r["dense_similarity"] >= 0.5 for r in dense_hits)


def test_rrf_threshold_is_opt_in():
    """未传阈值时保持历史行为，评测链路不受影响"""
    retriever = make_retriever(RESOURCES)
    assert retriever.search("Python 教程", top_k=5, mode="hybrid")
    assert retriever.last_no_hit_reason == ""


# ── 二、质量门控的两级决策 ──

def _item(cosine: float, logit: float) -> dict:
    return {"dense_similarity": cosine, "rerank_score": logit,
            "resource_type": "视频教程"}


def test_both_signals_below_hard_line_decides_web():
    """两路绝对信号同时低于硬线 → 判知识库无覆盖，直接联网"""
    report = RAGQualityChecker().evaluate([_item(0.12, 0.09)])
    assert report["decision"] == "web"
    assert report["passed"] is False
    assert report["grade"] == "low"
    assert any("无覆盖" in issue for issue in report["issues"])


def test_single_weak_signal_decides_rewrite():
    """只有一路偏弱 → 判改写重试，而不是直接联网"""
    report = RAGQualityChecker().evaluate([_item(0.30, 0.55)])
    assert report["decision"] == "rewrite"
    assert report["passed"] is False
    assert any("改写" in issue for issue in report["issues"])


def test_both_signals_strong_decides_pass():
    """两路都过软线且总分达标 → 正常推荐"""
    report = RAGQualityChecker().evaluate([_item(0.45, 0.90)])
    assert report["decision"] == "pass"
    assert report["passed"] is True
    assert report["score"] >= 0.55


def test_no_candidates_decides_web():
    """RRF 跳过融合导致无候选时，也必须判直接联网"""
    report = RAGQualityChecker().evaluate([])
    assert report["decision"] == "web"
    assert report["score"] == 0.0


def test_legacy_candidates_without_absolute_signals_still_scored():
    """只有 sigmoid 置信度的旧候选仍按分数判定，不误判为 web"""
    report = RAGQualityChecker().evaluate([{"rerank_confidence": 0.9}])
    assert report["decision"] == "pass"
    assert report["passed"] is True


def test_metadata_match_no_longer_carries_the_gate():
    """元数据自证项不能再单独把明显不相关的结果送过门控"""
    weak = RAGQualityChecker().evaluate([_item(0.12, 0.09)],
                                        field="AI", level="beginner")
    assert weak["decision"] == "web"
    assert weak["score"] < 0.55


# ── 三、决策到处置动作的映射 ──

def _bare_recommender() -> AdvancedSelfRAGRecommender:
    """绕过 __init__ 构造推荐器，避免加载向量库与模型"""
    recommender = AdvancedSelfRAGRecommender.__new__(AdvancedSelfRAGRecommender)
    recommender.quality_checker = RAGQualityChecker()
    recommender.MAX_REWRITE_TIMES = 2
    return recommender


def _report(decision: str) -> dict:
    return {"score": 0.9 if decision == "pass" else 0.2,
            "grade": "high" if decision == "pass" else "low",
            "passed": decision == "pass", "decision": decision,
            "signals": {}, "issues": []}


@pytest.mark.parametrize("decision,expected", [
    ("pass", "sufficient"), ("rewrite", "insufficient"), ("web", "kb_empty"),
])
def test_evaluate_results_maps_decision(decision, expected):
    """pass→直接推荐，rewrite→改写，web→跳过改写直接联网"""
    state = RAGState(kb_results=[{"similarity": 0.5}])
    state.quality = _report(decision)
    assert _bare_recommender()._evaluate_results(state) == expected


def test_rewrite_exhaustion_falls_back_to_web():
    """改写次数用尽后不再无限重试，转联网兜底"""
    state = RAGState(kb_results=[{"similarity": 0.5}], rewrite_count=2)
    state.quality = _report("rewrite")
    assert _bare_recommender()._evaluate_results(state) == "kb_empty"


# ── 四、完整 recommend 流程（内部方法替换，不触网、不加载模型）──

class _StubReranker:
    def status(self):
        return {"enabled": True, "available": True, "model": "stub", "min_confidence": 0.0}


class _SpyWeb:
    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def status(self):
        return {"available": True, "reason": "", "enabled": True,
                "api_key_configured": True, "channel": "spy", "last_error": ""}

    def search_learning_resources(self, **kwargs):
        self.calls += 1
        return [{"title": "联网资源", "description": "库外主题",
                 "resource_type": "视频教程", "url": "https://example.com/web"}]


def _mock_search_kb(monkeypatch, recommender, decisions):
    """让 _search_kb 按预设 decision 序列返回构造好的状态"""
    queue = list(decisions)

    def fake(state):
        decision = queue.pop(0) if len(queue) > 1 else queue[0]
        state.decision = decision
        state.quality = _report(decision)
        state.kb_results = [{
            "id": "kb-irrelevant", "title": "库内不相关资源",
            "similarity": 0.05, "dense_similarity": 0.05,
            "rerank_score": 0.01, "resource_type": "视频教程",
            "level": "beginner", "description": "x", "url": "https://example.com/kb",
        }]
        state.kb_relevance_score = state.quality["score"]
        state.candidate_count = 1
        state.rerank_used = True
        state.filters = {}
        state.search_query = "q"
        state.no_hit_reason = ""
        return state

    monkeypatch.setattr(recommender, "_search_kb", fake)


def test_web_branch_drops_kb_results_without_rewriting(monkeypatch):
    """web 决策：不改写、清空不相关 KB 结果、直接联网"""
    recommender = _bare_recommender()
    recommender.reranker = _StubReranker()
    recommender.web_search = _SpyWeb()
    _mock_search_kb(monkeypatch, recommender, ["web"])

    result = recommender.recommend("两周备考期末知识产权法")
    assert result["decision"] == "web"
    assert result["rewrite_count"] == 0
    assert result["used_web_search"] is True
    assert recommender.web_search.calls == 1
    assert all(r["source"] != "knowledge_base" for r in result["resources"])


def test_rewrite_branch_retries_then_falls_back_to_web(monkeypatch):
    """rewrite 决策：最多改写 2 次，仍不达标后联网兜底"""
    recommender = _bare_recommender()
    recommender.reranker = _StubReranker()
    recommender.web_search = _SpyWeb()
    _mock_search_kb(monkeypatch, recommender, ["rewrite"])

    result = recommender.recommend("表达含糊的库内查询")
    assert result["rewrite_count"] == 2
    assert result["used_web_search"] is True
    assert recommender.web_search.calls == 1
