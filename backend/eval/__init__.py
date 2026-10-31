"""评测与回归脚本。

- bench_retrieval   十档检索消融与延迟基准
- evaluate          Dense / Sparse / Hybrid 三路对比（兼容入口，内部复用 bench）
- evaluate_ragas    RAGAS 四指标评测，支持断点续跑
- test_rag_pipeline RAG 场景回归，逐条断言首条命中
- test_e2e          端到端调用链路冒烟
- test_modules      模块导入与基础能力冒烟

这些脚本以 `python -m eval.xxx` 的形式在 backend/ 目录下运行，
不是 pytest 用例（pytest 只收集 tests/）。
"""
