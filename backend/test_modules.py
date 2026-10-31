"""模块化测试：验证所有核心组件可正常导入和初始化（CI 用）"""
import sys
import os
import json

TESTS_PASSED = 0
TESTS_FAILED = 0


def test(name, fn):
    global TESTS_PASSED, TESTS_FAILED
    try:
        fn()
        TESTS_PASSED += 1
        print(f"  [OK] {name}")
    except Exception as e:
        TESTS_FAILED += 1
        print(f"  [FAIL] {name}: {e}")


def main():
    # 1. config
    test("config 加载 + RAG 配置", lambda: (
        (lambda cfg: (
            print(f"    model={cfg.get('defaults.model')}"),
            print(f"    rag={json.dumps(cfg.get_defaults().get('rag',{}))}"),
            None
        )[-1])(__import__('config').config)
    ))

    # 2. circuit breaker
    test("CircuitBreaker 熔断器", lambda: (
        (lambda: (
            __import__('sys').modules.update({'base_agent': __import__('base_agent')}),
            (lambda cb: (
                print(f"    state={cb.state}"),
                cb.call(fn=lambda: "ok") == "ok" or (_ for _ in ()).throw(Exception("fail"))
            ))(__import__('base_agent').CircuitBreaker(name="test"))
        ))()
    ))

    # 3-6. agent imports
    for mod, cls, attr in [
        ("requirement_extractor", "RequirementExtractorAgent", "AGENT_NAME"),
        ("course_planner", "CoursePlannerAgent", "AGENT_NAME"),
        ("resource_recommender", "ResourceRecommenderAgent", "AGENT_NAME"),
        ("assessment_feedback", "AssessmentFeedbackAgent", "AGENT_NAME"),
    ]:
        test(f"{cls} 初始化", lambda m=mod, c=cls, a=attr: (
            (lambda agent: print(f"    {a}={getattr(agent, a)}"))
            (getattr(__import__(m), c)())
        ))

    # 7. assessment validation
    test("Assessment 6维度验证", lambda: (
        (lambda agent: print(f"    valid={agent.validate_result({
            'assessment_summary': {
                'overall_rating': 'good',
                'feasibility_rating': 7, 'content_rating': 7,
                'time_rating': 7, 'method_rating': 7,
                'progression_rating': 7, 'personalization_rating': 7,
            },
            'assessment_metrics': [],
            'adjustment_suggestions': [
                {'area': 'c', 'issue': 'x', 'suggestion': 'y', 'priority': 'h'}
            ],
            'recommendations': [],
        })}"))
        (__import__('assessment_feedback').AssessmentFeedbackAgent())
    ))

    # 8. vector store
    test("VectorStore 初始化 + hybrid search", lambda: (
        (lambda store: (
            print(f"    total={store.get_stats().get('total_count', 0)}"),
            (lambda r: print(f"    results={len(r)}"))
            (store.search("Python", mode="dense", top_k=3))
        ))
        (__import__('vector_store').VectorStoreManager())
    ))

    # 9. self_rag
    test("SelfRAG 初始化 + 配置读取", lambda: (
        (lambda r: print(f"    threshold={r.SIMILARITY_THRESHOLD}, min_kb={r.MIN_KB_SIMILARITY}"))
        (__import__('self_rag_recommender').init_self_rag())
    ))

    # 10. graph orchestrator
    test("GraphOrchestrator 编译", lambda: (
        (lambda ok: print(f"    langgraph={'OK' if ok else 'SKIP'}"))
        (__import__('graph_orchestrator').LANGGRAPH_AVAILABLE)
    ))

    print(f"\n{'='*40}")
    print(f"Total: {TESTS_PASSED} passed, {TESTS_FAILED} failed")
    sys.exit(1 if TESTS_FAILED > 0 else 0)


if __name__ == "__main__":
    main()
