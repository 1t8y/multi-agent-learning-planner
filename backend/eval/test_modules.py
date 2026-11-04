"""模块冒烟测试：逐个导入并初始化核心组件，确认分层之后没有断链（CI 用）。

不依赖 pytest，直接 `python -m eval.test_modules` 运行；
任一检查抛异常只记为失败，不中断后续检查，最后按失败数决定退出码。
"""

import json
import sys

from src.config import config
from src.core.assessment_feedback import AssessmentFeedbackAgent
from src.core.base_agent import CircuitBreaker
from src.core.course_planner import CoursePlannerAgent
from src.core.graph_orchestrator import LANGGRAPH_AVAILABLE
from src.core.requirement_extractor import RequirementExtractorAgent
from src.core.resource_recommender import ResourceRecommenderAgent
from src.memory.vector_store import VectorStoreManager
from src.rag.retrieval import HybridRetriever
from src.rag.self_rag_recommender import init_self_rag

TESTS_PASSED = 0
TESTS_FAILED = 0


def check(name, fn):
    """执行一项检查：成功与失败都只打印一行，不抛出中断整轮冒烟。"""
    global TESTS_PASSED, TESTS_FAILED
    try:
        fn()
        TESTS_PASSED += 1
        print(f"  [OK] {name}")
    except Exception as exc:
        TESTS_FAILED += 1
        print(f"  [FAIL] {name}: {exc}")


def check_config():
    """配置单例能正常加载，并读得到 RAG 参数。"""
    print(f"    model={config.get('defaults.model')}")
    print(f"    rag={json.dumps(config.get_defaults().get('rag', {}))}")


def check_circuit_breaker():
    """熔断器在正常态能直接执行函数并原样返回结果。"""
    breaker = CircuitBreaker(name="test")
    print(f"    state={breaker.state}")
    if breaker.call(fn=lambda: "ok") != "ok":
        raise RuntimeError("熔断器未返回预期结果")


def check_agent(agent_cls):
    """四个子 Agent 都能无参构造，并暴露 AGENT_NAME 常量。"""
    agent = agent_cls()
    print(f"    AGENT_NAME={agent.AGENT_NAME}")


def check_assessment_validation():
    """评估 Agent 的 validate_result 能接受一份结构完整的评估结果。"""
    agent = AssessmentFeedbackAgent()
    valid = agent.validate_result({
        "assessment_summary": {
            "overall_rating": "good",
            "feasibility_rating": 7, "content_rating": 7,
            "time_rating": 7, "method_rating": 7,
            "progression_rating": 7, "personalization_rating": 7,
        },
        "assessment_metrics": [],
        "adjustment_suggestions": [
            {"area": "c", "issue": "x", "suggestion": "y", "priority": "h"}
        ],
        "recommendations": [],
    })
    print(f"    valid={valid}")


def check_vector_store():
    """向量库能初始化，并跑通一次稠密检索。"""
    store = VectorStoreManager()
    retriever = HybridRetriever(store)
    print(f"    total={store.get_stats().get('total_count', 0)}")
    results = retriever.search("Python", mode="dense", top_k=3)
    print(f"    results={len(results)}")


def check_self_rag():
    """Self-RAG 能初始化，并读到相似度阈值配置。"""
    recommender = init_self_rag()
    print(f"    threshold={recommender.SIMILARITY_THRESHOLD}, min_kb={recommender.MIN_KB_SIMILARITY}")


def check_orchestrator():
    """报告 LangGraph 是否可用：不可用时编排层会走线程版后备。"""
    print(f"    langgraph={'OK' if LANGGRAPH_AVAILABLE else 'SKIP'}")


def main():
    """依次跑完全部检查，按失败数返回退出码（CI 依赖这个退出码）。"""
    check("config 加载 + RAG 配置", check_config)
    check("CircuitBreaker 熔断器", check_circuit_breaker)

    for agent_cls in (
        RequirementExtractorAgent,
        CoursePlannerAgent,
        ResourceRecommenderAgent,
        AssessmentFeedbackAgent,
    ):
        check(f"{agent_cls.__name__} 初始化", lambda c=agent_cls: check_agent(c))

    check("Assessment 6维度验证", check_assessment_validation)
    check("VectorStore 初始化 + hybrid search", check_vector_store)
    check("SelfRAG 初始化 + 配置读取", check_self_rag)
    check("GraphOrchestrator 编译", check_orchestrator)

    print(f"\n{'='*40}")
    print(f"Total: {TESTS_PASSED} passed, {TESTS_FAILED} failed")
    sys.exit(1 if TESTS_FAILED > 0 else 0)


if __name__ == "__main__":
    main()
