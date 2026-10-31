# 目录结构说明

> 这份文档回答两个问题：**哪个文件夹放什么**、**为什么后端没有按 `agent_core/` `memory/` `tools/` 分子目录**。
> 命令与排障见 [OPERATIONS.md](./OPERATIONS.md)，分层与数据流见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## 1. 一眼看全

```text
multi-agent/
├── backend/      Python 后端：4 个 Agent + LangGraph 编排 + 混合检索 RAG + FastAPI
├── frontend/     React + TypeScript + Vite 前端
├── docs/         架构、运维、检索评测报告、开发记录、演示脚本、本文件
├── scripts/      演示素材生产（无头浏览器抓帧 → GIF 合成）
├── assets/       演示 GIF
├── .github/      CI
├── README.md     项目门面
└── .gitignore
```

根目录只放「跨分区的东西」，不再堆代码。

## 2. 各分区职责

| 分区 | 放什么 | 不该放什么 |
|---|---|---|
| `backend/` | 全部 Python 源码、`tests/`、`tools/`、`data/`、两套 venv、`requirements*.txt`、`pytest.ini` | 前端资源、演示 GIF |
| `frontend/` | `index.html`、`src/`、`dist/`、`node_modules/`、`package.json`、`vite/ts/tailwind/postcss` 配置、`scripts/verify-api-errors.mjs` | 后端代码、Python 依赖 |
| `docs/` | 面向人的说明文档（含 `RETRIEVAL_EVAL.md` 检索评测报告） | 运行期数据 |
| `scripts/` | 只服务于「产出演示素材」的脚本 | 业务逻辑、测试 |
| `backend/data/` | 知识库 jsonl、评测集与结果、反馈记录（部分被 gitignore） | 代码 |

`frontend/scripts/verify-api-errors.mjs` 之所以在前端目录：`npm run verify:api-errors`
用相对路径 `scripts/...` 调用它，且它靠 `import.meta.url` 上溯一级找 `src/utils/api.ts`，
放在 `frontend/` 下这两个前提才同时成立。

## 3. 后端为什么是平铺的

`backend/` 下 **29 个模块全部平铺在根目录**（另有 `tests/` 14 个、`tools/` 6 个），
这是刻意保留的，不是没整理：

1. 模块之间是**顶层绝对导入**（`from config import config`、`from base_agent import BaseAgent`、
   `from requirement_extractor import RequirementExtractorAgent`），没有包名前缀。
2. `config.py` 用 `Path(__file__)` **上溯两级**定位项目根，再去找 `.env`、`config/config.json`、
   `.trae/config/hermes_sync.json`。
3. `tests/conftest.py` 把 `parent.parent` 插进 `sys.path`，`pytest.ini` 的 `testpaths = tests`
   也按这个根来解析。

把某个文件挪进一级子目录，会同时破坏 1 和 2：import 找不到模块，路径推导整体偏移一级，
`data/`、`.env` 全部指错。要维持可用就必须改 import 和路径代码——这超出了「只调整目录」的范围，
所以保留平铺。

代价是根目录文件多，补偿办法是下面这张对照表：按职责找文件，而不是按目录找。

### 参考分层 → 本项目的实际落点

| 常见分层 | 本项目文件 | 做什么 |
|---|---|---|
| 状态定义 | `graph_orchestrator.py` 内的 `AgentState`（TypedDict） | 需求、计划、资源、评分、迭代轮次的唯一载体 |
| 规划 | `requirement_extractor.py`、`course_planner.py` | 需求抽成五字段并做白名单校验；把目标拆成阶段 |
| 推理 / 决策 | `base_agent.py` | LLM 调用封装（重试、JSON 提取、提示词、指标） |
| 反思 / 校验 | `resource_recommender.py`、`assessment_feedback.py`、`rag_quality.py` | 评分低于 6 触发重规划（最多 3 轮）；检索质量门控 |
| 编排 | `graph_orchestrator.py`（LangGraph）、`agent_coordinator.py`（线程版后备） | 节点流转、条件边、迭代上限 |
| 记忆 | `vector_store.py`、`vector_store_core.py`、`data/` | 长期记忆 = 知识库向量检索；短期上下文在 state 里 |
| 工具 | `web_search.py`、`hermes_sync.py` | 库内不足时联网补充；本地资源同步 |
| 模型接入 | `base_agent.py` + `config.py` | 统一走 OpenAI 兼容接口，默认 DeepSeek，换模型只改 `.env` |
| 安全 / 风控 | `requirement_extractor.py` 的白名单校验 | 非法枚举值重置为 `null`，不直接透传给下游 |
| 对外接口 | `api_server.py` | FastAPI，7 个接口，端口默认 8001 |
| 评测 | `evaluate.py`、`evaluate_ragas.py`、`bench_retrieval.py`、`retrieval_metrics.py`、`tools/` | 十档消融、RAGAS、测试集构建 |
| 检索增强 | `self_rag_recommender.py`、`advanced_self_rag.py`、`reranker.py` | 过滤 → 召回 → 融合 → 重排 → 质量门控 |

## 4. 命令在哪执行

| 要做的事 | 执行位置 | 命令 |
|---|---|---|
| 起后端 | `backend/` | `.\.venv-run\Scripts\python.exe -B api_server.py` |
| 跑测试 | `backend/` | `.\.venv-run\Scripts\python.exe -B -m pytest` |
| 数据校验 | `backend/` | `python -B rebuild_knowledge_base.py --check` |
| 起前端 | `frontend/` | `npm run dev` |
| 前端构建 | `frontend/` | `npm run build` |
| 接口故障回归 | `frontend/` | `npm run verify:api-errors` |
| 录制演示 / 合成 GIF | 仓库根 | `node scripts/record-demo.mjs`、`python scripts/build_demo_gif.py` |

前端命令不能在仓库根执行：`package.json` 在 `frontend/`，Vite 以它为 root 解析
`index.html` 与 `@ → /src` 别名。

## 5. 目录调整历史

- 2026-10-31：`learning-planning-multi-agent/` → `backend/`；前端从根移入 `frontend/`；
  `RETRIEVAL_EVAL.md` 从后端根移入 `docs/`；`verify-api-errors.mjs` 从前端无关的根 `scripts/`
  移入 `frontend/scripts/`。**未改动任何 `.py` / `.ts` / `.tsx` 文件内容。**
- `docs/DEVLOG.md` 中早于该日期的记录仍使用旧目录名，属历史快照，未改写。
