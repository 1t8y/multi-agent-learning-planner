# 代码精读与面试准备（L1 / L2 / L3 分级）

> 适用项目：multi-agent 学习资源推荐系统（后端 `backend/src`）
> 配套文档：`ARCHITECTURE.md`（设计）、`PROJECT_LAYOUT.md`（目录）、`RETRIEVAL_EVAL.md`（评测）
> 用法：遮住答案自测；答不出的回到文中标注的「文件:行号」重读源码。

---

## 0. 分级定义

| 级别 | 标准 | 面试中的典型表现 |
|---|---|---|
| **L1 能讲** | 说清模块职责、上下游、设计理由，不需要看代码 | "介绍一下你们项目的 RAG 链路" / "为什么这么分层" |
| **L2 能改** | 知道改哪个文件哪一行、改了会影响什么，能完成小改动 | "如果让你加一路召回 / 换分词器 / 调阈值，怎么改" |
| **L3 能复现** | 脱稿写出核心代码或流程，能逐行解释 | "手写 RRF / 画一下 LangGraph 图 / 写一下检索 8 步" |

建议顺序：先按板块过 L1 → 再过 L2（每个改动都去代码里定位一次）→ 最后只默写 L3 清单里的代码。

---

## 1. 项目全景（30 秒版）

| 层 | 目录/文件 | 一句话职责 |
|---|---|---|
| 配置 | `src/config.py`、`src/paths.py` | 配置单例（环境变量 + 默认值 + JSON）；RAG 参数都在 `get_defaults()["rag"]` |
| 存储层 | `src/memory/vector_store_core.py` | 只回答「怎么存、怎么取回原始候选」：Chroma 读写、BM25 索引、Dense/Sparse 召回 |
| | `src/memory/model_loader.py` | Embedding / Cross-Encoder 进程内单例，本地缓存优先 |
| | `src/memory/vector_store.py` | 对外统一入口，纯 re-export |
| 检索策略层 | `src/rag/retrieval.py` | 只回答「怎么把候选组合成结果」：RRF 融合、去重、多样性、缓存 |
| | `src/rag/self_rag_recommender.py` | Self-RAG 基础流程与 `RAGState` 状态机 |
| | `src/rag/advanced_self_rag.py` | 增强版：正向查询、元数据过滤、精排、质量门控、改写闭环 |
| | `src/rag/reranker.py` | Cross-Encoder 精排与置信度门控 |
| | `src/rag/rag_quality.py` | 运行时检索质量打分与归因 |
| Agent 内核 | `src/core/base_agent.py` | 基类：LLM 调用、JSON 解析、提示词、熔断 |
| | `src/core/requirement_extractor.py` 等 4 个 | 需求提取 / 课程规划 / 资源推荐 / 评估反馈 |
| | `src/core/graph_orchestrator.py` | LangGraph 编排（extract → plan → recommend∥assess → merge） |
| 其他 | `src/tools/`、`src/feedback/`、`src/api/`、`src/utils/` | 联网补充、反馈闭环、HTTP 接口、评测指标 |

**依赖方向**：`config/utils → memory/tools → rag → feedback/core → api`。反向依赖会让导入成环。

---

## 2. 术语表（缩写全称 + 类型）

| 缩写 | 全称 | 类型 | 一句话解释 |
|---|---|---|---|
| RAG | Retrieval-Augmented Generation | 技术架构统称 | 先检索资料，再让模型基于资料生成/推荐 |
| RRF | Reciprocal Rank Fusion | 算法（融合方法） | 按名次而不是分数融合多路检索结果 |
| BM25 | Best Matching 25（Okapi BM25） | 具体检索算法 | 基于词频/逆文档频率的稀疏检索打分 |
| Dense | Dense Retrieval | 检索方式 | 向量语义相似度召回 |
| Sparse | Sparse Retrieval | 检索方式 | 关键词/词频召回（这里是 BM25） |
| ChromaDB | Chroma Database | 具体向量数据库工具 | 持久化向量库，支持元数据过滤 |
| BGE | BAAI General Embedding | 具体模型系列 | 智源开源的中文向量模型 |
| Cross-Encoder | Cross-Encoder | 模型结构类型 | 把 query 和文档拼在一起打分的精排模型 |
| LangGraph | LangGraph | 具体编排框架 | 用状态图声明 LLM 应用流程 |
| StateGraph | State Graph | 框架核心类 | 声明节点、边、条件边 |
| TypedDict | Typed Dictionary | Python 类型工具 | 带类型提示的字典结构 |
| HITL | Human-in-the-Loop | 方法论术语 | 流程中插入人工审核 |
| LRU | Least Recently Used | 缓存淘汰策略 | 缓存满时淘汰最久未用的条目 |
| IDF | Inverse Document Frequency | 统计量 | 逆文档频率，词越常见权重越低 |
| KB | Knowledge Base | 概念 | 知识库 |
| LLM | Large Language Model | 概念 | 大语言模型 |
| Tavily | Tavily Search API | 具体工具/服务 | 联网搜索 API |
| jieba | jieba 中文分词 | 具体工具库 | 中文分词器 |
| MRR | Mean Reciprocal Rank | 评测指标 | 首个命中排名的倒数均值 |
| Hit@k | Hit at k | 评测指标 | 前 k 条内是否命中 |
| P@k | Precision at k | 评测指标 | 前 k 条的准确率 |

---

## 3. 板块 A：LangGraph 编排层

文件：`src/core/graph_orchestrator.py`

### 3.1 L1 问题与答案要点

**Q1：四个 Agent 是怎么串起来的？**

`StateGraph(LearningState)` 注册 5 个节点（extract / plan / recommend / assess / merge），边为 `extract → plan → (recommend ∥ assess) → merge`，merge 通过条件边决定回 plan 再生还是结束，入口是 extract。四个 Agent 实例在 `__init__` 里创建（第 116–119 行），节点函数只是调用各自的 `extract / plan / recommend / assess` 方法。

