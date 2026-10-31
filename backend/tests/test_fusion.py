# 文件：tests/test_fusion.py
# 功能：验证 RRF 融合、去重、多样性和文档解析的数学性质
# 输入：合成候选列表；输出：断言结果

from __future__ import annotations

from collections import OrderedDict

from vector_store_core import VectorStoreManager
from tests.fakes import make_store


def _stub() -> VectorStoreManager:
    """返回只用于调用纯函数方法的空实例"""
    return make_store([])


def _item(rid: str, similarity: float = 0.5, bm25: float | None = None) -> dict:
    """构造一条候选结果"""
    item = {"id": rid, "title": rid, "similarity": similarity,
            "resource_type": "视频教程", "url": f"https://example.com/{rid}"}
    if bm25 is not None:
        item["bm25_score"] = bm25
    return item


def test_rrf_formula_matches_definition():
    """两路都命中的文档，融合分数应等于两条倒数排名之和"""
    store = _stub()
    dense = [_item("a", 0.9)]
    sparse = [_item("a", bm25=8.0)]
    merged = store._rrf_merge(dense, sparse, top_k=5)
    expected = 2 * (1.0 / (store.RRF_K + 1))
    assert len(merged) == 1
    assert abs(merged[0]["fused_score"] - expected) < 1e-6


def test_rrf_prefers_document_hit_by_both_channels():
    """同时被两个通道命中的文档，应排在只被单通道命中的文档之前"""
    store = _stub()
    dense = [_item("only_dense", 0.95), _item("both", 0.60)]
    sparse = [_item("both", bm25=9.0), _item("only_sparse", bm25=1.0)]
    merged = store._rrf_merge(dense, sparse, top_k=5)
    assert merged[0]["id"] == "both"
    assert [m["id"] for m in merged].count("both") == 1


def test_rrf_keeps_original_scores():
    """融合不得覆盖原始 cosine 相似度与 BM25 分数"""
    store = _stub()
    merged = store._rrf_merge([_item("a", 0.87), _item("b", 0.42)],
                              [_item("b", bm25=7.5)], top_k=5)
    by_id = {m["id"]: m for m in merged}
    assert by_id["a"]["similarity"] == 0.87
    assert by_id["b"]["similarity"] == 0.42
    assert by_id["b"]["bm25_score"] == 7.5
    assert by_id["b"]["fused_score"] != by_id["b"]["similarity"]


def test_rrf_records_channel_ranks():
    """融合结果应记录两条通路各自的原始排名，便于归因"""
    store = _stub()
    merged = store._rrf_merge([_item("a"), _item("b")], [_item("b"), _item("c")], top_k=5)
    by_id = {m["id"]: m for m in merged}
    assert by_id["a"]["rank_dense"] == 1 and by_id["a"]["rank_sparse"] is None
    assert by_id["b"]["rank_dense"] == 2 and by_id["b"]["rank_sparse"] == 1
    assert by_id["c"]["rank_dense"] is None and by_id["c"]["rank_sparse"] == 2


def test_rrf_weight_controls_channel_priority():
    """调高 sparse 权重后，只看 sparse 命中的文档应排到前面"""
    store = _stub()
    dense = [_item("a"), _item("b")]
    sparse = [_item("c", bm25=10.0)]
    store.RRF_SPARSE_WEIGHT = 3.0
    merged = store._rrf_merge(dense, sparse, top_k=5)
    assert merged[0]["id"] == "c"


def test_sparse_only_result_gets_normalized_similarity():
    """仅在稀疏通路命中的文档，similarity 应按批次最大值归一到 0 到 1"""
    store = _stub()
    merged = store._rrf_merge([], [_item("a", bm25=10.0), _item("b", bm25=5.0)], top_k=5)
    by_id = {m["id"]: m for m in merged}
    assert by_id["a"]["similarity"] == 1.0
    assert by_id["b"]["similarity"] == 0.5


def test_dedupe_by_url_keeps_first():
    """同一 URL 的重复资源只保留排名更靠前的一条"""
    results = [
        {"id": "1", "url": "https://x/a", "title": "A"},
        {"id": "2", "url": "https://x/a", "title": "A副本"},
        {"id": "3", "url": "https://x/b", "title": "B"},
    ]
    unique = VectorStoreManager._dedupe(results)
    assert [r["id"] for r in unique] == ["1", "3"]


def test_dedupe_falls_back_to_title_when_url_missing():
    """URL 为空时按标题去重，且丢弃既无 URL 又无标题的空记录"""
    results = [
        {"id": "1", "url": "", "title": "同名"},
        {"id": "2", "url": "", "title": "同名"},
        {"id": "3", "url": "", "title": ""},
    ]
    assert [r["id"] for r in VectorStoreManager._dedupe(results)] == ["1"]


def test_diversify_keeps_first_and_adds_types():
    """多样性约束不改变首位，但应把不同类型的资源提前"""
    results = [
        {"id": "1", "resource_type": "视频教程"},
        {"id": "2", "resource_type": "视频教程"},
        {"id": "3", "resource_type": "文档资料"},
        {"id": "4", "resource_type": "实战项目"},
    ]
    out = VectorStoreManager._diversify(results, min_types=2)
    assert out[0]["id"] == "1"
    assert len(out) == 4
    assert out[1]["id"] == "3"


def test_diversify_noop_when_too_few_results():
    """结果数量不足以调整时保持原样"""
    results = [{"id": "1", "resource_type": "视频教程"}]
    assert VectorStoreManager._diversify(results, min_types=3) == results


def test_strip_title_removes_duplicated_title():
    """入库文档是「标题\\n描述」，取出时不应把标题重复拼进描述"""
    assert VectorStoreManager._strip_title("Python基础教程\n讲变量和函数", "Python基础教程") == "讲变量和函数"
    assert VectorStoreManager._strip_title("无前缀正文", "别的标题") == "无前缀正文"
    assert VectorStoreManager._strip_title("", "标题") == ""
