# 目录结构说明

> 回答三个问题：**哪个目录放什么**、**新代码该加在哪**、**命令在哪执行**。
> 运行与排障见 [OPERATIONS.md](./OPERATIONS.md)，数据流与节点设计见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 1. 一眼看全

```text
multi-agent/
├── backend/            Python 后端：Agent 内核 + RAG + HTTP 服务
├── frontend/           React + TypeScript + Vite
├── docs/               架构、运维、检索评测、开发记录、演示脚本
├── scripts/            演示素材生产（抓帧 → GIF）
├── assets/             演示 GIF
├── .github/            CI
├── README.md           项目门面
└── .gitignore
```

## 2. 后端分层

```text
backend/
├── src/
│   ├── config.py          配置单例（环境变量 + 默认值）
│   ├── paths.py           路径常量（BACKEND_ROOT / DATA_DIR / ...）
│   ├── core/              Agent 内核
│   │   ├── base_agent.py            基类：LLM 调用、JSON 解析、提示词、熔断
│   │   ├── requirement_extractor.py 需求提取（五字段 + 白名单校验）
│   │   ├── course_planner.py        课程规划（拆阶段）
│   │   ├── resource_recommender.py  资源推荐（调 RAG 链路）
│   │   ├── assessment_feedback.py   评估打分（低分触发重生成）
│   │   ├── graph_orchestrator.py    LangGraph 编排（节点 + 条件边）
│   │   └── agent_coordinator.py     线程版编排（无 LangGraph 时的后备）
│   ├── memory/            存储层：怎么存、怎么取回原始候选
│   │   ├── model_loader.py          本地模型加载（缓存优先）
│   │   ├── vector_store_core.py     Chroma 读写 + BM25 索引 + Dense/Sparse 原始召回
│   │   └── vector_store.py          对外统一入口
│   ├── rag/               检索策略层：怎么把候选组合成结果
│   │   ├── retrieval.py             RRF 融合 + 去重 + 多样性 + 查询缓存（HybridRetriever）
│   │   ├── self_rag_recommender.py  Self-RAG 主流程（改写、召回、合并、丢弃）
│   │   ├── advanced_self_rag.py     + 元数据过滤、精排、质量门控
│   │   ├── reranker.py              Cross-Encoder 精排与置信度门控
│   │   └── rag_quality.py           检索质量打分与归因
│   ├── tools/             外部能力
│   │   ├── web_search.py            联网搜索补充
│   │   └── hermes_sync.py           本地资源同步
│   ├── feedback/          反馈
│   │   └── feedback_manager.py      评分记录、统计、待审核队列
│   ├── api/               对外接口
│   │   └── api_server.py            FastAPI（7 个接口）
│   └── utils/
│       └── retrieval_metrics.py     检索指标（评测与基准共用）
├── eval/                  评测与回归（跑的实验）
│   ├── bench_retrieval.py           十档消融 + 延迟
│   ├── evaluate_ragas.py            RAGAS 四指标，支持 --resume
│   ├── evaluate.py                  Dense/Sparse/Hybrid 三路对比
│   ├── test_rag_pipeline.py         RAG 场景回归（10 条）
│   ├── test_e2e.py                  端到端冒烟
│   ├── test_modules.py              模块导入冒烟
│   └── tools/                       一次性实验：重排归因、质量门信号、门控阈值
├── scripts/               离线脚本（产数据）
│   ├── rebuild_knowledge_base.py    校验/重建 Chroma
│   ├── build_testset.py             从知识库派生评测集
│   ├── compare_ragas.py             新旧评测同题对照
│   └── download_chroma_model.py / manual_download_model.py
├── tests/                 pytest 用例（133 项）
├── data/                  知识库、评测集、反馈记录（部分被 gitignore）
└── pytest.ini
```

**依赖方向**（箭头表示「可以依赖」）：

```text
config / utils  →  memory / tools  →  rag  →  feedback / core  →  api
```

反向依赖会让导入成环，加代码前先确认自己在哪一层。

## 3. 新代码放哪（速查）

| 要做的事 | 放这里 |
|---|---|
| 新增一个 Agent（新的处理步骤） | `src/core/`，继承 `base_agent.BaseAgent` |
| 新增一种外部能力（API、命令行工具） | `src/tools/` |
| 改融合（RRF）、去重、多样性、查询缓存 | `src/rag/retrieval.py` |
| 改召回策略、精排、质量门控 | `src/rag/` 其余模块 |
| 改向量库读写、BM25 索引、Embedding、模型加载 | `src/memory/` |
| 改评分、反馈落盘、待审核队列 | `src/feedback/` |
| 加接口或改请求体 | `src/api/api_server.py` |
| 加一次评测实验 | `eval/`（一次性分析放 `eval/tools/`） |
| 加数据构建脚本 | `scripts/` |
| 加测试用例 | `tests/`（必须能离线跑，别依赖网络） |
| 改前端页面或组件 | `frontend/src/components/` |
| 改接口调用与错误文案 | `frontend/src/utils/api.ts` |

## 4. 三条硬约定

1. **跨层导入一律写全路径**：`from src.core.base_agent import BaseAgent`，
   不要写 `from base_agent import ...`（分层前的写法，现在会直接 ImportError）。
2. **路径只从 `src.paths` 取**：不要再用 `Path(__file__).parent` 自己往上数，
   不同目录深度不同，数错一级就会读不到 `data/`。
   已有 `BACKEND_ROOT` / `DATA_DIR` / `EVAL_DATA_DIR` / `KB_DATA_DIR`。
3. **脚本用 `-m` 运行**：`python -m eval.bench_retrieval`、`python -m scripts.build_testset`，
   工作目录必须是 `backend/`。直接 `python eval/bench_retrieval.py` 会因为找不到 `src` 而失败。

## 5. 命令在哪执行

| 要做的事 | 执行位置 | 命令 |
|---|---|---|
| 起后端 | `backend/` | `.\.venv-run\Scripts\python.exe -B -m src.api.api_server` |
| 跑测试 | `backend/` | `.\.venv-run\Scripts\python.exe -B -m pytest` |
| 知识库校验 | `backend/` | `python -B -m scripts.rebuild_knowledge_base --check` |
| 检索消融 | `backend/` | `python -B -m eval.bench_retrieval` |
| RAG 场景回归 | `backend/` | `python -B -m eval.test_rag_pipeline` |
| 起前端 | `frontend/` | `npm run dev` |
| 前端构建 | `frontend/` | `npm run build` |
| 接口故障回归 | `frontend/` | `npm run verify:api-errors` |
| 录制演示 / 合成 GIF | 仓库根 | `node scripts/record-demo.mjs`、`python scripts/build_demo_gif.py` |

## 6. 调整历史

- **2026-10-31（本次）**：后端从「29 个模块平铺在 `backend/` 根」重构为按职责分层
  `src/{core,memory,rag,tools,feedback,api,utils}`；评测脚本归入 `eval/`，
  离线脚本归入 `scripts/`；全部模块补中文注释。
  这次允许改代码，所以导入与路径推导都改到位了，不再有平铺时期的限制。
- **2026-10-31（前一次）**：`learning-planning-multi-agent/` → `backend/`，前端移入 `frontend/`，
  当时约束是「只改目录不改代码」，所以后端保持平铺；本次重构已解除该约束。
- `docs/DEVLOG.md` 中早于这些日期的记录沿用旧目录名，属历史快照，未改写。
