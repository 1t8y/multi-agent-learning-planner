# 文件：eval/tools/calibrate_scope_thresholds.py
# 功能：标定「库外查询识别」两级阈值所需的绝对分数分布
# 输入：eval.test_rag_pipeline 的库内场景与库外场景
# 输出：控制台分布表 + 阈值建议（不修改生产代码、不联网）
#
# 用法：cd backend && .venv-run/Scripts/python.exe -B -m eval.tools.calibrate_scope_thresholds
# 什么时候要重跑：换 Embedding / 重排模型、增删知识库资源后，
#                 docs/ARCHITECTURE.md 里的阈值标定区间需要同步更新。
from __future__ import annotations

from src.rag.advanced_self_rag import AdvancedSelfRAGRecommender
from src.rag.self_rag_recommender import RAGState
from eval.test_rag_pipeline import CASES, OUT_OF_SCOPE_CASES


def probe(recommender: AdvancedSelfRAGRecommender,
          objective: str, foundation: str, preference: str) -> dict:
    """输入一条查询，返回它的两路绝对信号与候选数"""
    state = RAGState(learning_objective=objective, current_foundation=foundation)
    state.learning_preference = preference
    query = recommender._build_search_query(state)
    field = recommender._detect_field(query)
    level = recommender._map_level_filter(foundation)
    types = recommender._map_resource_types(preference)

    # 标定必须看未过滤的原始分布：开着 RRF 前置门槛时库外查询会被全部过滤成空
    candidates, _ = recommender._search_candidates(
        query, field if field != "其他" else None, level, types)
    cosines = [float(r["dense_similarity"]) for r in candidates
               if r.get("dense_similarity") is not None]
    reranked = recommender.reranker.rerank(query, candidates, recommender.TOP_K)
    logits = [float(r["rerank_score"]) for r in reranked
              if r.get("rerank_score") is not None]
    return {"cosine": round(max(cosines), 4) if cosines else None,
            "logit": round(max(logits), 4) if logits else None,
            "candidates": len(candidates)}


def main() -> int:
    """打印库内/库外分布，并给出两级阈值的可选区间"""
    recommender = AdvancedSelfRAGRecommender()
    # 标定看原始分数，同时避免实验产生外部请求
    recommender.MIN_DENSE_SIMILARITY = None
    recommender.web_search = None

    groups = {
        "库内": [(objective, foundation, preference)
               for _, objective, foundation, preference in CASES],
        "库外": list(OUT_OF_SCOPE_CASES),
    }
    summary = {}
    print("\n| 组 | 场景 | top1 cosine | top1 logit | 候选数 |")
    print("|---|---|---:|---:|---:|")
    for label, cases in groups.items():
        rows = []
        for objective, foundation, preference in cases:
            p = probe(recommender, objective, foundation, preference)
            rows.append(p)
            print(f"| {label} | {objective[:18]} | {p['cosine']} | "
                  f"{p['logit']} | {p['candidates']} |")
        summary[label] = rows

    def values(label, key):
        return [r[key] for r in summary[label] if r[key] is not None]

    in_cos, out_cos = values("库内", "cosine"), values("库外", "cosine")
    in_logit, out_logit = values("库内", "logit"), values("库外", "logit")
    print(f"\n- cosine：库内 {min(in_cos):.4f}~{max(in_cos):.4f}，"
          f"库外 {min(out_cos):.4f}~{max(out_cos):.4f}")
    print(f"- logit ：库内 {min(in_logit):.4f}~{max(in_logit):.4f}，"
          f"库外 {min(out_logit):.4f}~{max(out_logit):.4f}")
    print(f"- 硬线可选区间：RAG_HARD_COSINE ∈ ({max(out_cos):.4f}, {min(in_cos):.4f})，"
          f"RAG_HARD_LOGIT ∈ ({max(out_logit):.4f}, {min(in_logit):.4f})")
    print("- 软线应落在库内最小值以下、硬线以上，留出一个「只有一路偏弱」的改写区间。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
