# 文件：rag_quality.py
# 功能：对运行时 RAG 检索结果做质量检测和问题归因
# 输入：查询、候选资源和过滤条件；输出：质量分、等级、信号和问题列表
from __future__ import annotations

from statistics import mean
from typing import Any


class RAGQualityChecker:
    """基于重排置信度、证据一致性和元数据匹配的运行时质量门控"""

    def __init__(self, threshold: float = 0.55):
        """输入通过阈值，初始化质量检测器"""
        self.threshold = threshold

    def _score(self, item: dict[str, Any]) -> float:
        """输入单条资源，返回 0 到 1 的证据置信度"""
        value = item.get("rerank_confidence", item.get("similarity", 0.0))
        return max(0.0, min(float(value or 0.0), 1.0))

    def evaluate(self, results: list[dict[str, Any]], field: str | None = None,
                 level: str | None = None, resource_types: list[str] | None = None) -> dict[str, Any]:
        """输入候选资源和过滤条件，返回质量报告"""
        if not results:
            return {"score": 0.0, "grade": "low", "passed": False,
                    "signals": {}, "issues": ["知识库未返回候选资源"]}

        scores = [self._score(item) for item in results]
        top_score, avg_score = max(scores), mean(scores)
        checks = []
        if field:
            checks.extend(item.get("field") == field for item in results)
        if level:
            checks.extend(item.get("level") == level for item in results)
        if resource_types:
            checks.extend(item.get("resource_type") in resource_types for item in results)
        match_ratio = sum(checks) / len(checks) if checks else 1.0
        diversity = len({item.get("resource_type", "") for item in results})
        quality_score = round(0.55 * top_score + 0.25 * avg_score + 0.20 * match_ratio, 4)

        issues = []
        if top_score < 0.55:
            issues.append("最高相关资源置信度偏低")
        if avg_score < 0.40:
            issues.append("候选资源整体相关性偏低")
        if match_ratio < 0.70:
            issues.append("领域、难度或资源类型匹配不足")
        if diversity <= 1 and len(results) > 1:
            issues.append("候选资源类型过于单一")

        grade = "high" if quality_score >= 0.72 else "medium" if quality_score >= self.threshold else "low"
        return {
            "score": quality_score,
            "grade": grade,
            "passed": quality_score >= self.threshold,
            "signals": {
                "top_confidence": round(top_score, 4),
                "average_confidence": round(avg_score, 4),
                "metadata_match_ratio": round(match_ratio, 4),
                "resource_type_diversity": diversity,
                "candidate_count": len(results),
            },
            "issues": issues,
        }
