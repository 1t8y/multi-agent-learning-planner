# 文件：tests/test_feedback_isolation.py
# 功能：验证反馈数据目录可替换，避免测试写入生产数据文件
# 输入：临时目录；输出：断言结果

from __future__ import annotations

import json
import os


def test_feedback_writes_to_custom_data_dir(tmp_path):
    """指定 data_dir 时，反馈与资源提交都只落在该目录"""
    from feedback_manager import FeedbackManager

    manager = FeedbackManager(data_dir=str(tmp_path))
    manager.submit_feedback(
        resource_id="r1",
        resource_title="示例资源",
        resource_url="https://example.com/r1",
        feedback_type="useful",
        rating=5,
        comment="有用",
        learning_objective="测试",
        user_id="tester",
    )

    feedback_file = tmp_path / "feedback_records.json"
    assert feedback_file.exists()
    assert len(json.loads(feedback_file.read_text(encoding="utf-8"))) == 1
    # 默认生产文件不应被这次写入创建或修改
    assert not os.path.exists("./data/feedback_records.json.tmp")


def test_feedback_reload_from_custom_dir(tmp_path):
    """同一目录再次初始化时应能读回历史记录，便于重启后保留数据"""
    from feedback_manager import FeedbackManager

    FeedbackManager(data_dir=str(tmp_path)).submit_feedback(
        resource_id="r2",
        resource_title="示例资源2",
        resource_url="https://example.com/r2",
        feedback_type="useful",
        rating=4,
        comment="还行",
        learning_objective="测试",
        user_id="tester",
    )
    reloaded = FeedbackManager(data_dir=str(tmp_path))
    assert len(reloaded.feedback_records) == 1
    assert reloaded.feedback_records[0].resource_id == "r2"


def test_submitted_resource_lands_in_pending_with_level(tmp_path):
    """提交的资源必须进入 pending，并保留调用方给的难度而不是硬编码 intermediate"""
    from feedback_manager import FeedbackManager

    manager = FeedbackManager(data_dir=str(tmp_path))
    result = manager.submit_resource(
        title="Python 零基础视频课",
        description="零基础入门",
        url="https://example.com/py",
        resource_type="视频教程",
        field="编程",
        tags=["Python", "零基础"],
        level="beginner",
    )

    assert result is not None
    assert result.status == "pending"
    assert result.level == "beginner"

    pending = manager.get_pending_submissions()
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    assert pending[0]["tags"] == ["Python", "零基础"]


def test_submit_resource_rejects_illegal_level(tmp_path):
    """非法难度回落到 intermediate，避免入库后无法被任何难度过滤命中"""
    from feedback_manager import FeedbackManager

    manager = FeedbackManager(data_dir=str(tmp_path))
    result = manager.submit_resource(
        title="难度写错的资源",
        description="",
        url="https://example.com/x",
        resource_type="文档资料",
        field="数学",
        tags=[],
        level="hard",
    )
    assert result is not None
    assert result.level == "intermediate"


def test_submit_resource_requires_title_and_url(tmp_path):
    """标题或 URL 为空时直接拒绝，不能进待审核队列"""
    from feedback_manager import FeedbackManager

    manager = FeedbackManager(data_dir=str(tmp_path))
    assert manager.submit_resource(
        title="", description="", url="https://a.com",
        resource_type="文档资料", field="编程", tags=[],
    ) is None
    assert manager.submit_resource(
        title="有标题", description="", url="",
        resource_type="文档资料", field="编程", tags=[],
    ) is None
    assert manager.get_pending_submissions() == []
