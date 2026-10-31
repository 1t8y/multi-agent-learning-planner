# 文件：retrieval_metrics.py
# 功能：检索评测指标的统一实现，供评测脚本与基准脚本共用
# 输入：检索结果 id 列表与期望 id 列表；输出：Hit@k、MRR@k、P@k 等指标

from __future__ import annotations

from typing import Dict, List, Optional, Sequence


def rank_of_first_hit(retrieved_ids: Sequence[str],
                      expected_ids: Sequence[str]) -> Optional[int]:
    """
    输入一次检索的 id 序列和可接受答案集合，返回首个命中的 1 基排名。

    一道题允许多个正确资源（同义资源、不同难度替代），任一命中即算召回。
    未命中返回 None。
    """
    acceptable = {str(i) for i in expected_ids}
    for position, doc_id in enumerate(retrieved_ids, start=1):
        if str(doc_id) in acceptable:
            return position
    return None


def precision_at_k(retrieved_ids: Sequence[str], expected_ids: Sequence[str], k: int) -> float:
    """
    输入检索结果，返回前 k 条中命中期望答案的比例。

    分母固定为 k 而不是实际返回条数：过滤后结果不足 k 条时，
    若按实际条数做分母会把 P@k 抬高，导致不同档位之间不可比。
    """
    acceptable = {str(i) for i in expected_ids}
    top = list(retrieved_ids)[:k]
    if k <= 0:
        return 0.0
    return sum(1 for doc_id in top if str(doc_id) in acceptable) / k


def summarize(details: List[Dict], k: int) -> Dict[str, float]:
    """
    输入逐题明细（含 rank）和截断位 k，返回聚合指标。

    Hit@1    首位命中率，最严的指标
    Hit@k    前 k 条内命中率，衡量召回能力
    MRR@k    命中排名的倒数均值，未命中记 0
    Precision@k  前 k 条里正确答案的占比
    """
    total = len(details)
    if total == 0:
        return {}
    hits = [d for d in details if d.get("rank") is not None]
    return {
        "questions": total,
        "hit_at_1": round(sum(1 for d in details if d.get("rank") == 1) / total, 4),
        f"hit_at_{k}": round(len(hits) / total, 4),
        f"mrr_at_{k}": round(sum(1.0 / d["rank"] for d in hits) / total, 4),
        f"p_at_{min(k, 3)}": round(
            sum(d.get("precision", 0.0) for d in details) / total, 4),
        "misses": total - len(hits),
    }


def group_summarize(details: List[Dict], k: int, key: str) -> Dict[str, Dict[str, float]]:
    """按指定字段分组后再统计，用于发现某类问题上的短板"""
    groups: Dict[str, List[Dict]] = {}
    for detail in details:
        groups.setdefault(str(detail.get(key, "unknown")), []).append(detail)
    return {name: summarize(rows, k) for name, rows in sorted(groups.items())}
