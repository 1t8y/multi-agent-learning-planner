# 项目地图

## 2026-09-24（增强 RAG 全链路）

```text
learning-planning-multi-agent/
├── advanced_self_rag.py       ← 查询正向化、元数据过滤、重排和质量门控
├── reranker.py                ← Cross-Encoder 候选精排
├── rag_quality.py             ← 运行时 RAG 质量检测与问题归因
├── test_rag_pipeline.py       ← 10 个资源推荐场景回归测试
├── vector_store.py            ← 兼容层增加 resource_types 过滤
├── vector_store_core.py       ← Chroma 多字段 $and 过滤
├── resource_recommender.py    ← 传递偏好并返回质量/重排信息
├── self_rag_recommender.py    ← 优先初始化增强 Self-RAG
├── evaluate_ragas.py          ← RAGAS 离线评测入口
└── data/evaluation/
    └── ragas_results_k5.csv   ← top-k=5 完整评测结果
```

本次变化：

- 新增 `AdvancedSelfRAGRecommender`，完整串起正向查询、过滤、重排和质量门控
- Cross-Encoder 使用 `BAAI/bge-reranker-base`，推理在本机完成
- Chroma 和 BM25 支持 `field`、`level`、`resource_types` 组合过滤
- 需求中的 `learning_preference` 和 `time_expectation` 已传入 RAG
- 前端资源区展示检索质量、候选数量和 Cross-Encoder 重排状态
- RAGAS 30 条评测和增强 RAG 10 场景测试均通过

## 2026-09-24（RAGAS v2 测试集审核通过）

```text
learning-planning-multi-agent/
├── evaluate_ragas.py                ← 检索指标与 RAGAS 评测入口（新增）
├── requirements-ragas.txt           ← 隔离 RAGAS 环境依赖（新增）
├── .venv/                           ← 本地隔离评测环境（不提交）
└── data/
    └── evaluation/
        ├── ragas_testset.jsonl      ← 旧版占位测试集，保留未使用
        ├── ragas_testset_v2.jsonl   ← 30 条已审核资源推荐测试题
        └── ragas_results.csv        ← 30 条 RAGAS 评测明细（新增）
```

本次变化：

- 新增 30 条资源推荐测试题，10 条已审核学习资源各覆盖 3 题
- 每题包含 `ground_truth`、`reference_contexts` 和 `expected_source_ids`
- 全部 30 条题目的 `review_status` 已由 `pending` 更新为 `approved`
- 旧版 `ragas_testset.jsonl` 保持原样，暂不参与评测
- 新增 `evaluate_ragas.py`，默认计算 Hit@1、Hit@3、MRR@3，加 `--ragas` 后运行 RAGAS
- 新增 `requirements-ragas.txt`，RAGAS 在项目本地 `.venv` 中隔离运行
- 完整 RAGAS 结果写入 `ragas_results.csv`，API Key 仅保存在被忽略的本地 `.env`
- `config.py` 现在优先读取项目本地 `.env`，并保留旧目录结构回退

## 2026-09-23（检索与知识库修复）

```text
learning-planning-multi-agent/
├── data/
│   ├── knowledge_base/
│   │   ├── knowledge_base_spec.md    ← 学习资源字段和输入输出对齐规范
│   │   └── learning_resources.jsonl  ← 10 条已审核学习资源
│   └── evaluation/
│       └── ragas_testset.jsonl       ← RAGAS 问题占位草稿
├── vector_store_core.py              ← 原 ChromaDB 存储与检索核心
├── vector_store.py                   ← 兼容适配层，修正过滤和 RRF 字段
├── rebuild_knowledge_base.py         ← 校验或重建 ChromaDB
└── PROJECT_MAP.md
```

本次变化：

- 将原 `vector_store.py` 重命名为 `vector_store_core.py`。
- 新增兼容适配层 `vector_store.py`，其他模块导入路径不变。
- 修复 BM25 未应用 `field/level` 过滤的问题。
- 修复 RRF 合并后丢失 `type/field/level` 的问题。
- 将原始相似度保留在 `similarity`，融合排名使用 `rrf_score`。
- 四组检索验证通过：Python、机器学习、Transformer、React。

## 2026-09-23（学习资源知识库）

```text
learning-planning-multi-agent/
├── data/
│   ├── knowledge_base/
│   │   ├── knowledge_base_spec.md
│   │   └── learning_resources.jsonl
│   └── evaluation/
│       └── ragas_testset.jsonl
└── PROJECT_MAP.md
```

本次变化：

- 删除错误的知识卡和旧规范。
- 新增 10 条已审核学习资源。
- 明确知识库存放学习资源，不存放领域知识正文。