**Q2：为什么 recommend 和 assess 能并行？**

两个节点都只依赖 `plan_data`，彼此不依赖；且分别写**不同的 state key**（`resource_data` 与 `assessment_data`）。LangGraph 对无依赖的边默认并行调度，所以能缩短单次请求耗时。

**Q3：条件边为什么不能改状态？再生计数为什么放在 merge 节点里？**

LangGraph 规定条件边函数**只能读取状态、不能返回状态更新**。所以 `iteration_count` 的递增必须放在 `_node_merge` 节点内部完成（第 233–234 行），条件边 `_should_regenerate` 只读 `_need_regenerate` 和 `iteration_count` 做路由（第 264–281 行）。

**Q4：节点返回值怎么合并进状态？并行写同一个 key 会怎样？**

节点函数返回一个 dict（只含要更新的字段），LangGraph 按 key 覆盖式合并回 `LearningState`。并行节点写不同 key 不会冲突；如果两个并行节点写**同一个 key**，就需要 reducer 声明（如 `Annotated[list, operator.add]`）。本项目靠「各节点写各的 key」规避冲突——注意第 61 行注释提到 Annotated，但 `LearningState` 字段实际没用 Annotated，这是注释与实现的出入，面试可主动指出。

**Q5：MemorySaver / interrupt_after 是干什么的？HITL 落地了吗？**

`compile(enable_interrupt=True)` 时启用 `interrupt_after=["merge"]` + `MemorySaver`（内存检查点），在 merge 后暂停等人审，为 HITL 预留。默认 `enable_interrupt=False`，**前端未实现**，属于预留能力，讲项目时要如实说明。

**Q6：没有 LangGraph 时的后备是什么？**

`src/core/agent_coordinator.py` 是线程版编排；`graph_orchestrator.py` 顶部对 langgraph 做 try-import，缺失时给出警告。

### 3.2 L2 能改（改哪、怎么改）

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 加一个节点（如 query_rewrite） | `graph.add_node(...)` + 插入对应边 + `LearningState` 加字段 | 保证新节点只写自己的 key |
| 调再生阈值 / 最大轮数 | `config.py` 的 `rag` 段：`regeneration_threshold` / `max_regeneration_rounds` | 也可用环境变量 `REGENERATION_THRESHOLD` / `MAX_REGENERATION_ROUNDS` 覆盖 |
| 开启 HITL | `compile(enable_interrupt=True)` | `invoke` 会自动带 `thread_id`，依赖 `MemorySaver` |
| 改节点异常兜底 | 各 `_node_xxx` 的 `except` 分支 | 统一约定：失败返回空结构，不抛异常，保证下游还能跑 |
| 换编排实现 | 在 `graph_orchestrator` 与 `agent_coordinator` 之间切换 | 对外入口都是 `invoke(user_input)` |

### 3.3 L3 核心代码

**(a) 图构建**（第 302–338 行，面试要能默写并解释每个调用）：

```python
graph = StateGraph(LearningState)

# 注册节点
graph.add_node("extract", self._node_extract)
graph.add_node("plan", self._node_plan)
graph.add_node("recommend", self._node_recommend)
graph.add_node("assess", self._node_assess)
graph.add_node("merge", self._node_merge)

# 定义边（流转路径）
graph.add_edge("extract", "plan")
graph.add_edge("plan", "recommend")
graph.add_edge("plan", "assess")
graph.add_edge("recommend", "merge")
graph.add_edge("assess", "merge")

graph.add_conditional_edges(
    "merge",
    self._should_regenerate,
    {"regenerate": "plan", "done": END},
)

graph.set_entry_point("extract")
```

**(b) 再生计数 + 条件边**（第 218–281 行核心）：

```python
def _node_merge(self, state):
    assessment = state.get("assessment_data", {})
    summary = assessment.get("assessment_summary", {})
    avg_score = summary.get("score_average", 0)
    iteration = state.get("iteration_count", 0)

    need_regenerate = (
        avg_score > 0
        and avg_score < REGENERATION_THRESHOLD
        and iteration < MAX_REGENERATION_ROUNDS
    )
    if need_regenerate:
        iteration += 1          # 只能在节点内递增，条件边不能写状态

    return {
        "result": {...},
        "iteration_count": iteration,
        "assessment_feedback_for_regeneration": feedback_text if need_regenerate else "",
        "_need_regenerate": need_regenerate,
    }

def _should_regenerate(self, state):
    if state.get("_need_regenerate", False):
        return "regenerate"
    return "done"
```

**(c) invoke 初始状态**（第 361–374 行）：

```python
initial_state = {
    "request_id": request_id,
    "user_input": user_input,
    "requirement_data": {},
    "plan_data": {},
    "resource_data": {},
    "assessment_data": {},
    "result": {},
    "iteration_count": 0,
    "assessment_feedback_for_regeneration": "",
    "error": "",
    "user_feedback": "",
    "user_approved": False,
}
```

---

## 4. 板块 B：RAG 检索策略层

文件：`src/rag/retrieval.py`、`src/rag/advanced_self_rag.py`（继承 `self_rag_recommender.py`）

### 4.1 L1 问题与答案要点

**Q1：一次 RAG 检索依次调用哪些文件？**

`api_server.py`（POST /api/plan）→ `graph_orchestrator.py`（`_node_recommend`）→ `resource_recommender.py`（`_recommend_with_rag`）→ `advanced_self_rag.py`（`recommend` / `_search_kb`）→ `retrieval.py`（`HybridRetriever.search`）→ `vector_store_core.py`（`_dense_search` / `_sparse_search`）→ 回 `advanced_self_rag.py` 走 `reranker.py` → `rag_quality.py` → 决策与 `_merge_and_select` → 回 `resource_recommender.py` → `graph_orchestrator` merge → 返回前端。

**Q2：为什么 memory 和 rag 要分层？**

