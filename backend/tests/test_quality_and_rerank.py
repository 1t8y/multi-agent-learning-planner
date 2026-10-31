# 文件：tests/test_quality_and_rerank.py
# 功能：验证运行时质量检测的评分逻辑和 Cross-Encoder 的降级行为
# 输入：合成候选；输出：断言结果

from __future__ import annotations

import pytest

from rag_quality import RAGQualityChecker
from reranker import ResourceReranker


def _candidate(confidence: float, resource_type: str = "视频教程",
               field: str = "AI", level: str = "beginner") -> dict:
    """构造一条带重排置信度的候选"""
    return {"id": str(confidence), "title": "t", "rerank_confidence": confidence,
            "resource_type": resource_type, "field": field, "level": level}


def test_empty_results_fail_quality_gate():
    """没有候选时质量门控必须判定失败并给出归因"""
    report = RAGQualityChecker().evaluate([])
    assert report["passed"] is False
    assert report["score"] == 0.0
    assert report["issues"]


def test_high_confidence_results_pass():
    """高置信度且元数据匹配时应通过质量门控"""
    results = [_candidate(0.9), _candidate(0.8), _candidate(0.85)]
    report = RAGQualityChecker(threshold=0.55).evaluate(results, field="AI", level="beginner")
    assert report["passed"] is True
    assert report["grade"] == "high"


def test_low_confidence_results_are_rejected():
    """整体置信度偏低时应判为不通过并给出问题说明"""
    results = [_candidate(0.2), _candidate(0.15)]
    report = RAGQualityChecker(threshold=0.55).evaluate(results)
    assert report["passed"] is False
    assert any("置信度" in issue for issue in report["issues"])


def test_metadata_mismatch_lowers_score():
    """元数据不匹配会拉低总分，这是过滤失效时的兜底信号"""
    matched = [_candidate(0.8, field="AI")]
    mismatched = [_candidate(0.8, field="数学")]
    good = RAGQualityChecker().evaluate(matched, field="AI")
    bad = RAGQualityChecker().evaluate(mismatched, field="AI")
    assert bad["score"] < good["score"]
    assert bad["signals"]["metadata_match_ratio"] == 0.0


def test_single_type_reported_as_low_diversity():
    """候选资源类型单一时应给出多样性告警"""
    results = [_candidate(0.7), _candidate(0.7)]
    report = RAGQualityChecker().evaluate(results)
    assert report["signals"]["resource_type_diversity"] == 1
    assert any("单一" in issue for issue in report["issues"])


def test_threshold_is_configurable():
    """同一批候选在不同阈值下通过情况应不同"""
    results = [_candidate(0.6)]
    assert RAGQualityChecker(threshold=0.5).evaluate(results)["passed"] is True
    assert RAGQualityChecker(threshold=0.95).evaluate(results)["passed"] is False


def test_falls_back_to_similarity_when_no_rerank_score():
    """没有重排分数时，质量检测应回退使用 similarity"""
    report = RAGQualityChecker().evaluate([{"similarity": 0.9, "resource_type": "文档资料"}])
    assert report["signals"]["top_confidence"] == 0.9


def test_reranker_disabled_keeps_original_order():
    """关闭重排时应原样返回候选顺序，且标记为不可用"""
    reranker = ResourceReranker(enabled=False)
    candidates = [{"id": "a", "title": "a", "description": "x"},
                  {"id": "b", "title": "b", "description": "y"}]
    assert [r["id"] for r in reranker.rerank("q", candidates, top_k=2)] == ["a", "b"]
    assert reranker.status()["available"] is False


def test_reranker_empty_input_is_safe():
    """空候选直接返回空列表，不触发模型加载"""
    assert ResourceReranker().rerank("q", [], top_k=5) == []


def test_reranker_degrades_when_model_unavailable(monkeypatch):
    """模型加载失败时必须降级为原排序，不能抛异常中断整条链路"""
    import reranker as reranker_module

    def boom(_name):
        raise RuntimeError("模型不可用")

    monkeypatch.setattr(reranker_module, "get_cross_encoder", boom, raising=False)
    reranker = ResourceReranker(model_name="bad-model")
    candidates = [{"id": "a", "title": "a", "description": "x"}]
    out = reranker.rerank("q", candidates, top_k=1)
    assert out[0]["id"] == "a"
    assert reranker.status()["available"] is False


def test_embedding_function_exposes_chroma_entrypoints():
    """Chroma 查询路径依赖 embed_query，缺失会导致稠密检索静默失败"""
    from vector_store_core import BGEEmbeddingFunction

    assert hasattr(BGEEmbeddingFunction, "embed_query")
    assert hasattr(BGEEmbeddingFunction, "embed_documents")
    assert hasattr(BGEEmbeddingFunction, "__call__")


class _StubModel:
    """固定输出的假 Cross-Encoder，用于离线验证门控逻辑"""

    def __init__(self, scores):
        self.scores = scores

    def predict(self, pairs, convert_to_numpy=True):
        """返回预设分数，忽略输入"""
        return self.scores


def _stub_reranker(scores, min_confidence):
    """构造一个已就绪、模型被替换成固定分数的重排器"""
    reranker = ResourceReranker(min_confidence=min_confidence)
    reranker._model = _StubModel(scores)
    reranker._load_attempted = True
    return reranker


def test_rerank_gate_keeps_fusion_order_when_confidence_low():
    """首位置信度低于门控阈值时，应保留融合顺序且仍回填重排分数"""
    candidates = [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}, {"id": "c", "title": "c"}]
    # 原始分都很低，sigmoid 后约 0.05~0.12，低于 0.55 阈值
    reranker = _stub_reranker([-3.0, -2.5, -2.0], min_confidence=0.55)
    out = reranker.rerank("q", candidates, top_k=3)
    assert [r["id"] for r in out] == ["a", "b", "c"]
    assert reranker.last_gate_fallback is True
    assert all("rerank_confidence" in r for r in out)


def test_rerank_gate_reorders_when_confidence_high():
    """首位置信度达标时正常重排，不做回退"""
    candidates = [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}]
    reranker = _stub_reranker([-2.0, 3.0], min_confidence=0.55)
    out = reranker.rerank("q", candidates, top_k=2)
    assert [r["id"] for r in out] == ["b", "a"]
    assert reranker.last_gate_fallback is False


def test_rerank_gate_disabled_by_default():
    """默认阈值为 0 时不门控，保持与历史行为一致"""
    candidates = [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}]
    reranker = _stub_reranker([-5.0, 0.0], min_confidence=0.0)
    out = reranker.rerank("q", candidates, top_k=2)
    assert [r["id"] for r in out] == ["b", "a"]
    assert reranker.last_gate_fallback is False
    assert ResourceReranker().min_confidence == 0.0
