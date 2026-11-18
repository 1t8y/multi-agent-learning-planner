# 文件：src/rag/rag_quality.py
# 功能：对运行时 RAG 检索结果做绝对相关性门控与处置决策
# 输入：候选资源和过滤条件；输出：质量分、等级、决策（pass/rewrite/web）和问题列表
from __future__ import annotations

from statistics import mean
from typing import Any, Optional

# 绝对相关性校准区间：把原始信号线性映射到 0~1。
# 标定依据（2026-11-12，10 个库内场景 / 6 个库外查询）：
#   dense top1 cosine  库内 0.2944~0.5944   库外 -0.0631~0.2184
#   rerank top1 logit  库内 0.800~0.992     库外 0.004~0.281
# 旧实现用 sigmoid(rerank logit) 当置信度：logit=0 就白给 0.5，
# 再加上元数据自证项白送 0.20，库外查询因此能稳定拿到 0.60+ 并通过门控。
COSINE_FLOOR = 0.10   # 低于此值视为语义完全未命中
COSINE_FULL = 0.50    # 达到此值视为语义强命中
LOGIT_FULL = 1.00     # 达到此值视为重排强命中


def _clamp(value: float) -> float:
    """把数值截断到 0~1"""
    return max(0.0, min(float(value), 1.0))


