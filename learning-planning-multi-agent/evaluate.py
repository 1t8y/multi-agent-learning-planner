"""评估脚本：跑测试集输出量化对比报告"""

import json
from vector_store import VectorStoreManager, init_vector_store_with_seed_data

TEST_CASES = [
    {"query": "Python入门学习", "expected_titles": ["Python基础教程"]},
    {"query": "机器学习基础", "expected_titles": ["机器学习实战"]},
    {"query": "Transformer注意力机制", "expected_titles": ["Transformer原理详解"]},
    {"query": "微积分线性代数", "expected_titles": ["高等数学核心概念"]},
    {"query": "React前端框架", "expected_titles": ["React官方文档"]},
]


def evaluate_mode(mode="dense"):
    store = init_vector_store_with_seed_data()
    hr_count = 0
    mrr_sum = 0.0
    precision_sum = 0.0

    for case in TEST_CASES:
        results = store.search(case["query"], mode=mode, top_k=5)
        titles = [r.get("title", "") for r in results]
        hit = any(t in titles for t in case["expected_titles"])
        if hit:
            hr_count += 1
            for rank, title in enumerate(titles, 1):
                if title in case["expected_titles"]:
                    mrr_sum += 1.0 / rank
                    break
        rel_count = sum(1 for t in titles[:3] if t in case["expected_titles"])
        precision_sum += rel_count / 3

    n = len(TEST_CASES)
    return {
        "HR@5": round(hr_count / n, 3),
        "MRR": round(mrr_sum / n, 3),
        "P@3": round(precision_sum / n, 3),
    }


if __name__ == "__main__":
    print("=== 检索评估报告 ===")
    dense = evaluate_mode("dense")
    hybrid = evaluate_mode("hybrid")
    print(json.dumps({"dense": dense, "hybrid": hybrid}, indent=2, ensure_ascii=False))
    print("\n提升幅度:")
    for k in dense:
        delta = hybrid[k] - dense[k]
        sign = "+" if delta > 0 else ""
        print(f"  {k}: {dense[k]} → {hybrid[k]} ({sign}{delta:.3f})")
