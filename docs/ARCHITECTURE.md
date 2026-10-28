# 架构说明

> 面向想了解实现细节的读者。快速上手请看 [README](../README.md)，运维/排障看 [OPERATIONS.md](OPERATIONS.md)。

## 1. 分层

```text
┌──────────────────────────────────────────────────────────┐
│ 前端（React 18 + TypeScript + Vite + Tailwind）           │
│ 输入需求 → 展示需求/计划/资源/评估 → 提交反馈/贡献资源      │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP（默认 :8001）
┌───────────────────────────▼──────────────────────────────┐
│ API 层（FastAPI）                                          │
│ /api/plan  /api/feedback  /api/resources/*  /api/health    │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│ 编排层（LangGraph StateGraph）                             │
│ extract → plan → recommend ∥ assess → merge                │
│ 评估均分 < 6 时回到 plan 重新生成（最多 3 轮）              │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│ Agent 层（4 个）                                           │
│ 需求提取 / 课程规划 / 资源推荐（增强 Self-RAG） / 评估反馈   │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│ 检索层（BGE Embedding + ChromaDB + BM25 + RRF + 重排）     │
│ 60 条已审核资源，元数据过滤（领域/难度/类型）              │
└──────────────────────────────────────────────────────────┘
```

| Agent | 文件 | 职责 |
|---|---|---|
| RequirementExtractorAgent | `requirement_extractor.py` | 提取五维需求（目标/基础/每日时长/偏好/时间期望） |
| CoursePlannerAgent | `course_planner.py` | 生成阶段化学习计划 |
| ResourceRecommenderAgent | `resource_recommender.py` | 调用增强 Self-RAG 推荐资源 |
| AssessmentFeedbackAgent | `assessment_feedback.py` | 六维评估计划质量并给调整建议 |

四个 Agent 的系统提示词都写在代码里（`_get_default_prompt`），仓库不依赖外置提示词文件。

## 2. LangGraph 编排

```text
extract ──► plan ──► recommend ──┐
                      │          ├──► merge ──► END
                      └► assess ─┘
             ▲                     │
             └──── score < 6 ──────┘   （最多 3 轮）
```

- `recommend` 与 `assess` 并行执行，缩短单次请求耗时。
- 条件边 `should_regenerate` 依据评估均分决定是否重生成。
- `MemorySaver` 做状态持久化，为 Human-in-the-Loop 预留接口（前端未实现）。

## 3. 增强 RAG 链路

```text
用户需求
  │
  ▼
查询正向化 ──► 元数据过滤（field / level / resource_types）
  │
  ▼
混合召回：Dense(BGE) + BM25 ──► RRF 融合 ──► Cross-Encoder 精排
  │
  ▼
运行时质量检测 ──┬─ 通过 ──► 输出资源
                └─ 不通过 ──► 查询改写 / Tavily 补充 ──► 二次检索
```

| 组件 | 文件 | 作用 |
|---|---|---|
| 增强 Self-RAG | `advanced_self_rag.py` | 串联过滤、召回、重排、质量门控与改写 |
| 混合检索核心 | `vector_store_core.py` | ChromaDB + BM25 + RRF + 元数据过滤 + LRU 缓存 |
| Cross-Encoder | `reranker.py` | `BAAI/bge-reranker-base` 精排，支持置信度门控 |
| 质量检测 | `rag_quality.py` | 输出质量分/等级/信号，决定是否改写重试 |
| 模型加载 | `model_loader.py` | Embedding / Reranker 进程内单例，本地缓存优先 |
| 检索指标 | `retrieval_metrics.py` | Hit@k / MRR@k / P@k，支持一题多答案 |

模型：Embedding `BAAI/bge-small-zh-v1.5`，重排 `BAAI/bge-reranker-base`，均在本地推理。

**RRF 用标准倒数排名公式** `score = Σ wᵢ / (k + rankᵢ)`：只看名次，不看分数分布，因此不需要把
dense 余弦和 BM25 分数归一化。三路信息分开留痕——原始分在 `similarity` / `bm25_score`，
融合分在 `fused_score`，各路名次在 `rank_dense` / `rank_sparse`，便于排查排序问题。

**重排置信度门控**（`RAG_RERANK_MIN_CONFIDENCE`，默认关闭）：首位重排置信度低于阈值时保留融合顺序，
但仍回填 `rerank_score` / `rerank_confidence` 给质量门控用。这样排序端与质量端解耦，
在 97 题上把重排从 −0.02 的负收益翻成 +0.01，且不增加延迟。详见 [RETRIEVAL_EVAL.md](../learning-planning-multi-agent/RETRIEVAL_EVAL.md) 第 3.3 节。

## 4. HTTP 接口

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/plan` | 生成学习规划（需求 → 计划 → 资源 → 评估） |
| POST | `/api/feedback` | 提交资源反馈，返回 `feedback_id` |
| GET | `/api/resources/{id}/stats` | 读取单个资源的评分与反馈条数 |
| POST | `/api/resources/submit` | 提交新资源（进入待审核队列） |
| GET | `/api/resources/pending` | 待审核资源列表 |
| GET | `/api/stats` | 知识库与反馈汇总统计 |
| GET | `/api/health` | 健康检查（知识库规模、缓存命中、模型加载状态） |

`/api/health` 是健康检查，`/api/stats` 是业务汇总，两者不要混用。

## 5. 数据流与一致性

- **反馈闭环**：`POST /api/feedback` → 写 `data/feedback_records.json` → 同步更新 Chroma 中该资源的
  `rating` / `feedback_count` → 清检索缓存，下一次查询即可见新评分。
- **资源 ID 必须全程透传**：Self-RAG 合成结果时若丢掉知识库 `id`，前端只能造 `resource_0` 假 ID，
  反馈会「记录成功但评分永不更新」。因此 `id` / `rating` / `feedback_count` 三个字段在合成阶段必须保留。
- **评测集与知识库同源**：`data/evaluation/testset_queries.jsonl` 是人工维护的唯一来源，
  `ragas_testset_v3.jsonl` 由 `tools/build_testset.py` 派生，避免手改两处产生漂移。