`memory` 只负责「怎么存、怎么取回一批原始候选」，`rag/retrieval.py` 只负责「怎么把候选组合成最终结果」。换存储（如换掉 Chroma）不用动排序策略，调融合策略也不用碰数据库代码。

**Q3：RRF 为什么不需要把 Dense 和 BM25 分数归一化？**

RRF 只用**名次**参与计算（`w / (k + rank)`），原始分数只用于同路内部排序，所以余弦相似度和 BM25 分不在同一量纲也没关系。

**Q4：四级过滤降级是什么？为什么降级？**

`_search_candidates` 依次尝试：① field + level + resource_types 全开 → ② 去掉 level → ③ 去掉 resource_types → ④ 全部放开。严格过滤可能返回 0 条，逐级放宽保证仍有候选，避免「有库但没结果」。

**Q5：改写策略是什么？最多几次？**

思路是围绕学习目标换模板：`topic` / `topic 入门 教程` / `topic 系统学习 推荐资源`，按 `rewrite_count` 轮换；`MAX_REWRITE_TIMES=2`（配置 `RAG_MAX_REWRITE_TIMES`）。增强版还会先用 `_clean_objective` 去掉否定句和评测措辞。

**Q6：知识库为空（kb_empty）之后去哪？**

走 `_search_web()` 调 Tavily 联网搜索；仍无结果则 `_merge_and_select` 输出空列表，`resource_recommender` 检查 `quality.passed` 后回退 `_recommend_with_llm()`（AI 生成兜底）。两种进 `kb_empty` 的路径不同：`decision=web`（知识库无覆盖）会先清空不相关的本地候选、不改写；`rewrite` 次数用尽则保留本地候选，让联网结果作为补充。

**Q7：为什么 id / rating / feedback_count 必须透传？**

前端提交反馈靠 `id` 定位资源；丢了 `id` 只能造 `resource_0` 这种假 ID，后端 `update_feedback` 找不到资源会静默失败——表现为「反馈记录成功，但评分永不更新」。

### 4.2 L2 能改（改哪、怎么改）

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 调 RRF 参数 | `retrieval.py:34-36` 的 `RRF_K` / `RRF_DENSE_WEIGHT` / `RRF_SPARSE_WEIGHT` | 改前先跑 `python -m eval.bench_retrieval` 看 Hit@1 / MRR@5 |
| 加第三路召回（如知识图谱） | `rrf_merge` 加一段循环 + `HybridRetriever.search` 加对应召回调用 | 聚合逻辑不变，按 doc_id 累加 |
| 改去重键 | `dedupe()`（第 107–120 行）：URL → 标题 | 注意空 key 处理 |
| 改多样性约束 | `diversify()` + 配置 `RAG_MIN_TYPES` | 只调整顺序，不增删条目 |
| 改缓存容量 / 键 | `DEFAULT_CACHE_SIZE`（第 39 行）/ `cache_key`（第 220–221 行） | 键里必须带 `data_version` |
| 改过滤降级链 | `advanced_self_rag.py:_search_candidates()` 的 `attempts` 列表 | 顺序决定放宽优先级 |
| 改改写模板 | `_rewrite_query()` 的 `strategies` | 次数由 `MAX_REWRITE_TIMES` 控制 |
| 改候选数 / 返回数 | 配置 `RAG_CANDIDATE_K` / `RAG_TOP_K` | 候选池必须 ≥ top_k |

### 4.3 L3 核心代码

**(a) `rrf_merge`（第 59–104 行，必背）**：

```python
def rrf_merge(dense_results, sparse_results, top_k=5, *,
              k=RRF_K, dense_weight=RRF_DENSE_WEIGHT, sparse_weight=RRF_SPARSE_WEIGHT):
    fused = {}

    # dense 侧：按名次累加权重分
    for rank, item in enumerate(dense_results, start=1):
        doc_id = item.get("id") or f"dense-{rank}"
        entry = fused.setdefault(doc_id, {**item, "rank_dense": rank, "rank_sparse": None})
        entry["rrf_score"] = entry.get("rrf_score", 0.0) + dense_weight / (k + rank)

    # sparse 侧：先算本批最大 BM25，供「只在稀疏侧出现」的文档补 similarity
    top_bm25 = max((item.get("bm25_score", 0.0) for item in sparse_results), default=1.0) or 1.0
    for rank, item in enumerate(sparse_results, start=1):
        doc_id = item.get("id") or f"sparse-{rank}"
        entry = fused.get(doc_id)
        if entry is None:
            entry = {**item, "rank_dense": None, "rank_sparse": rank,
                     "similarity": round(item.get("bm25_score", 0.0) / top_bm25, 5)}
            fused[doc_id] = entry
        else:
            entry["rank_sparse"] = rank
            entry["bm25_score"] = item.get("bm25_score")
        entry["rrf_score"] = entry.get("rrf_score", 0.0) + sparse_weight / (k + rank)

    # 收尾：分数四舍五入、按融合分排序（同分时 dense 名次靠前者优先）
    merged = list(fused.values())
    for item in merged:
        item["fused_score"] = round(item.get("rrf_score", 0.0), 6)
        item["similarity"] = round(float(item.get("similarity", 0.0) or 0.0), 5)
    merged.sort(key=lambda x: (-x.get("fused_score", 0.0),
                               x.get("rank_dense") or 10 ** 6))
    return merged[:top_k]
```

核心公式：`score = Σ wᵢ / (k + rankᵢ)`。`k=60` 是平滑常数（越小头名优势越大），`w` 是两路权重。

**(b) `HybridRetriever.search` 八步（第 185–266 行）**：

