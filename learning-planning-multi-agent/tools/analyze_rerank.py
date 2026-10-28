# 文件：tools/analyze_rerank.py
# 功能：诊断 Cross-Encoder 重排为何改变名次，逐题打印候选的融合排名与重排分数
# 输入：bench_retrieval.json 中名次发生变化的题目
# 输出：控制台诊断表（不写文件）

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCH = ROOT / "data" / "evaluation" / "bench_retrieval.json"
TESTSET = ROOT / "data" / "evaluation" / "ragas_testset_v3.jsonl"


def load_rows() -> dict[str, dict]:
    """读取评测集，返回 id 到题目的映射"""
    rows = [json.loads(line) for line in TESTSET.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["id"]: row for row in rows}


def changed_ids() -> list[str]:
    """返回在 hybrid 与 hybrid+rerank 之间名次发生变化的题目 id"""
    payload = json.loads(BENCH.read_text(encoding="utf-8"))
    base = {x["id"]: x["rank"] for x in payload["modes"]["hybrid"]["details"]}
    rr = {x["id"]: x["rank"] for x in payload["modes"]["hybrid+rerank"]["details"]}
    return [qid for qid in base if base[qid] != rr[qid]]


def main() -> int:
    """逐题输出候选表，标出正确答案与最终首位"""
    from reranker import ResourceReranker
    from vector_store import init_vector_store_with_seed_data

    store = init_vector_store_with_seed_data()
    reranker = ResourceReranker()
    rows = load_rows()

    for qid in changed_ids():
        row = rows[qid]
        expected = set(row["expected_source_ids"])
        candidates = store.search(row["question"], top_k=10, mode="hybrid")
        # 对全部候选打分，才能看到被挤出前 5 的那条到底被打了多少分
        scored = reranker.rerank(row["question"], candidates, top_k=len(candidates))
        scores = {item["id"]: item["rerank_score"] for item in scored}
        top = scored[0]["id"]

        print("=" * 100)
        print(f"[{qid}] {row['question']}")
        print(f"  期望: {row['expected_source_ids']}  {row['expected_sources']}")
        print(f"  融合首位: {candidates[0]['id']}   重排首位: {top}"
              f"   {'重排后仍然正确' if top in expected else '重排把正确答案挤下去了'}")
        print()
        print(f"  {'':3s} {'id':30s} {'dense':>5s} {'sparse':>6s} {'RRF':>8s} {'rerank':>8s}  标题")
        for cand in candidates:
            mark = "<-- 期望" if cand["id"] in expected else ""
            star = "  *" if cand["id"] in expected else "   "
            print(
                f"{star} {cand['id']:30s} {str(cand.get('rank_dense')):>5s} "
                f"{str(cand.get('rank_sparse')):>6s} {cand.get('fused_score', 0):>8.5f} "
                f"{scores.get(cand['id'], 0):>8.3f}  {cand['title'][:22]:22s} {mark}"
            )
        print(f"  重排后顺序: {[item['id'] for item in scored][:5]}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
