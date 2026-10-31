# 文件：evaluate.py
# 功能：Dense / Sparse / Hybrid 三路检索对比（兼容入口，内部复用 bench_retrieval）
# 说明：v2.4.0 起旧的 25 条硬编码用例（引用已下线的 5 条预设资源）已废弃，
#       统一改用 data/evaluation/ragas_testset_v3.jsonl 的真实评测集。

from __future__ import annotations

import json

from bench_retrieval import format_table, load_tests, run_mode
from vector_store import init_vector_store_with_seed_data

TOP_K = 5


def main() -> int:
    """执行三路检索对比并打印 Markdown 表格"""
    store = init_vector_store_with_seed_data()
    rows = load_tests()

    runners = {
        "dense": lambda row: store.search(row["question"], top_k=TOP_K, mode="dense"),
        "sparse": lambda row: store.search(row["question"], top_k=TOP_K, mode="sparse"),
        "hybrid": lambda row: store.search(row["question"], top_k=TOP_K, mode="hybrid"),
    }
    report = {name: run_mode(fn, rows, TOP_K) for name, fn in runners.items()}

    print("# 检索对比（Dense vs Sparse vs Hybrid）\n")
    print(format_table(report, TOP_K))
    print(f"\n知识库 {store.get_stats()['total_count']} 条，题目 {len(rows)} 道，top_k={TOP_K}")

    deltas = {
        "hit_at_1_gain_vs_dense": round(
            report["hybrid"]["metrics"]["hit_at_1"] - report["dense"]["metrics"]["hit_at_1"], 4),
        "mrr_gain_vs_dense": round(
            report["hybrid"]["metrics"][f"mrr_at_{TOP_K}"]
            - report["dense"]["metrics"][f"mrr_at_{TOP_K}"], 4),
    }
    print(json.dumps(deltas, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