def _safe_float(value: Any) -> float:
    """把可能为 None / 字符串的分数安全转成 float，脏数据按 0 处理"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class RAGQualityChecker:
    """基于绝对相关性的运行时质量门控与处置决策。

    与旧版的三点区别：
    1. 分数来源不是 sigmoid(rerank logit)，而是 cosine / logit 的绝对校准分；
    2. 元数据匹配从 0.20 降权到 0.10 —— 候选全是同一条 where 子句筛出来的，
       它只证明过滤生效，不含任何主题信息，不该白送 0.20 分；
    3. 输出 decision：
         web      两路绝对信号同时低于硬线 → 知识库无覆盖，跳过重写直接联网
         rewrite  只有一路偏低或总分未过线 → 改写查询重试，超限后联网
         pass     两路都够且总分达标
       缺绝对信号时（合成数据 / 重排模型不可用）退化为纯分数判定，保持向后兼容。
    """

    def __init__(self, threshold: float = 0.55, *,
                 hard_cosine: Optional[float] = None,
                 hard_logit: Optional[float] = None,
                 soft_cosine: Optional[float] = None,
                 soft_logit: Optional[float] = None):
        """输入通过阈值与两级门槛；未显式传入的门槛统一从全局 config 读取。"""
        try:
            from src.config import config
            rag = config.get_defaults().get("rag", {})
        except Exception:
            rag = {}
        self.threshold = threshold
        self.hard_cosine = _safe_float(hard_cosine if hard_cosine is not None
                                       else rag.get("hard_cosine", 0.25))
        self.hard_logit = _safe_float(hard_logit if hard_logit is not None
                                      else rag.get("hard_logit", 0.5))
        self.soft_cosine = _safe_float(soft_cosine if soft_cosine is not None
                                       else rag.get("soft_cosine", 0.28))
        self.soft_logit = _safe_float(soft_logit if soft_logit is not None
                                      else rag.get("soft_logit", 0.65))

    @staticmethod
    def _score(item: dict[str, Any]) -> float:
        """输入单条资源，返回 0~1 的绝对相关性；缺绝对信号时回退旧标量。"""
        cosine = item.get("dense_similarity")
        logit = item.get("rerank_score")
        if cosine is None and logit is None:
            legacy = item.get("rerank_confidence")
            if legacy is None:
                legacy = item.get("similarity", 0.0)
            return _clamp(_safe_float(legacy))
        parts = []
        if cosine is not None:
            parts.append(_clamp((_safe_float(cosine) - COSINE_FLOOR)
                                / (COSINE_FULL - COSINE_FLOOR)))
        if logit is not None:
            parts.append(_clamp(_safe_float(logit) / LOGIT_FULL))
        return sum(parts) / len(parts) if parts else 0.0

    @staticmethod
    def _absolute_signals(results: list[dict[str, Any]]) -> tuple[Optional[float], Optional[float]]:
        """返回 (最高真实余弦, 最高重排原始分)；缺失的维度返回 None。"""
        cosines = [_safe_float(r["dense_similarity"]) for r in results
                   if r.get("dense_similarity") is not None]
        logits = [_safe_float(r["rerank_score"]) for r in results
                  if r.get("rerank_score") is not None]
        return (max(cosines) if cosines else None,
                max(logits) if logits else None)

    def evaluate(self, results: list[dict[str, Any]], field: str | None = None,
                 level: str | None = None, resource_types: list[str] | None = None) -> dict[str, Any]:
        """输入候选资源和过滤条件，返回质量报告与处置决策"""
        if not results:
            return {"score": 0.0, "grade": "low", "passed": False,
                    "decision": "web", "signals": {},
                    "issues": ["知识库未返回候选资源"]}

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

        # 权重从 0.55/0.25/0.20 改为 0.65/0.25/0.10：
        # 把「元数据自证」省下的 0.10 交给绝对相关性的首位项。
        quality_score = round(0.65 * top_score + 0.25 * avg_score
                              + 0.10 * match_ratio, 4)

        top_cosine, top_logit = self._absolute_signals(results)
        if top_cosine is not None or top_logit is not None:
            # 缺失的一维视为「不坏」：重排模型不可用时只有 cosine，
            # 不应因为拿不到 logit 就把所有库内查询都判成 rewrite。
            hard_cos_bad = top_cosine is not None and top_cosine < self.hard_cosine
            hard_logit_bad = top_logit is not None and top_logit < self.hard_logit
            soft_cos_bad = top_cosine is not None and top_cosine < self.soft_cosine
            soft_logit_bad = top_logit is not None and top_logit < self.soft_logit
            if (top_cosine is not None and top_logit is not None
                    and hard_cos_bad and hard_logit_bad):
                # 两路都实测且都极低：主题不在库里，改写只是换词，没有意义
                decision = "web"
            elif soft_cos_bad or soft_logit_bad or quality_score < self.threshold:
                # 单路偏弱：更可能是查询表达不好，值得改写重试
                decision = "rewrite"
            else:
                decision = "pass"
        else:
            decision = "pass" if quality_score >= self.threshold else "rewrite"

        passed = decision == "pass" and quality_score >= self.threshold

        issues = []
        if top_score < 0.55:
            issues.append("最高相关资源置信度偏低")
        if avg_score < 0.40:
            issues.append("候选资源整体相关性偏低")
        if match_ratio < 0.70:
            issues.append("领域、难度或资源类型匹配不足")
        if diversity <= 1 and len(results) > 1:
            issues.append("候选资源类型过于单一")
        if decision == "web":
            issues.append("两路绝对相关性均低于硬阈值，判定知识库无覆盖")
        elif decision == "rewrite":
            issues.append("绝对相关性偏弱或总分未达标，需要改写查询")

        grade = ("high" if quality_score >= 0.72 else
                 "medium" if quality_score >= self.threshold else "low")
        if decision == "web":
            grade = "low"
        return {
            "score": quality_score,
            "grade": grade,
            "passed": passed,
            "decision": decision,
            "signals": {
                "top_confidence": round(top_score, 4),
                "average_confidence": round(avg_score, 4),
                "top_dense_similarity": round(top_cosine, 4) if top_cosine is not None else None,
                "top_rerank_logit": round(top_logit, 4) if top_logit is not None else None,
                "metadata_match_ratio": round(match_ratio, 4),
                "resource_type_diversity": diversity,
                "candidate_count": len(results),
            },
            "issues": issues,
        }