```python
def search(self, query, field=None, level=None, top_k=5, mode="hybrid",
           resource_types=None, candidate_k=None, min_types=0):
    # 1. 就绪检查
    if not self.ready or not query:
        return []

    # 2. 候选池大小
    pool = max(int(candidate_k or top_k), top_k)

    # 3. 查缓存（键里带 data_version，写库后自然不命中）
    cache_key = (self.store.data_version, query, field, level, int(top_k), mode,
                 tuple(sorted(resource_types or ())), pool, int(min_types))
    cached = self._cache.get(cache_key)
    if cached is not None:
        self._stats["cache_hits"] += 1
        self._cache.move_to_end(cache_key)
        return [dict(item) for item in cached]
    self._stats["cache_misses"] += 1
    started = time.perf_counter()

    # 4. 双路召回
    dense_results = []
    if mode in ("dense", "hybrid"):
        dense_results = self.store._dense_search(query, field, level, resource_types, pool)
        self._stats["dense_calls"] += 1

    sparse_results = []
    if mode in ("sparse", "hybrid"):
        sparse_results = self.store._sparse_search(query, pool, field, level, resource_types)
        self._stats["sparse_calls"] += 1

    # 5. 融合：hybrid 用 RRF；单路各自成结果
    if mode == "hybrid":
        self._stats["hybrid_calls"] += 1
        results = rrf_merge(dense_results, sparse_results, pool,
                            k=self.RRF_K,
                            dense_weight=self.RRF_DENSE_WEIGHT,
                            sparse_weight=self.RRF_SPARSE_WEIGHT)
    elif mode == "sparse":
        results = normalize_sparse(sparse_results)
    else:
        results = dense_results

    # 6. 去重
    results = dedupe(results)[:pool]

    # 7. 多样性约束（默认关闭）
    if min_types > 0:
        results = diversify(results, min_types)
    results = results[:top_k]

    # 8. 写缓存 + 记耗时（LRU 淘汰）
    self._stats["latency_ms_total"] += (time.perf_counter() - started) * 1000
    self._cache[cache_key] = [dict(item) for item in results]
    while len(self._cache) > self.cache_size:
        self._cache.popitem(last=False)
    return results
```

**(c) 过滤降级链**（`advanced_self_rag.py:79-97`）：

```python
attempts = [
    {"field": field, "level": level, "resource_types": resource_types},
    {"field": field, "level": None, "resource_types": resource_types},
    {"field": field, "level": None, "resource_types": None},
    {"field": None, "level": None, "resource_types": None},
]
for filters in attempts:
    results = self.retriever.search(
        query=query, field=filters["field"], level=filters["level"],
        top_k=self.CANDIDATE_K, mode="hybrid",
        resource_types=filters["resource_types"],
        min_types=self.MIN_TYPES,
    )
    if results:
        return results, filters
return [], attempts[0]
```

**(d) 合成时的 id 透传**（`self_rag_recommender.py:330-345`）：

```python
resource = {
    # id 必须透传：前端提交反馈靠它定位资源，丢了就只能造 resource_0 这种假 id，
    # 后端 update_feedback 会找不到资源而静默失败
    "id": kb.get("id", ""),
    "phase": "第一阶段：基础入门",
    "type": kb.get("resource_type", "文档资料"),
    "title": kb.get("title", ""),
    "description": kb.get("description", ""),
    "duration": "2-4小时",
    "difficulty": self._map_level(kb.get("level", "intermediate")),
    "recommendation_reason": f"来自本地知识库，相似度 {sim:.2f}",
    "url": kb.get("url", ""),
    "source": "knowledge_base",
    "rating": float(kb.get("rating", 0) or 0),
    "feedback_count": int(kb.get("feedback_count", 0) or 0),
}
```

---

## 5. 板块 C：存储层（BM25 / where / data_version）

文件：`src/memory/vector_store_core.py`

### 5.1 L1 问题与答案要点

**Q1：BM25 索引怎么建？**

懒加载：首次 `_sparse_search` 发现 `_bm25_loaded=False` 时调 `_rebuild_bm25_index()`。建索引步骤：查进程内共享缓存（key 为「库标识 + v1 + 世代号」）→ 命中直接复用 → 否则 `collection.get()` 全量拉取 documents/ids/metadatas → 逐条 `_tokenize_for_bm25`（jieba 分词，回退字符级）→ `BM25Okapi(tokenized)` → 打包四元组写入 `_BM25_CACHE` → 赋值给实例并置 `_bm25_loaded=True`。

**Q2：为什么懒加载？**

Dense 模式、纯缓存命中的请求不触发建索引，省启动时间和内存；只有真正走稀疏检索才付这个成本。

**Q3：为什么全量重建、不做增量更新？**

BM25 的 IDF（逆文档频率）是全局统计，增删一条文档会改变全库所有词的权重，增量维护复杂且易错；知识库只有 60 条已审核资源，全量重建成本可忽略，正确性优先。

**Q4：失效有哪两个入口？失效做了哪几件事？**

入口：① `_invalidate()`（增删资源后由 `add_resource` / `add_resources_batch` / `seed_catalog_resources` / `reset_database` 调用）；② `_bm25_stale = True` 的 setter（兼容外部脚本手动标记）。动作：共享世代号 +1 → 清空 `_BM25_CACHE` 中该库的旧条目 → 本地 `_bm25_loaded=False`、`bm25=None`、清空本地引用 → `_bump_version()` 让检索层缓存也失效。

**Q5：`update_feedback` 为什么不动 BM25？**

它只改 metadata 里的 `rating` / `feedback_count`，文档正文没变，BM25 索引不需要重建，只需 `_bump_version()` 让查询缓存失效。区分「文档变更」和「元数据变更」是关键。

**Q6：where 过滤在 Dense 和 Sparse 两条路有什么不同？**

Dense 路把 `_build_where()` 生成的 where 子句直接传给 `collection.query(where=...)`，由 Chroma 内部过滤；Sparse 路没有 Chroma 查询，只能在 Python 循环里手动比对 `field` / `level` / `resource_types`，不匹配就 `continue`。

**Q7：`data_version` 和 `_generation` 有什么区别？**

