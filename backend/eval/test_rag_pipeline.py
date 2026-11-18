# 文件：eval/test_rag_pipeline.py
# 功能：验证增强 Self-RAG 的过滤、重排、质量门控与库外查询兜底链路
# 输入：无；输出：逐场景结果和最终退出码
from __future__ import annotations

from src.rag.advanced_self_rag import AdvancedSelfRAGRecommender


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

# 知识库只有 AI / 编程 / 数学，这些主题必须被判为「无覆盖」并直接联网
OUT_OF_SCOPE_CASES = [
    ("备考期末知识产权法，掌握核心考点概念", "零基础", "视频"),
    ("想学韩语入门，有推荐的视频课程吗", "零基础", "视频"),
    ("两周备考期末民法学，要核心法条", "零基础", "文字"),
]


class SpyWebSearch:
    """替换真实联网通道：只记录调用，避免回归脚本产生外部请求。"""

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def status(self):
        return {"enabled": True, "api_key_configured": True, "channel": "spy",
                "available": True, "reason": "", "last_error": ""}

    def search_learning_resources(self, **kwargs):
        self.calls += 1
        return [{"title": "联网补充资源", "description": "知识库未覆盖的主题",
                 "resource_type": "视频教程", "url": "https://example.com/web"}]


def run_case(recommender: AdvancedSelfRAGRecommender, case: tuple) -> bool:
    """输入推荐器和库内场景，返回该场景是否通过"""
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
    passed = (top_id == expected_id and quality.get("passed", False)
              and result.get("decision") == "pass"
              and not result.get("used_web_search") and rerank_ok)
    print(
        f"{'PASS' if passed else 'FAIL'} expected={expected_id} top={top_id} "
        f"quality={quality.get('grade')} score={quality.get('score')} candidates={result.get('candidate_count')}"
    )
    return passed


def run_out_of_scope_case(recommender: AdvancedSelfRAGRecommender,
                          case: tuple, spy: SpyWebSearch) -> bool:
    """库外查询必须跳过改写直接联网，且不能混入不相关的知识库资源"""
    objective, foundation, preference = case
    result = recommender.recommend(
        learning_objective=objective,
        current_foundation=foundation,
        learning_preference=preference,
        time_expectation="短期学习",
    )
    resources = result.get("resources", [])
    kb_ids = [r.get("id") for r in resources if r.get("source") == "knowledge_base"]
    passed = (result.get("decision") == "web"
              and result.get("rewrite_count") == 0
              and result.get("used_web_search") is True
              and spy.calls == 1
              and not kb_ids
              and result.get("quality", {}).get("passed") is False)
    print(
        f"{'PASS' if passed else 'FAIL'} [库外] {objective[:16]} decision={result.get('decision')} "
        f"rewrite={result.get('rewrite_count')} web={result.get('used_web_search')} kb_ids={kb_ids}"
    )
    return passed


def main() -> int:
    """执行库内与库外全部场景并返回退出码"""
    recommender = AdvancedSelfRAGRecommender()
    results = [run_case(recommender, case) for case in CASES]

    original_web = recommender.web_search
    try:
        for case in OUT_OF_SCOPE_CASES:
            spy = SpyWebSearch()
            recommender.web_search = spy
            results.append(run_out_of_scope_case(recommender, case, spy))
    finally:
        recommender.web_search = original_web

    print(f"summary={sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
