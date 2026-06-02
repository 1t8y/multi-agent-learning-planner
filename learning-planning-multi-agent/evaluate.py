"""评估脚本：跑测试集输出量化对比报告"""

import json
from vector_store import VectorStoreManager, init_vector_store_with_seed_data

TEST_CASES = [
    # Python基础教程 - 5个查询变体
    {"query": "Python入门学习", "expected_titles": ["Python基础教程"]},
    {"query": "零基础学Python编程", "expected_titles": ["Python基础教程"]},
    {"query": "Python变量数据类型", "expected_titles": ["Python基础教程"]},
    {"query": "Python控制流和函数", "expected_titles": ["Python基础教程"]},
    {"query": "Python编程基础教程", "expected_titles": ["Python基础教程"]},

    # 机器学习实战 - 5个查询变体
    {"query": "机器学习基础", "expected_titles": ["机器学习实战"]},
    {"query": "sklearn机器学习算法", "expected_titles": ["机器学习实战"]},
    {"query": "AI机器学习应用", "expected_titles": ["机器学习实战"]},
    {"query": "机器学习从理论到实践", "expected_titles": ["机器学习实战"]},
    {"query": "scikit-learn入门", "expected_titles": ["机器学习实战"]},

    # Transformer原理详解 - 5个查询变体
    {"query": "Transformer注意力机制", "expected_titles": ["Transformer原理详解"]},
    {"query": "大模型Transformer架构", "expected_titles": ["Transformer原理详解"]},
    {"query": "NLP注意力机制", "expected_titles": ["Transformer原理详解"]},
    {"query": "Transformer模型原理", "expected_titles": ["Transformer原理详解"]},
    {"query": "自注意力机制详解", "expected_titles": ["Transformer原理详解"]},

    # 高等数学核心概念 - 5个查询变体
    {"query": "微积分线性代数", "expected_titles": ["高等数学核心概念"]},
    {"query": "大学高数概率论", "expected_titles": ["高等数学核心概念"]},
    {"query": "数学基础微积分", "expected_titles": ["高等数学核心概念"]},
    {"query": "线性代数基础课程", "expected_titles": ["高等数学核心概念"]},
    {"query": "高数入门学习", "expected_titles": ["高等数学核心概念"]},

    # React官方文档 - 5个查询变体
    {"query": "React前端框架", "expected_titles": ["React官方文档"]},
    {"query": "React Hooks入门", "expected_titles": ["React官方文档"]},
    {"query": "React TypeScript开发", "expected_titles": ["React官方文档"]},
    {"query": "前端React框架", "expected_titles": ["React官方文档"]},
    {"query": "React官方教程", "expected_titles": ["React官方文档"]},
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