`data_version` 是**实例级**字段，服务检索层的 LRU 查询缓存（缓存键第一项就是它）；`_generation` 是**模块级共享**的世代号，服务 BM25 的跨实例共享缓存。两者都由写操作触发失效，但作用域和服务对象不同。

**Q8：metadata 有什么限制？**

Chroma 的 metadata 只支持标量（str / int / float / bool），不支持 list。所以 `tags` 被压成逗号分隔字符串，`rating` / `feedback_count` 转成字符串；且写入键必须与 `_build_where` 读取键一致，否则过滤静默失效（不报错）。

### 5.2 L2 能改（改哪、怎么改）

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 换分词器 | `_tokenize_for_bm25()`（第 84–91 行） | 建索引和查询必须用同一个分词函数，否则分数不可比 |
| 加一个过滤字段 | `_build_where()` + `LearningResource.to_metadata()` + `_sparse_search` 的手动过滤 | 三处要同步，metadata 值必须是标量 |
| 改 BM25 索引字段 | `_rebuild_bm25_index()` 里的 `all_data["documents"]` | 目前索引 `title + "\n" + description` |
| 改缓存失效粒度 | `_bump_version()` / `_invalidate()` | 评分只 bump 版本，内容变更才重建 BM25 |
| 换检索库（如 Elasticsearch） | `memory/` 内部实现，保持 `_dense_search` / `_sparse_search` 签名 | 上层 `rag` 不需要改，这是分层价值 |

### 5.3 L3 核心代码

**(a) `_rebuild_bm25_index`（第 509–537 行）**：

```python
def _rebuild_bm25_index(self):
    if not BM25_AVAILABLE:
        return
    cache_key = (self._store_key, "v1", _generation(self._store_key))
    with _CACHE_LOCK:
        hit = _BM25_CACHE.get(cache_key)
    if hit is not None:
        self.bm25, self._bm25_docs, self._bm25_ids, self._bm25_metas = hit
        self._bm25_loaded = True
        return
    try:
        all_data = self.collection.get()
        if not all_data or not all_data["documents"]:
            self._bm25_loaded = True
            return
        tokenized = [_tokenize_for_bm25(doc) for doc in all_data["documents"]]
        bm25 = BM25Okapi(tokenized)
        payload = (bm25, list(all_data["documents"]), list(all_data["ids"] or []),
                   list(all_data["metadatas"] or []))
        with _CACHE_LOCK:
            _BM25_CACHE[cache_key] = payload
            _LOAD_STATS["bm25_builds"] += 1
        self.bm25, self._bm25_docs, self._bm25_ids, self._bm25_metas = payload
        self._bm25_loaded = True
    except Exception as e:
        print(f"[vector_store] BM25索引重建失败: {e}")
```

**(b) `_invalidate`（第 425–433 行）**：

```python
def _invalidate(self):
    """文档增删后：失效 BM25 索引，并提升数据版本号让检索缓存失效"""
    with _CACHE_LOCK:
        _bump_generation(self._store_key)
        for key in [k for k in _BM25_CACHE if k[:2] == (self._store_key, "v1")]:
            _BM25_CACHE.pop(key, None)
    self._bm25_loaded = False
    self.bm25 = None
    self._bump_version()
```

**(c) `_build_where`（第 439–451 行）**：

```python
def _build_where(self, field, level, resource_types):
    conditions = []
    if field:
        conditions.append({"field": field})
    if level:
        conditions.append({"level": level})
    if resource_types:
        conditions.append({"resource_type": {"$in": list(resource_types)}})
    if not conditions:
        return {}
    return {"$and": conditions} if len(conditions) > 1 else conditions[0]
```

**(d) Dense 路调用 where（第 453–463 行）**：

```python
where_filter = self._build_where(field, level, resource_types)
if where_filter:
    raw = self.collection.query(query_texts=[query], n_results=top_k, where=where_filter)
else:
    raw = self.collection.query(query_texts=[query], n_results=top_k)
```

**(e) Sparse 路手动过滤（第 550–562 行）**：

```python
scores = self.bm25.get_scores(_tokenize_for_bm25(query))
ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
for idx, score in ranked:
    if score <= 0:
        continue
    meta = self._bm25_metas[idx] if idx < len(self._bm25_metas) else {}
    if field and meta.get("field") != field:
        continue
    if level and meta.get("level") != level:
        continue
    if resource_types and meta.get("resource_type") not in resource_types:
        continue
```

**(f) 版本号 + 检索缓存键（`retrieval.py:220`）**：

```python
cache_key = (self.store.data_version, query, field, level, int(top_k), mode,
             tuple(sorted(resource_types or ())), pool, int(min_types))
```

写库后 `self.store.data_version += 1`（`vector_store_core.py:423`），旧键自然不再命中。

---

## 6. 板块 D：精排与质量门控

文件：`src/rag/reranker.py`、`src/rag/rag_quality.py`

### 6.1 L1 问题与答案要点

**Q1：Cross-Encoder 和 Dense 检索的 Bi-Encoder 有什么区别？**

Bi-Encoder（`BGE` 向量模型）分别编码 query 和文档，靠向量点积算相似度，可预先建库、检索快但精度有限；Cross-Encoder（`bge-reranker-base`）把 query 和文档**拼成一对**输入模型打分，精度更高但只能对候选逐个算，所以放在召回之后做精排。

**Q2：重排置信度怎么算？**

`confidence = 1 / (1 + e^(-score))`，把模型原始分（可正可负、无上界）映射到 0~1。

**Q3：置信度门控的逻辑是什么？为什么能救回负收益？**

`min_confidence > 0` 时，若首位候选的重排置信度低于阈值，说明模型对这题没有判断力，此时**保留融合顺序**（而不是按重排顺序），但仍回填 `rerank_score` / `rerank_confidence` 供质量门控使用。这样「排序端」和「质量端」解耦，在 97 题上把重排从 −0.02 的负收益翻成 +0.01。

**Q4：质量分公式和阈值？现在怎么判断「库外查询」？**

