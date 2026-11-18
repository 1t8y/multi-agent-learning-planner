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
混合召回：Dense(BGE) + BM25 ──► 绝对分数门槛 ──► RRF 融合 ──► Cross-Encoder 精排
  │
  ▼
运行时质量门控 ──┬─ pass ─────► 输出资源
                ├─ rewrite ──► 查询改写（≤2 次）──► 二次检索 ──► 仍不达标则联网
                └─ web ──────► 清空 KB 结果，跳过改写 ──► Tavily 联网 ──► LLM 兜底
```

| 组件 | 文件 | 作用 |
|---|---|---|
| 增强 Self-RAG | `src/rag/advanced_self_rag.py` | 串联过滤、召回、重排、质量门控与改写 |
| 存储与原始召回 | `src/memory/vector_store_core.py` | Chroma 读写 + BM25 索引 + Dense/Sparse 各自的候选召回 |
| 融合与排序策略 | `src/rag/retrieval.py` | RRF 融合 + 去重 + 多样性约束 + 查询缓存（`HybridRetriever`），含融合前绝对分数门槛 |
| Cross-Encoder | `src/rag/reranker.py` | `BAAI/bge-reranker-base` 精排，支持置信度门控 |
| 质量检测 | `src/rag/rag_quality.py` | 输出质量分/等级/绝对信号与 `decision`（pass / rewrite / web） |
| 模型加载 | `src/memory/model_loader.py` | Embedding / Reranker 进程内单例，本地缓存优先 |
| 检索指标 | `src/utils/retrieval_metrics.py` | Hit@k / MRR@k / P@k，支持一题多答案 |

> **存储与策略的分界**：`memory` 只回答「怎么存、怎么取回一批原始候选」，
> `rag/retrieval.py` 回答「怎么把这些候选组合成最终结果」。
> 换存储（比如换掉 Chroma）不必动排序策略，调排序策略也不必碰数据库代码。

模型：Embedding `BAAI/bge-small-zh-v1.5`，重排 `BAAI/bge-reranker-base`，均在本地推理。

**RRF 用标准倒数排名公式** `score = Σ wᵢ / (k + rankᵢ)`：只看名次，不看分数分布，因此不需要把
dense 余弦和 BM25 分数归一化。三路信息分开留痕——原始分在 `similarity` / `bm25_score`，
融合分在 `fused_score`，各路名次在 `rank_dense` / `rank_sparse`，便于排查排序问题。
公式实现在 `src/rag/retrieval.py` 的 `rrf_merge()`，参数 `RRF_K` / `RRF_DENSE_WEIGHT` /
`RRF_SPARSE_WEIGHT` 也在该模块顶部，默认 60 / 1.0 / 1.0。

**重排置信度门控**（`RAG_RERANK_MIN_CONFIDENCE`，默认关闭）：首位重排置信度低于阈值时保留融合顺序，
但仍回填 `rerank_score` / `rerank_confidence` 给质量门控用。这样排序端与质量端解耦，
在 97 题上把重排从 −0.02 的负收益翻成 +0.01，且不增加延迟。详见 [RETRIEVAL_EVAL.md](./RETRIEVAL_EVAL.md) 第 3.3 节。

### 库外查询识别与两级门控

知识库只有 AI / 编程 / 数学三个领域。旧链路的问题在于**全链路都是相对量**：Chroma 永远
返回 top-k 最近邻、RRF 只按名次融合、重排只做候选内排序，而 `sigmoid(rerank logit)` 在
logit=0 时就给 0.5，元数据匹配又白送 0.20 分 —— 「知识产权法」这类库外查询也能拿到
0.63 分并推荐出一堆 Python / 数学课程。

门控因此只看绝对信号：`dense_similarity`（真实稠密余弦）与 `rerank_score`（Cross-Encoder
原始 logit，未经 sigmoid）。质量分改为：

```
score = 0.65 × top_relevance + 0.25 × avg_relevance + 0.10 × metadata_match_ratio
```

`relevance` 是两路绝对信号线性校准到 0~1 后的均值；元数据匹配从 0.20 降权到 0.10，
因为它只证明 where 子句生效，不含任何主题信息。

两级门槛的分界（2026-11-12 标定：库内 cosine 0.2944~0.5944 / logit 0.800~0.992；
库外 cosine −0.0631~0.2184 / logit 0.004~0.281）：

| decision | 触发条件 | 处置 |
|---|---|---|
| `web` | 两路实测且 `top cosine < hard_cosine` 且 `top logit < hard_logit`；或 RRF 跳过融合后无候选 | 判定知识库无覆盖，**跳过改写**、清空不相关 KB 结果，直接联网；联网仍失败走 LLM |
| `rewrite` | 只有一路低于软线，或总分未过 `RAG_QUALITY_THRESHOLD` | 查询改写重试（最多 `RAG_MAX_REWRITE_TIMES` 次），仍不达标再联网 |
| `pass` | 两路都过软线且总分达标 | 正常推荐 |

区分依据是：**两路同时极低说明主题根本不在库里，改写只是换词；单路偏弱更可能是查询
表达不好，值得改写**。RRF 侧另有一道前置门槛：`HybridRetriever.search()` 在融合前按
`min_dense_similarity` / `min_bm25_score` 过滤候选，dense 全灭时跳过融合直接返回空
（BM25 靠「学习 / 基础 / 概念」等通用词凑出的命中不算有效命中）。该门槛默认关闭，
只由增强版 Self-RAG 显式传入，评测链路保持历史行为、Hit@1 不受影响。

`rerank_confidence` 不再回写 `similarity`：`MIN_KB_SIMILARITY` 过滤与前端展示都用真实分数。
回归保护见 `tests/test_out_of_scope_gate.py` 与 `eval/test_rag_pipeline.py` 的库外场景。
阈值不是拍脑袋定的：换 Embedding / 重排模型或增删知识库资源后，跑
`python -m eval.tools.calibrate_scope_thresholds` 重新采集两组分布并同步更新此处区间。

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
  `ragas_testset_v3.jsonl` 由 `scripts/build_testset.py` 派生，避免手改两处产生漂移。
