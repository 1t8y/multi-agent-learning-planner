# 文件：tests/test_feedback_loop.py
# 功能：验证反馈闭环的三个后端环节——资源 id 透传、单资源统计读取、反馈写入后统计变化
# 输入：假集合（tests/fakes.py）；输出：断言结果

from __future__ import annotations

from tests.fakes import make_resource, make_store


def _resources() -> list[dict]:
    """构造两条带反馈历史的知识库资源"""
    return [
        make_resource("kb-001", "Python基础教程", "零基础 Python 视频教程", field="编程"),
        make_resource("kb-002", "线性代数", "线性代数与矩阵", field="数学"),
    ]


def test_search_result_carries_feedback_count():
    """检索结果必须带 feedback_count，否则卡片刷新后无法展示反馈条数"""
    store = make_store(_resources())
    results = store.search("Python 教程", top_k=2, mode="dense")
    assert results
    assert all("feedback_count" in item for item in results)
    assert all(isinstance(item["feedback_count"], int) for item in results)


def test_get_resource_stats_returns_current_values():
    """读单资源统计：初始为 0，写入反馈后应反映最新均值与条数"""
    store = make_store(_resources())
    before = store.get_resource_stats("kb-001")
    assert before is not None
    assert before["rating"] == 0.0
    assert before["feedback_count"] == 0

    assert store.update_feedback("kb-001", 5) is True
    assert store.update_feedback("kb-001", 3) is True

    after = store.get_resource_stats("kb-001")
    assert after["feedback_count"] == 2
    assert after["rating"] == 4.0  # (5 + 3) / 2


def test_get_resource_stats_missing_returns_none():
    """不存在的资源返回 None，由 API 层映射成 404"""
    store = make_store(_resources())
    assert store.get_resource_stats("ghost") is None
    assert store.get_resource_stats("") is None


def test_merge_and_select_passes_resource_id():
    """
    资源合成阶段必须把知识库 id 透传给前端。

    历史缺陷：这里只复制标题/描述，id 丢失后前端只能造 resource_0 这种假 id，
    后端 update_feedback 找不到资源，评分永远不更新。
    """
    from self_rag_recommender import RAGState, SelfRAGRecommender

    recommender = object.__new__(SelfRAGRecommender)
    recommender.MIN_KB_SIMILARITY = 0.15

    state = RAGState(
        learning_objective="学习 Python",
        kb_results=[
            {
                "id": "kb-001",
                "title": "Python基础教程",
                "description": "零基础教程",
                "resource_type": "视频教程",
                "level": "beginner",
                "url": "https://example.com/kb-001",
                "similarity": 0.8,
                "rating": 4.5,
                "feedback_count": 3,
            }
        ],
        web_results=[],
    )

    merged = recommender._merge_and_select(state)
    assert merged.final_resources
    first = merged.final_resources[0]
    assert first["id"] == "kb-001"
    assert first["rating"] == 4.5
    assert first["feedback_count"] == 3


def test_merge_and_select_drops_low_similarity():
    """相似度低于阈值的知识库结果不应进入最终列表（保护既有行为）"""
    from self_rag_recommender import RAGState, SelfRAGRecommender

    recommender = object.__new__(SelfRAGRecommender)
    recommender.MIN_KB_SIMILARITY = 0.5

    state = RAGState(
        learning_objective="学习 Python",
        kb_results=[
            {"id": "kb-002", "title": "无关资源", "description": "", "similarity": 0.1,
             "url": "https://example.com/x", "resource_type": "文档资料", "level": "beginner"},
        ],
        web_results=[],
    )

    assert recommender._merge_and_select(state).final_resources == []