`quality_score = 0.65 × 首位绝对相关性 + 0.25 × 平均绝对相关性 + 0.10 × 元数据匹配率`
（`quality_threshold` 默认 0.55）；`grade`：≥0.72 为 high，≥阈值 medium，否则 low。
绝对相关性由 `dense_similarity`（真实余弦）与 `rerank_score`（Cross-Encoder 原始 logit）
线性校准到 0~1 后取均值，**不再用 `sigmoid(logit)`** —— logit=0 就白给 0.5，
再加元数据自证项白送 0.20，会让「知识产权法」这类库外查询也稳定拿 0.63 分通过门控。

报告额外输出 `decision`：

| decision | 判定 | 处置 |
|---|---|---|
| `web` | 两路绝对信号同时低于硬线，或 RRF 跳过融合后无候选 | 判知识库无覆盖，清空本地候选、跳过改写直接联网 |
| `rewrite` | 只有一路低于软线，或总分未过线 | 改写查询（最多 2 次），仍不达标再联网 |
| `pass` | 两路都过软线且总分达标 | 正常推荐 |

阈值标定与 RRF 前置门槛见 [ARCHITECTURE.md](./ARCHITECTURE.md) 的「库外查询识别与两级门控」。

### 6.2 L2 能改（改哪、怎么改）

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 换重排模型 | 配置 `RAG_RERANK_MODEL` | 需先下载到本地缓存，否则首次联网加载 |
| 关掉重排 | `RAG_RERANK_ENABLED=false` | 关闭后直接按融合顺序返回 |
| 开置信度门控 / 调阈值 | `RAG_RERANK_MIN_CONFIDENCE`（默认 0，即关闭） | 阈值建议用 `eval/tools` 实验确定 |
| 调质量通过线 | `RAG_QUALITY_THRESHOLD` | 影响是否触发改写重试 |
| 改质量分权重 | `rag_quality.py` 的 `evaluate()` | 0.65 / 0.25 / 0.10 三权重之和为 1 |
| 调库外识别门槛 | `RAG_RRF_MIN_DENSE_SIMILARITY` / `RAG_HARD_*` / `RAG_SOFT_*` | 改完跑 `python -m eval.test_rag_pipeline`（含库外 3 题），别只跑库内 10 题 |

### 6.3 L3 核心代码

**(a) `rerank`（第 51–82 行）**：

```python
def _confidence(self, score: float) -> float:
    return round(1.0 / (1.0 + math.exp(-float(score))), 5)

def rerank(self, query, resources, top_k=5):
    if not resources:
        return []
    self._ensure_model()
    if not self._model:
        return resources[:top_k]
    pairs = [
        (query, f"{item.get('title', '')}\n{item.get('description', '')}")
        for item in resources
    ]
    scores = self._model.predict(pairs, convert_to_numpy=True)
    annotated = [
        {
            **item,
            "rerank_score": round(float(score), 5),
            "rerank_confidence": self._confidence(float(score)),
        }
        for item, score in zip(resources, scores)
    ]
    ranked = sorted(annotated, key=lambda item: item["rerank_score"], reverse=True)
    if self.min_confidence > 0 and ranked[0]["rerank_confidence"] < self.min_confidence:
        self.last_gate_fallback = True
        return annotated[:top_k]          # 保留融合顺序
    self.last_gate_fallback = False
    return ranked[:top_k]
```

**(b) `evaluate` 质量分与决策（核心）**：

```python
scores = [self._score(item) for item in results]   # dense_similarity + rerank_score 校准；缺信号回退旧标量
top_score, avg_score = max(scores), mean(scores)

checks = []
if field:
    checks.extend(item.get("field") == field for item in results)
if level:
    checks.extend(item.get("level") == level for item in results)
if resource_types:
    checks.extend(item.get("resource_type") in resource_types for item in results)
match_ratio = sum(checks) / len(checks) if checks else 1.0
diversity = len({item.get("resource_type", "") for item in results})

quality_score = round(0.65 * top_score + 0.25 * avg_score + 0.10 * match_ratio, 4)

top_cosine, top_logit = self._absolute_signals(results)   # 真实余弦 / 重排原始 logit
hard_cos_bad = top_cosine is not None and top_cosine < self.hard_cosine
hard_logit_bad = top_logit is not None and top_logit < self.hard_logit
soft_cos_bad = top_cosine is not None and top_cosine < self.soft_cosine
soft_logit_bad = top_logit is not None and top_logit < self.soft_logit
if (top_cosine is not None and top_logit is not None
        and hard_cos_bad and hard_logit_bad):
    decision = "web"          # 两路都极低 → 知识库无覆盖，跳过改写直接联网
elif soft_cos_bad or soft_logit_bad or quality_score < self.threshold:
    decision = "rewrite"      # 单路偏弱 → 改写查询重试
else:
    decision = "pass"
passed = decision == "pass" and quality_score >= self.threshold
```

---

## 7. 板块 E：Agent 层

文件：`src/core/base_agent.py`、四个 Agent 文件

### 7.1 L1 问题与答案要点

- **四个 Agent 的职责**：RequirementExtractor（五维需求：目标/基础/每日时长/偏好/时间期望）、CoursePlanner（阶段化计划）、ResourceRecommender（调 RAG 链路出资源）、AssessmentFeedback（整体评分 + 四维评估 + 调整建议）。
- **提示词在哪**：全部写在代码里（各 Agent 的 `_get_default_prompt`），不依赖外部提示词文件；输出格式段落是硬约束，下游按该 JSON 结构解析。
- **失败兜底**：`_call_api` 失败或 JSON 解析失败时返回 `_get_default_result()`（空结构），不抛异常，保证编排层还能拿到计划和评估。
- **统一签名**：四个 Agent 对外都有 `process(输入) -> 结果`，编排器不关心内部方法名。

