# 文件：tools/experiment_rerank_gate.py
# 功能：量化 Cross-Encoder 重排的失效条件，并评估「分数过低时回退融合顺序」的效果
# 输入：v3 评测集 + 已重建的 chroma_db
# 输出：控制台诊断表（不写文件、不修改生产代码）

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTSET = ROOT / "data" / "evaluation" / "ragas_testset_v3.jsonl"
CANDIDATE_K = 10
TOP_K = 5
THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]


def rank_of(ids: list[str], expected: set[str]) -> int | None:
    """返回首个命中的 1 基排名"""
    for position, doc_id in enumerate(ids, start=1):
        if doc_id in expected:
            return position
    return None


def main() -> int:
    """跑一次全量打分，然后用离线复算评估各阈值"""
    from reranker import ResourceReranker
    from vector_store import init_vector_store_with_seed_data

    store = init_vector_store_with_seed_data()
    reranker = ResourceReranker()
    rows = [json.loads(line) for line in TESTSET.read_text(encoding="utf-8").splitlines() if line.strip()]

    samples = []
    for row in rows:
        expected = set(row["expected_source_ids"])
        candidates = store.search(row["question"], top_k=CANDIDATE_K, mode="hybrid")
        scored = reranker.rerank(row["question"], candidates, top_k=len(candidates))
        fused_ids = [c["id"] for c in candidates]
        rerank_ids = [s["id"] for s in scored]
        top_score = scored[0]["rerank_score"] if scored else 0.0
        samples.append({
            "id": row["id"],
            "top_score": top_score,
            "rank_fused": rank_of(fused_ids, expected),
            "rank_rerank": rank_of(rerank_ids, expected),
        })

    total = len(samples)

    # ---- 1. 重排置信度分桶，看模型在有判断力/没判断力时的表现差异 ----
    print("\n## 1. 按「最高重排分数」分桶\n")
    print("| 最高重排分数 | 题数 | 融合 Hit@1 | 重排 Hit@1 | 提升 | 退步 |")
    print("|---|---:|---:|---:|---:|---:|")
    buckets = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 1.01)]
    for low, high in buckets:
        group = [s for s in samples if low <= s["top_score"] < high]
        if not group:
            continue
        fused_hit = sum(1 for s in group if s["rank_fused"] == 1)
        rerank_hit = sum(1 for s in group if s["rank_rerank"] == 1)
        up = sum(1 for s in group if s["rank_rerank"] == 1 and s["rank_fused"] != 1)
        down = sum(1 for s in group if s["rank_fused"] == 1 and s["rank_rerank"] != 1)
        label = f"[{low:.1f}, {high:.1f})" if high <= 1.0 else f"[{low:.1f}, 1.0]"
        print(f"| {label} | {len(group)} | {fused_hit/len(group):.4f} | "
              f"{rerank_hit/len(group):.4f} | {up} | {down} |")

    # ---- 2. 阈值回退：最高分低于阈值时不用重排 ----
    print("\n## 2. 阈值回退（最高分 < 阈值则保留融合顺序）\n")
    print("| 阈值 | Hit@1 | MRR@5 | Hit@5 | 实际触发回退 |")
    print("|---:|---:|---:|---:|---:|")
    for threshold in THRESHOLDS:
        hit1 = 0
        mrr = 0.0
        hit5 = 0
        fallback = 0
        for sample in samples:
            if sample["top_score"] < threshold:
                rank = sample["rank_fused"]
                fallback += 1
            else:
                rank = sample["rank_rerank"]
            if rank == 1:
                hit1 += 1
            if rank is not None and rank <= TOP_K:
                hit5 += 1
                mrr += 1.0 / rank
        print(f"| {threshold:.1f} | {hit1/total:.4f} | {mrr/total:.4f} | "
              f"{hit5/total:.4f} | {fallback}/{total} |")

    # ---- 3. 端点对照 ----
    scores = [s["top_score"] for s in samples]
    print("\n## 3. 端点与分数分布\n")
    print(f"- 纯融合：Hit@1 = {sum(1 for s in samples if s['rank_fused']==1)/total:.4f}")
    print(f"- 纯重排：Hit@1 = {sum(1 for s in samples if s['rank_rerank']==1)/total:.4f}")
    print(f"- 最高重排分数：中位数 {statistics.median(scores):.3f}，"
          f"最小 {min(scores):.3f}，最大 {max(scores):.3f}")
    print(f"- 最高分 < 0.1 的题：{sum(1 for s in scores if s < 0.1)}/{total}，"
          f"< 0.3 的题：{sum(1 for s in scores if s < 0.3)}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
