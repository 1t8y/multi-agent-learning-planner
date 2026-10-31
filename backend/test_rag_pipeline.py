# 文件：test_rag_pipeline.py
# 功能：验证增强 Self-RAG 的过滤、重排和质量门控链路
# 输入：无；输出：逐场景结果和最终退出码
from __future__ import annotations

from advanced_self_rag import AdvancedSelfRAGRecommender


CASES = [
    ("python-bilibili-001", "Python编程基础", "零基础", "视频"),
    ("python-official-002", "Python官方语法和模块教程", "零基础", "文字"),
    ("ml-crash-course-002", "机器学习入门课程", "零基础", "文字"),
    ("ml-sklearn-001", "scikit-learn模型选择和评估", "中级", "文字"),
    ("transformer-illustrated-001", "Transformer图解和注意力机制", "中级", "文字"),
    ("huggingface-nlp-002", "Hugging Face NLP微调实战", "中级", "实操"),
    ("math-calculus-001", "人工智能所需微积分线性代数和概率论", "零基础", "视频"),
    ("math-linear-khan-002", "线性代数向量矩阵特征值", "零基础", "视频"),
    ("react-official-001", "React组件Hooks官方文档", "中级", "文字"),
    ("typescript-handbook-002", "TypeScript类型系统官方手册", "中级", "文字"),
]


def run_case(recommender: AdvancedSelfRAGRecommender, case: tuple) -> bool:
    """输入推荐器和场景，返回该场景是否通过"""
    expected_id, objective, foundation, preference = case
    result = recommender.recommend(
        learning_objective=objective,
        current_foundation=foundation,
        learning_preference=preference,
    )
    resources = result.get("resources", [])
    top_id = resources[0].get("id") if resources else None
    quality = result.get("quality", {})
    rerank_ok = result.get("rerank", {}).get("available", False)
    passed = top_id == expected_id and quality.get("passed", False) and rerank_ok
    print(
        f"{'PASS' if passed else 'FAIL'} expected={expected_id} top={top_id} "
        f"quality={quality.get('grade')} score={quality.get('score')} candidates={result.get('candidate_count')}"
    )
    return passed


def main() -> int:
    """执行全部 RAG 场景测试并返回退出码"""
    recommender = AdvancedSelfRAGRecommender()
    results = [run_case(recommender, case) for case in CASES]
    print(f"summary={sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
