# 文件：bench_retrieval.py
# 功能：检索链路消融评测与延迟基准
# 输入：data/evaluation/ragas_testset_v3.jsonl、已重建的 chroma_db
# 输出：控制台 Markdown 表格 + data/evaluation/bench_retrieval.json

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Callable, Dict, List

from retrieval_metrics import group_summarize, precision_at_k, rank_of_first_hit, summarize

ROOT = Path(__file__).resolve().parent
TESTSET = ROOT / "data" / "evaluation" / "ragas_testset_v3.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "bench_retrieval.json"
LEVELS = {"零基础": "beginner", "进阶": "intermediate", "高阶": "advanced"}


def load_tests() -> List[Dict]:
    """读取评测测试集"""
    rows = [json.loads(line) for line in TESTSET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit("测试集为空，先运行 tools/build_testset.py")
    return rows


def build_modes(store, top_k: int, candidate_k: int,
                gate: float = 0.55) -> tuple[Dict[str, Callable[[Dict], List[Dict]]], Dict[str, int]]:
    """
    构造各消融档位的检索函数，统一返回结果列表。

    带 filter 的档位使用题目标注的领域/难度/类型作为过滤条件，
    等价于「需求提取阶段完全正确」的理想情况，用于衡量过滤本身的收益；
    线上实际效果还取决于需求提取准确率，这一点在报告里单独说明。

    带 gate 的档位启用置信度门控：首位重排置信度低于 gate 时保留融合顺序。
    第二个返回值统计各门控档位的回退次数。
    """
    from reranker import ResourceReranker

    reranker = ResourceReranker()
    gated = ResourceReranker(min_confidence=gate)
    counters: Dict[str, int] = {}

    def rerank(query: str, results: List[Dict]) -> List[Dict]:
        """对候选做 Cross-Encoder 精排并截断"""
        return reranker.rerank(query, results, top_k=top_k)

    def make_gated(name: str) -> Callable[[Dict], List[Dict]]:
        """生成带门控的档位函数，并按档位名累计回退次数"""
        def run(row: Dict) -> List[Dict]:
            query = row["question"]
            candidates = (filtered(row, candidate_k) if "filter" in name
                          else store.search(query, top_k=candidate_k, mode="hybrid"))
            output = gated.rerank(query, candidates, top_k=top_k)
            if gated.last_gate_fallback:
                counters[name] = counters.get(name, 0) + 1
            return output
        return run

    def plain(mode: str, k: int):
        return lambda row: store.search(row["question"], top_k=k, mode=mode)

    def filtered(row: Dict, k: int, mode: str = "hybrid", min_types: int = 0) -> List[Dict]:
        """带元数据过滤的检索"""
        return store.search(
            row["question"], top_k=k, mode=mode,
            field=row.get("topic"),
            level=LEVELS.get(row.get("difficulty", ""), None),
            resource_types=[row["resource_type"]] if row.get("resource_type") else None,
            min_types=min_types,
        )

    modes = {
        "dense": plain("dense", top_k),
        "sparse": plain("sparse", top_k),
        "hybrid": plain("hybrid", top_k),
        # 对照组：候选池同样放到 candidate_k 但不做重排，用于剥离「池子变大」的影响
        "hybrid@candidate_k": lambda row: store.search(
            row["question"], top_k=top_k, mode="hybrid", candidate_k=candidate_k),
        "hybrid+rerank": lambda row: rerank(
            row["question"], store.search(row["question"], top_k=candidate_k, mode="hybrid")),
        "hybrid+rerank+gate": make_gated("hybrid+rerank+gate"),
        "hybrid+filter": lambda row: filtered(row, top_k),
        "hybrid+filter+div": lambda row: filtered(row, top_k, min_types=2),
        "hybrid+filter+rerank": lambda row: rerank(
            row["question"], filtered(row, candidate_k)),
        "hybrid+filter+rerank+gate": make_gated("hybrid+filter+rerank+gate"),
    }
    return modes, counters


def run_mode(runner: Callable[[Dict], List[Dict]], rows: List[Dict], top_k: int) -> Dict:
    """输入一个检索档位，返回该档位的逐题明细、指标和延迟"""
    precision_k = min(3, top_k)
    details, latencies = [], []
    for row in rows:
        started = time.perf_counter()
        results = runner(row)
        latencies.append((time.perf_counter() - started) * 1000)
        ids = [item.get("id", "") for item in results]
        details.append({
            "id": row["id"],
            "rank": rank_of_first_hit(ids, row["expected_source_ids"]),
            "precision": precision_at_k(ids, row["expected_source_ids"], precision_k),
            "top_ids": ids,
            "topic": row.get("topic", ""),
            "difficulty": row.get("difficulty", ""),
            "query_style": row.get("query_style", ""),
        })
    metrics = summarize(details, top_k)
    metrics["latency_ms_p50"] = round(statistics.median(latencies), 2)
    metrics["latency_ms_p95"] = round(
        sorted(latencies)[max(int(len(latencies) * 0.95) - 1, 0)], 2)
    return {
        "metrics": metrics,
        "by_topic": group_summarize(details, top_k, "topic"),
        "by_difficulty": group_summarize(details, top_k, "difficulty"),
        "by_query_style": group_summarize(details, top_k, "query_style"),
        "details": details,
    }


def format_table(report: Dict[str, Dict], top_k: int) -> str:
    """把各档位指标渲染成 Markdown 表格"""
    header = (
        f"| 档位 | Hit@1 | Hit@{top_k} | MRR@{top_k} | P@3 | 未命中 | P50(ms) | P95(ms) |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    for name, payload in report.items():
        m = payload["metrics"]
        lines.append(
            f"| {name} | {m['hit_at_1']:.4f} | {m[f'hit_at_{top_k}']:.4f} | "
            f"{m[f'mrr_at_{top_k}']:.4f} | {m[f'p_at_{min(top_k, 3)}']:.4f} | "
            f"{m['misses']} | {m['latency_ms_p50']:.2f} | {m['latency_ms_p95']:.2f} |"
        )
    return "\n".join(lines)


def measure_cold_start(store, rows: List[Dict]) -> Dict[str, float]:
    """
    测量首个查询与稳态查询的耗时。

    稳态样本使用 candidate_k=10 的参数组合，避免与前面消融档位命中同一缓存条目，
    否则测到的是缓存命中时间而不是真实检索时间。
    """
    warm_query = "Python 机器学习 教程"
    started = time.perf_counter()
    store.search(warm_query, top_k=5, mode="hybrid", candidate_k=10)
    first = (time.perf_counter() - started) * 1000

    samples = []
    for row in rows[:20]:
        t0 = time.perf_counter()
        store.search(row["question"], top_k=5, mode="hybrid", candidate_k=10)
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "first_hybrid_query_ms": round(first, 2),
        "warm_hybrid_query_ms_p50": round(statistics.median(samples), 2),
        "warm_hybrid_query_ms_p95": round(
            sorted(samples)[max(int(len(samples) * 0.95) - 1, 0)], 2),
    }


def main() -> int:
    """解析参数，执行全部消融档位并输出报告"""
    parser = argparse.ArgumentParser(description="检索链路消融评测")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-rerank", action="store_true", help="跳过需要加载重排模型的档位")
    parser.add_argument("--gate-confidence", type=float, default=0.55,
                        help="置信度门控阈值，首位重排置信度低于该值时保留融合顺序")
    args = parser.parse_args()

    import time as _time

    init_started = _time.perf_counter()
    from vector_store import init_vector_store_with_seed_data, get_cache_stats

    store = init_vector_store_with_seed_data()
    init_seconds = _time.perf_counter() - init_started

    rows = load_tests()
    modes, counters = build_modes(store, args.top_k, args.candidate_k, gate=args.gate_confidence)
    if args.skip_rerank:
        modes = {name: fn for name, fn in modes.items() if "rerank" not in name}

    report = {}
    for name, runner in modes.items():
        report[name] = run_mode(runner, rows, args.top_k)
        print(f"[bench] {name} 完成", flush=True)
    for name, count in counters.items():
        if name in report:
            report[name]["metrics"]["gate_fallbacks"] = count

    cold = measure_cold_start(store, rows)
    payload = {
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kb_total": store.get_stats()["total_count"],
        "questions": len(rows),
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "rerank_gate_confidence": args.gate_confidence,
        "init_seconds": round(init_seconds, 2),
        **cold,
        "cache_stats": get_cache_stats(),
        "modes": report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n## 检索消融结果\n")
    print(format_table(report, args.top_k))
    print(f"\n知识库 {payload['kb_total']} 条，题目 {payload['questions']} 道，"
          f"top_k={args.top_k}，candidate_k={args.candidate_k}")
    print(f"初始化 {payload['init_seconds']}s，首个混合查询 {cold['first_hybrid_query_ms']}ms，"
          f"稳态 P50 {cold['warm_hybrid_query_ms_p50']}ms")
    print(f"\n明细已写入：{args.output.relative_to(ROOT)}")

    best = max(report.items(), key=lambda kv: kv[1]["metrics"][f"mrr_at_{args.top_k}"])
    print(f"最优档位：{best[0]}（MRR@{args.top_k}={best[1]['metrics'][f'mrr_at_{args.top_k}']:.4f}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
