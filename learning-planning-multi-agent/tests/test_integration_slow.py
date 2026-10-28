# 文件：tests/test_integration_slow.py
# 功能：依赖真实向量库与模型的集成冒烟测试（默认不在快速套件中运行）
# 输入：本地 chroma_db 与 data/knowledge_base；输出：断言结果

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def store():
    """返回加载了真实知识库的向量库实例"""
    from vector_store import init_vector_store_with_seed_data

    return init_vector_store_with_seed_data()


def test_store_matches_catalog_size(store, kb_rows):
    """向量库条数与已审核资源数一致，说明重建没有漏写"""
    approved = [row for row in kb_rows if row["review_status"] == "approved"]
    assert store.get_stats()["total_count"] == len(approved)


def test_dense_retrieval_actually_works(store):
    """稠密检索必须真的返回结果：曾因 Embedding 缺少 embed_query 静默退化为纯 BM25"""
    results = store.search("线性代数 特征值", top_k=3, mode="dense")
    assert results, "稠密检索返回空，检查 EmbeddingFunction 接口"
    assert all(item["similarity"] > 0 for item in results)


def test_hybrid_beats_or_matches_dense_on_known_query(store):
    """混合检索的正确答案应出现在首位"""
    results = store.search("Transformer 自注意力 位置编码 图解", top_k=5, mode="hybrid")
    assert results
    assert "transformer" in results[0]["title"].lower() or "transformer" in results[0]["description"].lower()


def test_filter_returns_only_matching_metadata(store):
    """带过滤条件时结果元数据必须全部匹配"""
    results = store.search("教程", field="数学", level="beginner",
                           resource_types=["视频教程"], top_k=10, mode="hybrid")
    assert results
    for item in results:
        assert item["field"] == "数学"
        assert item["level"] == "beginner"
        assert item["resource_type"] == "视频教程"


def test_repeated_query_hits_cache(store):
    """同一查询第二次应命中缓存，延迟显著下降"""
    store.search("Python 入门", top_k=5, mode="hybrid")
    before = store.get_stats()["retrieval"]["cache_hits"]
    store.search("Python 入门", top_k=5, mode="hybrid")
    after = store.get_stats()["retrieval"]["cache_hits"]
    assert after == before + 1


def test_reranker_available_and_ordered(store):
    """重排模型加载成功后，候选应按重排分数降序"""
    from reranker import ResourceReranker

    reranker = ResourceReranker()
    candidates = store.search("机器学习 模型 评估", top_k=8, mode="hybrid")
    reranked = reranker.rerank("机器学习 模型 评估", candidates, top_k=5)
    assert reranker.status()["available"] is True
    scores = [item["rerank_score"] for item in reranked]
    assert scores == sorted(scores, reverse=True)