### 7.2 L2 能改

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 改提示词 | 对应 Agent 的 `_get_default_prompt` | 输出格式段必须与解析代码同步改 |
| 加第 5 个 Agent | 新建文件继承 `BaseAgent` + 在 `GraphOrchestrator.__init__` 实例化 + 注册节点 | 遵循「只写自己的 state key」 |
| 改重试 / 熔断 | `base_agent.py` 的调用封装 | 与 `config.py` 的 `retry_count` / `timeout` 联动 |

### 7.3 L3 说明

**这一板块不要求默写代码**。面试标准是能讲清「四个 Agent 的边界为什么这么划」「提示词与解析的耦合点在哪」「失败为什么返回空结构而不是抛异常」。真正需要复现的是编排层的图构建（板块 A）。

---

## 8. 板块 F：API 层

文件：`src/api/api_server.py`

### 8.1 L1 问题与答案要点

- **7 个接口**：`POST /api/plan`（生成规划）、`POST /api/feedback`（提交反馈）、`GET /api/resources/{id}/stats`（单资源评分）、`POST /api/resources/submit`（提交新资源）、`GET /api/resources/pending`（待审核列表）、`GET /api/stats`（业务汇总）、`GET /api/health`（健康检查）。
- **`/api/plan` 流程**：FastAPI 路由 → `orchestrator.invoke(user_input)` → 返回 `requirement_data / plan / resources / assessment / _meta`。
- **health vs stats 别混**：health 看知识库规模、缓存命中、模型加载状态（系统可用性）；stats 看资源分布、反馈统计（业务数据）。

### 8.2 L2 能改

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 加接口 | 在 `create_app()` 里加路由函数 | 沿用 `PlanRequest` / `FeedbackData` 的 Pydantic 模型风格 |
| 改请求体 | 对应 Pydantic 模型 + 前端 `utils/api.ts` | 前后端同步改 |
| 改错误返回 | 路由内 `HTTPException` | `frontend/scripts/verify-api-errors.mjs` 是回归脚本 |

### 8.3 L3 说明

路由注册是模式化代码（`@app.post(...)` + async 函数 + 异常处理），**能照着写一个新接口即可，不要求默写现有 7 个**。

---

## 9. 板块 G：反馈闭环

文件：`src/feedback/feedback_manager.py`、`src/memory/vector_store_core.py:update_feedback`

### 9.1 L1 问题与答案要点

- **闭环流程**：`POST /api/feedback` → `FeedbackManager` 落盘 `data/feedback_records.json` → `VectorStoreManager.update_feedback()` 更新 Chroma 中该资源的 `rating` / `feedback_count` → `_bump_version()` 让检索缓存失效 → 下一次查询立即可见新评分。
- **评分公式**：累计平均 `new_rating = (old_rating × old_count + rating) / (old_count + 1)`，`feedback_count` 加 1。
- **id 透传坑**：见板块 B 的 Q7——合成资源时丢 `id`，反馈会「记录成功但评分永不更新」。

### 9.2 L2 能改

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 改评分公式（如时间衰减） | `update_feedback()` 第 613 行 | 需同步调整 `feedback_count` 语义 |
| 加反馈字段 | `FeedbackManager.submit_feedback` + 落盘结构 + 接口模型 | 前端展示字段同步 |
| 加审核流程 | `feedback_manager` 的待审核队列 | 与 `/api/resources/pending` 联动 |

### 9.3 L3 核心代码

`update_feedback` 评分核心（第 608–620 行）：

```python
metadata = existing["metadatas"][0]
old_rating = float(metadata.get("rating", 0))
old_count = int(metadata.get("feedback_count", 0))

new_count = old_count + 1
new_rating = ((old_rating * old_count) + rating) / new_count

metadata["rating"] = str(round(new_rating, 2))
metadata["feedback_count"] = str(new_count)

self.collection.update(ids=[resource_id], metadatas=[metadata])
self._bump_version()      # 只让查询缓存失效，不重建 BM25
```

---

## 10. 板块 H：评测与指标

文件：`src/utils/retrieval_metrics.py`、`backend/eval/bench_retrieval.py`

### 10.1 L1 问题、指标三要素与项目结论

**指标定义（必须说明数据含义、取值范围、好坏方向）**：

| 指标 | 数据含义 | 取值范围 | 好坏方向 |
|---|---|---|---|
| `Hit@k` | 前 k 条结果中至少命中一个正确答案的题目占比 | 0 ~ 1 | **越高越好**（衡量召回） |
| `MRR@k` | 每道题首个命中排名的倒数（未命中记 0）的均值 | 0 ~ 1 | **越高越好**（衡量排名质量） |
| `P@k` | 前 k 条中命中正确答案的比例，分母固定为 k | 0 ~ 1 | **越高越好**（衡量准确率） |

**项目结论**：`eval/bench_retrieval.py` 做十档消融（Dense / Sparse / Hybrid / 加过滤 / 加多样性 / 加精排等）；重排置信度门控在 97 题上把重排收益从 −0.02 翻成 +0.01，且不增加延迟（详见 `RETRIEVAL_EVAL.md` 3.3 节）。

**为什么 P@k 分母固定为 k**：过滤后结果可能不足 k 条，若按实际返回条数做分母会抬高 P@k，导致不同档位不可比。

### 10.2 L2 能改

| 需求 | 改哪里 | 注意 |
|---|---|---|
| 加指标（如 NDCG） | `retrieval_metrics.py` 加函数 + `summarize` 注册 | 保持「一题多答案」语义 |
| 加消融档 | `eval/bench_retrieval.py` 的档位配置 | 每档只变一个变量 |
| 重跑评测 | `backend/` 下 `python -m eval.bench_retrieval` | 工作目录必须是 `backend/` |

### 10.3 L3 核心代码

`summarize`（第 39–60 行）：

