# 文件：tests/test_search_pipeline.py
# 功能：用内存假集合验证检索主链路的过滤、缓存、去重与数量控制
# 输入：无；输出：断言结果

from __future__ import annotations

import pytest

from tests.fakes import make_resource, make_retriever, make_store

RESOURCES = [
    make_resource("py-video", "Python基础教程", "Python 变量 数据类型 控制流 函数 入门",
                  field="编程", level="beginner", resource_type="视频教程"),
    make_resource("py-doc", "Python官方教程", "Python 官方 语法 数据结构 模块 错误处理",
                  field="编程", level="beginner", resource_type="文档资料"),
    make_resource("py-adv", "Python语言参考", "Python 描述符 元类 生成器 高级 语义",
                  field="编程", level="advanced", resource_type="文档资料"),
    make_resource("ml-video", "机器学习入门", "机器学习 入门 分类 回归 模型 训练",
                  field="AI", level="beginner", resource_type="视频教程"),
    make_resource("ml-doc", "机器学习文档", "机器学习 模型 评估 调参 交叉验证",
                  field="AI", level="intermediate", resource_type="文档资料"),
]


@pytest.fixture()
def retriever():
    """每个用例拿到独立的内存检索器（内含一个独立的假向量库）"""
    return make_retriever(RESOURCES)


def test_level_filter_applies_to_dense_channel(retriever):
    """难度过滤应剔除 level 不匹配的资源"""
    results = retriever.search("Python 教程", level="beginner", top_k=10, mode="dense")
    assert results
    assert all(item["level"] == "beginner" for item in results)


def test_field_filter_applies_to_sparse_channel(retriever):
    """BM25 通路同样要遵守领域过滤，这是修复前的实际缺陷"""
    results = retriever.search("机器学习 模型", field="AI", top_k=10, mode="sparse")
    assert results
    assert all(item["field"] == "AI" for item in results)


def test_resource_type_filter_applies_to_both_channels(retriever):
    """资源类型过滤在 dense 和 hybrid 两条链路上都必须生效"""
    for mode in ("dense", "sparse", "hybrid"):
        results = retriever.search("Python 教程", resource_types=["文档资料"], top_k=10, mode=mode)
        assert results, f"{mode} 未返回结果"
        assert all(item["resource_type"] == "文档资料" for item in results), f"{mode} 过滤失效"


def test_hybrid_respects_all_filters(retriever):
    """混合检索的最终结果同时满足领域、难度和类型约束"""
    results = retriever.search("Python 教程", field="编程", level="beginner",
                           resource_types=["视频教程"], top_k=10, mode="hybrid")
    assert len(results) == 1
    assert results[0]["id"] == "py-video"


def test_hybrid_annotates_scores(retriever):
    """混合结果应带融合分数和两条通路的排名"""
    results = retriever.search("机器学习 模型 评估", top_k=5, mode="hybrid")
    assert results
    for item in results:
        assert "fused_score" in item
        assert "rank_dense" in item and "rank_sparse" in item


def test_top_k_is_respected(retriever):
    """返回数量不得超过 top_k"""
    assert len(retriever.search("Python 机器学习", top_k=2, mode="hybrid")) <= 2


def test_query_cache_avoids_second_dense_call(retriever):
    """相同查询第二次应命中缓存，不再触发向量检索"""
    retriever.search("Python 教程", top_k=3, mode="hybrid")
    dense_after_first = retriever._stats["dense_calls"]
    retriever.search("Python 教程", top_k=3, mode="hybrid")
    assert retriever._stats["dense_calls"] == dense_after_first
    assert retriever._stats["cache_hits"] == 1


def test_cache_isolated_by_filter(retriever):
    """过滤条件不同属于不同缓存条目，不能互相串结果"""
    beginner = retriever.search("Python", level="beginner", top_k=10, mode="dense")
    advanced = retriever.search("Python", level="advanced", top_k=10, mode="dense")
    assert {r["level"] for r in beginner} == {"beginner"}
    assert {r["level"] for r in advanced} == {"advanced"}


def test_write_invalidates_cache(retriever):
    """写入后缓存必须失效，否则会返回过期结果。

    失效机制是「数据版本号」：缓存键里带 store.data_version，
    写库自增后旧键不再命中（缓存条目本身留给 LRU 淘汰，不再主动清空）。
    """
    retriever.search("Python 教程", top_k=3, mode="hybrid")
    version_before = retriever.store.data_version

    retriever.store.add_resources_batch([make_resource(
        "new-doc", "Python异步编程", "Python 异步 协程 事件循环 教程",
        field="编程", level="beginner", resource_type="文档资料")])

    assert retriever.store.data_version > version_before
    results = retriever.search("Python 异步 协程", top_k=5, mode="hybrid")
    assert any(item["id"] == "new-doc" for item in results)


def test_description_does_not_repeat_title(retriever):
    """检索结果的描述不应以标题开头重复一遍"""
    results = retriever.search("Python 变量", top_k=5, mode="dense")
    for item in results:
        assert not item["description"].startswith(item["title"] + "\n")


def test_min_types_increases_type_diversity(retriever):
    """开启类型多样性后，结果覆盖的资源类型数应不少于未开启时"""
    plain = retriever.search("教程", top_k=2, mode="dense")
    diverse = retriever.search("教程", top_k=2, mode="dense", min_types=2)
    assert len({r["resource_type"] for r in diverse}) >= len({r["resource_type"] for r in plain})
    assert diverse[0]["id"] == plain[0]["id"]


def test_empty_query_returns_nothing(retriever):
    """空查询直接返回空列表，不浪费一次编码"""
    assert retriever.search("", top_k=3) == []


def test_where_clause_builder_nests_conditions():
    """多个过滤条件应组合成 $and，单个条件直接平铺"""
    from src.memory.vector_store_core import VectorStoreManager

    store = make_store([])
    assert store._build_where(None, None, None) == {}
    assert store._build_where("AI", None, None) == {"field": "AI"}
    combined = store._build_where("AI", "beginner", ["视频教程"])
    assert "$and" in combined and len(combined["$and"]) == 3
    assert VectorStoreManager is not None
