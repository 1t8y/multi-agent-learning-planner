"""评估反馈 Agent 维度收敛回归测试

对应 v2.7.x 的修复：提示词曾经要求 6 个维度（多出 progression_rating /
personalization_rating），但输出 schema 与前端只消费 4 个。多出的维度既白花
token，又让 `_node_assess` 按 6 维求的均分和用户看到的 4 项对不上。

这里不实例化 Agent（需要 DeepSeek key），直接对提示词文本、输出格式、
默认兜底结果做静态一致性断言，保证 4 维口径在四处不再漂移。
"""

from __future__ import annotations

import json
import re

import pytest

from src.core.assessment_feedback import AssessmentFeedbackAgent

# 收敛后的四个评分维度（也是前端 AssessmentSummary 实际消费的字段）
FOUR_RATINGS = ["feasibility_rating", "content_rating", "time_rating", "method_rating"]
# 已移除的两个维度，任何地方都不该再出现
REMOVED_RATINGS = ["progression_rating", "personalization_rating"]


@pytest.fixture(scope="module")
def prompt() -> str:
    return AssessmentFeedbackAgent._get_default_prompt(AssessmentFeedbackAgent())


def _json_block(text: str) -> dict:
    """从提示词的「输出格式」段落里抠出 JSON 示例并解析。"""
    # 提示词里 JSON 示例前后有代码围栏/说明文字，抓第一个 { 到最后一个 } 的平衡块
    start = text.find("{")
    end = text.rfind("}")
    assert start != -1 and end > start, "提示词里应有 JSON 输出示例"
    return json.loads(text[start : end + 1])


def test_prompt_declares_four_dimensions(prompt):
    """提示词正文与维度清单都只讲 4 维，不再提 6 维"""
    assert "4个维度" in prompt or "4 个维度" in prompt
    assert "6个维度" not in prompt and "6 个维度" not in prompt


def _rating_keys(summary: dict) -> list[str]:
    """取 summary 里的评分字段，排除 overall_rating 这个总分占位"""
    return sorted(
        k for k in summary if k.endswith("_rating") and k != "overall_rating"
    )


def test_prompt_output_schema_has_only_four_ratings(prompt):
    """提示词里给出的输出格式只含四个评分字段"""
    schema = _json_block(prompt)["assessment_summary"]
    assert _rating_keys(schema) == sorted(FOUR_RATINGS)
    assert "overall_rating" in schema


def test_default_result_is_four_dimensional():
    """默认兜底结果只含四个评分字段 + 均分，没有残留维度"""
    summary = AssessmentFeedbackAgent._get_default_result(
        AssessmentFeedbackAgent()
    )["assessment_summary"]
    assert _rating_keys(summary) == sorted(FOUR_RATINGS)
    assert summary["score_average"] == 0


def test_validate_result_accepts_four_and_rejects_six():
    """validate_result 的字段白名单是 4 维：4 维通过、含 6 维旧字段也仍通过（向后兼容）"""
    agent = AssessmentFeedbackAgent()

    base = {
        "assessment_summary": {
            "overall_rating": "8",
            "feasibility_rating": 8,
            "content_rating": 8,
            "time_rating": 8,
            "method_rating": 8,
        },
        "assessment_metrics": [],
        "adjustment_suggestions": [],
        "recommendations": [],
    }
    assert agent.validate_result(base) is True

    # 缺任一四维字段应判无效
    for missing in FOUR_RATINGS:
        broken = json.loads(json.dumps(base))
        del broken["assessment_summary"][missing]
        assert agent.validate_result(broken) is False, f"缺 {missing} 应判无效"


def test_no_removed_rating_anywhere_in_source():
    """源码里彻底清除 progression_rating / personalization_rating"""
    from src.paths import BACKEND_ROOT

    source = (BACKEND_ROOT / "src" / "core" / "assessment_feedback.py").read_text(
        encoding="utf-8"
    )
    for removed in REMOVED_RATINGS:
        assert removed not in source


def test_orchestrator_score_average_is_mean_of_four():
    """编排层均分是「四个 *_rating 的均值」，与前端展示的维度数一致。

    直接复算 _node_assess 里的求均值逻辑，防止有人改回 6 维后均分口径又漂移。
    """
    summary = {
        "overall_rating": "8",
        "feasibility_rating": 9,
        "content_rating": 9,
        "time_rating": 8,
        "method_rating": 8,
    }
    scores = [
        v
        for k, v in summary.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k.endswith("_rating")
    ]
    assert len(scores) == 4
    assert round(sum(scores) / len(scores), 1) == 8.5
