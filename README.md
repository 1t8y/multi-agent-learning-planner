# 多智能体学习规划助手

![Version](https://img.shields.io/badge/version-2.3.0-blue)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-ff6b35)
![RAGAS](https://img.shields.io/badge/RAGAS-0.4.3-6f42c1)

> 基于 LangGraph、Self-RAG、Hybrid Search、Cross-Encoder 重排和 RAGAS 的学习规划系统。
> 输入自然语言学习需求，输出结构化学习计划、可信学习资源和评估建议。

## 项目定位

本项目管理完整的学习规划链路：

1. 从用户输入中提取学习目标、基础、时间、偏好和时间期望。
2. 生成阶段化学习计划。
3. 从本地资源知识库检索资源。
4. 对候选资源进行交叉编码器重排。
5. 检查检索质量，质量不足时自动改写查询或联网补充。
6. 对计划、资源和执行路径进行评估。
7. 使用 RAGAS 对资源推荐链路进行离线评测。

## 系统架构

```text
用户输入
   |
   v
需求提取 Agent
   |
   v
课程规划 Agent
   |
   +----------------------+
   |                      |
   v                      v
资源推荐 Agent         评估反馈 Agent
   |                      |
   +----------+-----------+
              |
              v
          结果整合
              |
              v
        前端结果页面
```

LangGraph 状态图：

```text
extract -> plan -> recommend -> merge
               \-> assess ----^
```

当评估均分低于阈值时，可以重新进入规划和生成阶段。

## 增强 RAG 链路

```text
用户需求
  |
  v
查询正向化
  |
  v
field / level / resource_types 过滤
  |
  v
Dense + BM25 + RRF 混合召回
  |
  v
Cross-Encoder 精排
  |
  v
运行时质量检测
  |                  |
  | 通过             | 不通过
  v                  v
生成资源推荐      查询改写 / 联网补充
                     |
                     v
                  二次检索与重排
```

核心组件：

| 组件 | 文件 | 作用 |
|---|---|---|
| 增强 Self-RAG | `learning-planning-multi-agent/advanced_self_rag.py` | 串联过滤、召回、重排和质量门控 |
| Cross-Encoder | `learning-planning-multi-agent/reranker.py` | 对候选资源进行精排 |
| 质量检测 | `learning-planning-multi-agent/rag_quality.py` | 输出质量分、等级、信号和问题 |
| 混合向量库 | `learning-planning-multi-agent/vector_store.py` | Dense、BM25、RRF 和元数据过滤 |
| RAGAS 评测 | `learning-planning-multi-agent/evaluate_ragas.py` | 运行离线 RAG 质量评测 |

当前重排模型为 `BAAI/bge-reranker-base`，向量模型为 `BAAI/bge-small-zh-v1.5`。

## Agent 职责

| Agent | 职责 |
|---|---|
| RequirementExtractorAgent | 提取五维学习需求 |
| CoursePlannerAgent | 生成阶段化学习计划 |
| ResourceRecommenderAgent | 执行增强 Self-RAG 资源推荐 |
| AssessmentFeedbackAgent | 评估计划质量并给出调整建议 |

## 项目结构

```text
multi-agent/
├── src/                              # React 前端
├── package.json                      # 前端依赖和版本
├── requirements.txt                  # Vercel Serverless 最小依赖
├── learning-planning-multi-agent/
│   ├── api_server.py                 # FastAPI 入口
│   ├── graph_orchestrator.py         # LangGraph 编排器
│   ├── requirement_extractor.py      # 需求提取 Agent
│   ├── course_planner.py             # 课程规划 Agent
│   ├── resource_recommender.py       # 资源推荐 Agent
│   ├── assessment_feedback.py        # 评估反馈 Agent
│   ├── self_rag_recommender.py       # Self-RAG 基础实现
│   ├── advanced_self_rag.py          # 增强 Self-RAG 实现
│   ├── reranker.py                   # Cross-Encoder 重排
│   ├── rag_quality.py                # 运行时质量检测
│   ├── vector_store.py               # 检索兼容层
│   ├── vector_store_core.py          # ChromaDB 和混合检索核心
│   ├── evaluate_ragas.py             # RAGAS 评测入口
│   ├── test_modules.py               # 模块测试
│   ├── test_e2e.py                   # 端到端测试
│   ├── test_rag_pipeline.py          # 增强 RAG 回归测试
│   ├── requirements.txt              # 后端运行依赖
│   ├── requirements-ragas.txt        # RAGAS 隔离环境依赖
│   └── data/
│       ├── knowledge_base/           # 已审核学习资源
│       └── evaluation/               # RAGAS 测试集和结果
└── .gitignore                        # 隐私和运行文件忽略规则
```

## 本地启动

### 1. 后端

```powershell
cd learning-planning-multi-agent
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -B api_server.py
```

后端默认地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

### 2. 前端

```powershell
npm install
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:5173
```

## 环境变量

在 `learning-planning-multi-agent/.env` 中配置：

```env
DEEPSEEK_API_KEY=your_key_here
API_BASE_URL=https://api.deepseek.com/v1/chat/completions

# 可选，用于本地知识库不足时补充搜索结果
TAVILY_API_KEY=your_key_here

# 增强 RAG 参数
RAG_CANDIDATE_K=10
RAG_TOP_K=5
RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=BAAI/bge-reranker-base
RAG_QUALITY_THRESHOLD=0.55
```

`.env`、`.venv`、模型缓存、ChromaDB、反馈记录和资源提交记录均已加入 `.gitignore`。

## 测试

后端模块测试：

```powershell
cd learning-planning-multi-agent
python -B test_modules.py
```

端到端测试：

```powershell
python -B test_e2e.py
```

增强 RAG 回归：

```powershell
python -B test_rag_pipeline.py
```

前端构建：

```powershell
npm.cmd run build
```

## RAGAS 评测

RAGAS 使用独立环境，避免影响后端运行依赖：

```powershell
cd learning-planning-multi-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ragas.txt
.\.venv\Scripts\python.exe -B evaluate_ragas.py --top-k 5 --mode hybrid --ragas --output data\evaluation\ragas_results_k5.csv
```

最近一次 30 条测试结果：

| 指标 | 数值 |
|---|---:|
| Hit@1 | 0.9333 |
| Hit@5 | 1.0000 |
| MRR@5 | 0.9611 |
| Faithfulness | 0.9430 |
| Answer Relevancy | 0.5419 |
| Context Precision | 0.9611 |
| Context Recall | 0.9833 |

## 隐私说明

- API Key 只存放在本地 `.env`，不会进入仓库。
- 向量嵌入和 Cross-Encoder 重排在本地执行。
- DeepSeek 只接收完成学习规划和评估所需的文本请求。
- RAGAS 会把评测问题、上下文、回答和参考答案发送给配置的 LLM。
- 用户反馈、资源提交、ChromaDB 和本地虚拟环境均被 Git 忽略。

## 已知限制

- 首次请求需要加载嵌入模型和 Cross-Encoder，冷启动可能耗时约 20 到 30 秒。
- 热态请求主要耗时来自 DeepSeek 的需求提取、规划和评估调用。
- 当前接口为一次性响应，尚未实现流式输出。
- RAGAS 0.4.3 对旧版 LangChain 包装器有弃用提示，但不影响当前评测结果。

## 版本记录

### v2.3.0 | 2026-09-28

- 新增增强 Self-RAG、Cross-Encoder 重排和运行时 RAG 质量检测。
- 增加 `field`、`level`、`resource_types` 组合过滤。
- 接入 RAGAS 0.4.3 和独立评测环境。
- 增加增强 RAG 回归测试和前端质量展示。

### v2.2.0 | 2026-06-01

- 加入 Hybrid Search、CRAG、中文 Embedding、配置外部化和熔断器。
- 增加请求追踪和检索量化脚本。

### v2.0.0 | 2026-05-30

- 引入 LangGraph 编排、Self-RAG 和六维评估。

### v1.0.0 | 2026-05-26

- 完成 React 前端、FastAPI 后端和 LangGraph 多 Agent 编排。
- 集成 ChromaDB、混合检索和反馈闭环。

## License

尚未指定。
