"""评估脚本：Hybrid Search vs Dense Retrieval 量化对比报告"""

import json
from vector_store import VectorStoreManager, init_vector_store_with_seed_data

TEST_CASES = [
    {"query": "Python入门学习", "expected_titles": ["Python基础教程"]},
    {"query": "零基础学Python编程", "expected_titles": ["Python基础教程"]},
    {"query": "Python变量数据类型", "expected_titles": ["Python基础教程"]},
    {"query": "Python控制流和函数", "expected_titles": ["Python基础教程"]},
    {"query": "Python编程基础教程", "expected_titles": ["Python基础教程"]},
    {"query": "机器学习基础", "expected_titles": ["机器学习实战"]},
    {"query": "sklearn机器学习算法", "expected_titles": ["机器学习实战"]},
    {"query": "AI机器学习应用", "expected_titles": ["机器学习实战"]},
    {"query": "机器学习从理论到实践", "expected_titles": ["机器学习实战"]},
    {"query": "scikit-learn入门", "expected_titles": ["机器学习实战"]},
    {"query": "Transformer注意力机制", "expected_titles": ["Transformer原理详解"]},
    {"query": "大模型Transformer架构", "expected_titles": ["Transformer原理详解"]},
    {"query": "NLP注意力机制", "expected_titles": ["Transformer原理详解"]},
    {"query": "Transformer模型原理", "expected_titles": ["Transformer原理详解"]},
    {"query": "自注意力机制详解", "expected_titles": ["Transformer原理详解"]},
    {"query": "微积分线性代数", "expected_titles": ["高等数学核心概念"]},
    {"query": "大学高数概率论", "expected_titles": ["高等数学核心概念"]},
    {"query": "数学基础微积分", "expected_titles": ["高等数学核心概念"]},
    {"query": "线性代数基础课程", "expected_titles": ["高等数学核心概念"]},
    {"query": "高数入门学习", "expected_titles": ["高等数学核心概念"]},
    {"query": "React前端框架", "expected_titles": ["React官方文档"]},
    {"query": "React Hooks入门", "expected_titles": ["React官方文档"]},
    {"query": "React TypeScript开发", "expected_titles": ["React官方文档"]},
    {"query": "前端React框架", "expected_titles": ["React官方文档"]},
    {"query": "React官方教程", "expected_titles": ["React官方文档"]},
]


def evaluate_mode_detailed(mode="dense"):
    store = init_vector_store_with_seed_data()
    hr_count = 0
    mrr_sum = 0.0
    precision_sum = 0.0
    per_query_results = []

    for case in TEST_CASES:
        results = store.search(case["query"], mode=mode, top_k=5)
        titles = [r.get("title", "") for r in results]
        similarities = [r.get("similarity", 0) for r in results]
        hit = any(t in titles for t in case["expected_titles"])
        rank = None
        for i, t in enumerate(titles, 1):
            if t in case["expected_titles"]:
                rank = i
                break
        if hit:
            hr_count += 1
            if rank:
                mrr_sum += 1.0 / rank
        rel_count = sum(1 for t in titles[:3] if t in case["expected_titles"])
        precision_sum += rel_count / 3
        per_query_results.append({
            "query": case["query"],
            "expected": case["expected_titles"][0],
            "hit": hit,
            "rank": rank,
            "top_results": titles[:5],
            "top_scores": [round(s, 4) for s in similarities[:5]]
        })

    n = len(TEST_CASES)
    return {
        "metrics": {
            "HR@5": round(hr_count / n, 3),
            "MRR": round(mrr_sum / n, 3),
            "P@3": round(precision_sum / n, 3),
        },
        "per_query": per_query_results
    }


def print_comparison_report():
    print("=" * 70)
    print("Hybrid Search vs Dense Retrieval 量化对比报告")
    print("=" * 70)
    print()

    dense = evaluate_mode_detailed("dense")
    sparse = evaluate_mode_detailed("sparse")
    hybrid = evaluate_mode_detailed("hybrid")

    print("【整体指标对比】")
    print("-" * 70)
    print(f"{'指标':<10} {'Dense':<12} {'Sparse':<12} {'Hybrid':<12} {'Hybrid提升(vs Dense)':<15}")
    print("-" * 70)

    for metric in ["HR@5", "MRR", "P@3"]:
        d = dense["metrics"][metric]
        s = sparse["metrics"][metric]
        h = hybrid["metrics"][metric]
        delta = h - d
        delta_str = f"+{delta:.3f}" if delta > 0 else f"{delta:.3f}"
        print(f"{metric:<10} {d:<12.3f} {s:<12.3f} {h:<12.3f} {delta_str:<15}")

    print()
    print("【查询级别详细对比 - 排名变化】")
    print("-" * 70)
    print(f"{'#':<3} {'查询':<20} {'期望文档':<18} {'Dense':<8} {'Sparse':<8} {'Hybrid':<8}")
    print("-" * 70)

    for i, (dq, sq, hq) in enumerate(zip(dense["per_query"], sparse["per_query"], hybrid["per_query"]), 1):
        d_rank = str(dq["rank"]) if dq["rank"] else "-"
        s_rank = str(sq["rank"]) if sq["rank"] else "-"
        h_rank = str(hq["rank"]) if hq["rank"] else "-"
        query_display = dq["query"][:18] + "..." if len(dq["query"]) > 18 else dq["query"]
        print(f"{i:<3} {query_display:<20} {dq['expected']:<18} {d_rank:<8} {s_rank:<8} {h_rank:<8}")

    print()
    print("【统计分析】")
    print("-" * 70)

    hybrid_better = 0
    hybrid_worse = 0
    hybrid_same = 0

    for dq, hq in zip(dense["per_query"], hybrid["per_query"]):
        d_rank = dq["rank"] or 999
        h_rank = hq["rank"] or 999
        if h_rank < d_rank:
            hybrid_better += 1
        elif h_rank > d_rank:
            hybrid_worse += 1
        else:
            hybrid_same += 1

    total = len(dense["per_query"])
    print(f"Hybrid 排名优于 Dense: {hybrid_better}/{total} ({hybrid_better/total*100:.1f}%)")
    print(f"Hybrid 排名劣于 Dense: {hybrid_worse}/{total} ({hybrid_worse/total*100:.1f}%)")
    print(f"Hybrid 排名相同于 Dense: {hybrid_same}/{total} ({hybrid_same/total*100:.1f}%)")

    print()
    print("【配置信息】")
    print("-" * 70)
    print(f"测试用例数: {len(TEST_CASES)} (5个资源 × 5种查询变体)")
    print(f"知识库资源数: 5 (预设学习资源)")
    print(f"稀疏检索: BM25 + jieba中文分词 (5个文档)")
    print(f"融合策略: 保守型加权融合 (Dense为主, Sparse补充)")
    print(f"Embedding模型: BAAI/bge-small-zh-v1.5 (中文)")

    print()
    print("=" * 70)


if __name__ == "__main__":
    print_comparison_report()