```python
total = len(details)
if total == 0:
    return {}
hits = [d for d in details if d.get("rank") is not None]
return {
    "questions": total,
    "hit_at_1": round(sum(1 for d in details if d.get("rank") == 1) / total, 4),
    f"hit_at_{k}": round(len(hits) / total, 4),
    f"mrr_at_{k}": round(sum(1.0 / d["rank"] for d in hits) / total, 4),
    f"p_at_{min(k, 3)}": round(sum(d.get("precision", 0.0) for d in details) / total, 4),
    "misses": total - len(hits),
}
```

`precision_at_k`（第 25–36 行，注意分母）：

```python
acceptable = {str(i) for i in expected_ids}
top = list(retrieved_ids)[:k]
if k <= 0:
    return 0.0
return sum(1 for doc_id in top if str(doc_id) in acceptable) / k
```

---

## 11. 一页纸 L3 默写清单（面试前最后过一遍）

- [ ] **RRF**：`rrf_merge()` 公式 `Σ w/(k+rank)`、两侧循环、同分 dense 优先（`retrieval.py:59-104`）
- [ ] **LangGraph**：`StateGraph` 注册 5 节点 + 边 + 条件边 + 入口（`graph_orchestrator.py:302-338`）
- [ ] **再生语义**：计数在 merge 节点内递增，条件边只读（`218-281`）
- [ ] **检索 8 步**：就绪 → 候选池 → 缓存 → 双路召回 → 融合 → 去重 → 多样性 → 截断写缓存（`retrieval.py:185-266`）
- [ ] **过滤降级链**：四级 attempts（`advanced_self_rag.py:79-97`）
- [ ] **BM25 建/失效**：懒加载 + 共享缓存键 + `_invalidate` 四件事（`vector_store_core.py:509-537, 425-433`）
- [ ] **where 过滤**：`_build_where` + Dense 传参 / Sparse 手动比对（`439-451, 550-562`）
- [ ] **缓存失效**：`cache_key` 带 `data_version`（`retrieval.py:220`）
- [ ] **重排门控**：sigmoid 置信度 + 首位低于阈值保留融合顺序（`reranker.py:51-82`）
- [ ] **质量分**：`0.65×top + 0.25×avg + 0.10×match` + 三态 decision（`rag_quality.py:118-137`）
- [ ] **评分回写**：累计平均公式 + 只 bump 版本（`vector_store_core.py:608-620`）

---

## 12. 面试自测题速查（40 题）

| # | 问题 | 板块 | 答案位置 |
|---|---|---|---|
| 1 | 四个 Agent 怎么串起来？ | A | §3.1 Q1 |
| 2 | 为什么 recommend 和 assess 并行？ | A | §3.1 Q2 |
| 3 | 条件边为什么不能改状态？ | A | §3.1 Q3 |
| 4 | 并行节点写同一 key 会怎样？ | A | §3.1 Q4 |
| 5 | MemorySaver 干什么？HITL 落地了吗？ | A | §3.1 Q5 |
| 6 | 不用 LangGraph 的后备是什么？ | A | §3.1 Q6 |
| 7 | 加一个节点怎么加？ | A | §3.2 |
| 8 | 再生阈值在哪改？ | A | §3.2 |
| 9 | 一次 RAG 检索的文件顺序？ | B | §4.1 Q1 |
| 10 | 为什么 memory / rag 分层？ | B | §4.1 Q2 |
| 11 | RRF 为什么不用归一化？ | B | §4.1 Q3 |
| 12 | 四级过滤降级是什么？ | B | §4.1 Q4 |
| 13 | 改写策略与次数？ | B | §4.1 Q5 |
| 14 | kb_empty 之后去哪？ | B | §4.1 Q6 |
| 15 | 为什么 id 必须透传？ | B | §4.1 Q7 |
| 16 | RRF 参数在哪、怎么调？ | B | §4.2 |
| 17 | 怎么加第三路召回？ | B | §4.2 |
| 18 | 去重键怎么改？ | B | §4.2 |
| 19 | 缓存容量和键怎么改？ | B | §4.2 |
| 20 | 降级链顺序怎么调？ | B | §4.2 |
| 21 | BM25 索引怎么建？ | C | §5.1 Q1 |
| 22 | 为什么懒加载？ | C | §5.1 Q2 |
| 23 | 为什么全量重建不增量？ | C | §5.1 Q3 |
| 24 | 失效的入口和动作？ | C | §5.1 Q4 |
| 25 | update_feedback 为什么不动 BM25？ | C | §5.1 Q5 |
| 26 | where 在 dense / sparse 的差异？ | C | §5.1 Q6 |
| 27 | data_version 和 _generation 区别？ | C | §5.1 Q7 |
| 28 | metadata 有什么限制？ | C | §5.1 Q8 |
| 29 | 换分词器要改哪几处？ | C | §5.2 |
| 30 | 加过滤字段要同步哪三处？ | C | §5.2 |
| 31 | Cross-Encoder 和 Bi-Encoder 区别？ | D | §6.1 Q1 |
| 32 | 重排置信度怎么算？ | D | §6.1 Q2 |
| 33 | 门控为什么能救负收益？ | D | §6.1 Q3 |
| 34 | 质量分公式与阈值？ | D | §6.1 Q4 |
| 35 | 怎么关重排 / 开门控？ | D | §6.2 |
| 36 | 四个 Agent 的职责边界？ | E | §7.1 |
| 37 | 7 个接口与 health/stats 区别？ | F | §8.1 |
| 38 | 反馈闭环怎么走？ | G | §9.1 |
| 39 | 评分公式与为什么只 bump 版本？ | G | §9.1 / §9.3 |
| 40 | 三个指标的含义/范围/方向？ | H | §10.1 |

---

## 13. 核心结论（一句话）

**L1 讲清「每层负责什么、为什么这样分层」，L2 能定位到具体文件行号并完成小改动，L3 只需脱稿复现 RRF、图构建、检索 8 步、降级链、BM25 建/失效、重排门控这六段核心代码——其余板块讲到能改即可，不必背代码。**
