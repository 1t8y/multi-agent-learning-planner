# 多智能体学习规划助手 - 项目规范文档

> 版本: v2.2.0
> 更新日期: 2026-06-01

---

## 1. 项目概述

### 1.1 项目定位
基于 **LangGraph + Self-RAG** 的多智能体学习规划系统，从用户自然语言输入到完整的学习规划、资源推荐、评估反馈，全流程自动化。

### 1.2 核心价值
- 🤖 多智能体协作：4个专业化Agent协同工作
- 🔍 智能检索：Self-RAG + Hybrid Search 双重保障
- 📊 质量控制：6维度评估 + 自动再生机制
- ☁️ 云端部署：Vercel Serverless 一键部署

---

## 2. 架构规范

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Web 界面    │  │  API 调用   │  │   命令行交互              │  │
│  │ (React 18)  │  │  (FastAPI)  │  │ (graph_orchestrator)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      编排层 (LangGraph)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  extract → plan → recommend ∥ assess → merge            │    │
│  │                              ↑_______________|          │    │
│  │                           (score<6 → 再生，最多3轮)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  关键能力:                                                        │
│  - 声明式状态图 (StateGraph)                                     │
│  - 并行分支执行 (recommend ∥ assess)                              │
│  - 条件边控制 (conditional_edges)                                 │
│  - 状态持久化 (MemorySaver)                                      │
│  - 中断支持 (Human-in-the-Loop)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Agent 层 (4个)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ 需求分析Agent │  │ 课程规划Agent │  │ 资源推荐Agent          │  │
│  │ (Extractor)  │  │ (Planner)    │  │ (Recommender)         │  │
│  │ LLM+正则      │  │ LLM生成      │  │ Self-RAG + Hybrid     │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
│                                              │                    │
│  ┌──────────────┐                          │                    │
│  │ 评估反馈Agent │  ┌─────────────────────────┘                    │
│  │ (Assessor)   │  ▼                                              │
│  │ 6维度评分     │  ┌───────────────────────┐                      │
│  │ 自动再生触发  │  │ Self-RAG 检索流程      │                      │
│  └──────────────┘  │ KB → 改写 → Tavily →  │                      │
│                    │ LLM生成                │                      │
│                    └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        基础设施层                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  ChromaDB       │  │  Tavily API     │  │  DeepSeek API   │  │
│  │  Hybrid Search  │  │  网络搜索       │  │  LLM推理        │  │
│  │  BGE中文Embedding│  │                │  │                │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ CircuitBreaker  │  │  ConfigManager  │  │  VectorStore    │  │
│  │ 熔断器          │  │ 配置管理器       │  │ 向量存储管理器   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流规范

```
用户输入
    │
    ▼
[request_id 生成] ─────┐
    │                   │
    ▼                   │
[extract] ──→ 结构化需求 │
    │                   │
    ▼                   │
[plan] ──→ 学习计划     │
    │                   │
    ├───────────────────┼───────────────────┐
    ▼                   ▼                   │
[recommend]       [assess]              [meta 透传]
    │                   │                   │
    └─────────┬─────────┘                   │
              ▼                             │
          [merge]  ←────────────────────────┘
              │
              ├─ 评分<6? ──是──→ [iteration++] ──→ 回到plan
              │                          │
              否                         │
              ▼                          │
          [输出结果] ←────────────────────┘
              │
              ▼
          [request_id + 迭代次数]
```

---

## 3. 模块规范

### 3.1 核心模块职责

| 模块 | 文件 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| 编排器 | `graph_orchestrator.py` | 状态图编排、并行分支、条件再生 | user_input | result + _meta |
| 需求分析 | `requirement_extractor.py` | 从自然语言提取结构化需求 | user_input | requirement_data |
| 课程规划 | `course_planner.py` | 生成阶段化学习路径 | requirement_data | plan_data |
| 资源推荐 | `resource_recommender.py` | 基于需求和计划推荐资源 | requirement_data + plan_data | resource_data |
| 评估反馈 | `assessment_feedback.py` | 6维度评估 + 再生建议 | requirement_data + plan_data | assessment_data |
| Self-RAG | `self_rag_recommender.py` | 智能检索闭环 | learning_objective + foundation | resources + rag_info |
| 向量存储 | `vector_store.py` | ChromaDB + Hybrid Search | query | List[Resource] |
| 网络搜索 | `web_search.py` | Tavily 搜索 | learning_objective | List[WebResource] |
| 配置管理 | `config.py` | 单例配置、环境变量覆盖 | 无 | Config |
| 反馈管理 | `feedback_manager.py` | 用户反馈处理 | feedback | 更新向量库 |

### 3.2 接口规范

#### 3.2.1 Agent 统一接口

所有 Agent 应遵循以下接口规范：

```python
class BaseAgent:
    AGENT_NAME: str = "base_agent"
    
    def __init__(self):
        # 初始化配置、API客户端、熔断器等
        pass
    
    def validate_result(self, result: Dict) -> bool:
        # 验证输出结果格式
        pass
    
    def get_metrics(self) -> Dict:
        # 返回性能指标
        return {
            "call_count": 0,
            "error_count": 0,
            "success_rate": 1.0,
            "last_execution_time": 0.0
        }
```

#### 3.2.2 配置键规范

```python
# config.py 中定义的 RAG 配置
rag_config = {
    'similarity_threshold': 0.5,      # 检索充分阈值
    'min_kb_similarity': 0.15,        # 最低可用阈值
    'max_rewrite_times': 2,           # 最大查询改写次数
    'regeneration_threshold': 6.0,    # 计划再生阈值
    'max_regeneration_rounds': 3      # 最大再生轮数
}
```

#### 3.2.3 环境变量规范

```env
# 必需
DEEPSEEK_API_KEY=sk-xxx

# 可选
TAVILY_API_KEY=tvly-xxx
API_BASE_URL=https://api.deepseek.com/v1/chat/completions

# RAG 参数覆盖（可选）
RAG_SIMILARITY_THRESHOLD=0.5
RAG_MIN_KB_SIMILARITY=0.15
RAG_MAX_REWRITE_TIMES=2
REGENERATION_THRESHOLD=6.0
MAX_REGENERATION_ROUNDS=3
```

---

## 4. 升级路线图

### 4.1 已完成升级 (v1.0.0 → v2.3.0)

#### v1.0 → v2.0 核心升级

| 升级项 | 改动内容 | 影响 |
|--------|----------|------|
| **编排器重构** | `agent_coordinator.py` (线程) → `graph_orchestrator.py` (LangGraph) | 核心架构变更 |
| **引入 LangGraph** | StateGraph + 并行分支 + 条件边 | Agent 协作能力提升 |
| **Self-RAG 实现** | KB → 改写 → Tavily → LLM 三级策略 | 资源推荐智能化 |
| **6 维度评估** | 新增进阶逻辑、个性化匹配维度 | 计划质量可控 |
| **Vercel 部署** | Serverless 架构，线上可访问 | 商业化部署基础 |

#### v2.0 → v2.2 工程升级

| 升级项 | 改动内容 | 面试价值 |
|--------|----------|----------|
| **Hybrid Search** | Dense + BM25 + RRF | 检索优化亮点 |
| **中文 Embedding** | BGE-small-zh-v1.5 + 镜像下载 | 本土化适配 |
| **CRAG 支持** | LLM 逐文档判断 + 知识分解 | RAG 深度应用 |
| **配置外部化** | config.py 单例 + 环境变量覆盖 | 工程素养体现 |
| **熔断器** | CircuitBreaker 模式 | 系统韧性设计 |
| **请求追踪** | UUID request_id + 结构化日志 | 可观测性 |
| **评估脚本** | HR@5 / MRR / P@3 量化指标 | 可量化评估 |

#### v2.2 → v2.3 检索升级

| 升级项 | 改动内容 | 面试价值 |
|--------|----------|----------|
| **增强 Self-RAG** | 查询正向化、过滤、重排、质量门控 | RAG 全链路能力 |
| **Cross-Encoder** | BGE-reranker-base 候选精排 | 二级排序实践 |
| **RAG 质量检测** | 置信度、元数据匹配、类型多样性 | 可观测与可解释 |
| **RAGAS 评测** | 30 条资源推荐测试集和四项指标 | 量化评测闭环 |

### 4.2 推荐升级方向 (参考改进建议.md)

#### 高优先级（面试高频 + 项目适配）

- ✅ **Hybrid Search** - 已实现
- ✅ **完善评估体系** - evaluate.py 已实现基础版，可扩展测试集
- ⬜ **Human-in-the-Loop (interrupt)** - 代码已有基础，需完善前端交互
- ⬜ **CRAG 升级** - 已有 `use_llm` 参数，需完善知识分解逻辑
- ✅ **配置外部化** - 已实现
- ✅ **请求 ID + 结构化日志** - 已实现
- ✅ **熔断器** - 已实现
- ✅ **测试自动化 (CI)** - .github/workflows/test.yml 已配置

#### 中优先级

- ⬜ **Self-Consistency / ToT** - 提示工程深度应用
- ⬜ **Embedding 模型替换** - 可考虑更强中文模型
- ⬜ **Agent 注册化** - 等 Agent 超过 8-10 个时再做

---

## 5. 测试规范

### 5.1 测试文件结构

```
learning-planning-multi-agent/
├── test_modules.py       # 模块级测试（CI 用）
├── test_e2e.py           # 端到端测试
└── evaluate.py           # 检索评估脚本
```

### 5.2 测试执行

```bash
# CI 测试（快速验证所有模块可导入）
python test_modules.py

# E2E 测试（验证完整流程）
python test_e2e.py

# 检索质量评估
python evaluate.py
```

### 5.3 test_modules.py 测试覆盖

| 测试项 | 内容 |
|--------|------|
| config | 配置加载 + RAG 配置读取 |
| CircuitBreaker | 熔断器初始化 + 基本调用 |
| 4 Agent | RequirementExtractorAgent 等初始化 |
| Assessment | 6 维度验证逻辑 |
| VectorStore | 初始化 + hybrid search |
| SelfRAG | 初始化 + 配置读取 |
| GraphOrchestrator | LangGraph 编译检查 |

### 5.4 评估指标规范

```python
# evaluate.py 输出
{
  "dense": {
    "HR@5": 0.8,    # Hit Rate @ 5
    "MRR": 0.65,    # Mean Reciprocal Rank
    "P@3": 0.7      # Precision @ 3
  },
  "hybrid": {
    "HR@5": 0.9,
    "MRR": 0.75,
    "P@3": 0.83
  }
}
```

---

## 6. 代码规范

### 6.1 导入顺序

```python
# 标准库
import os
import json
import logging
from typing import Dict, Any

# 第三方库
from langgraph.graph import StateGraph

# 本地模块
from config import config
```

### 6.2 日志规范

```python
# 使用 logging 模块
logging.basicConfig(level=logging.INFO, format="[Module] %(message)s")
logger = logging.getLogger(__name__)

# 结构化日志（关键事件）
logger.info(json.dumps({
    "request_id": request_id,
    "event": "invoke_start",
    "input_preview": user_input[:80]
}, ensure_ascii=False))
```

### 6.3 错误处理

```python
# 优先 try-except + 优雅降级
try:
    result = external_api.call()
except Exception as e:
    logger.error(f"[module] 失败: {e}")
    return fallback_result  # 或空结果
```

### 6.4 类型提示

```python
from typing import TypedDict, Dict, Any, Optional, List

class LearningState(TypedDict, total=False):
    request_id: str
    user_input: str
    requirement_data: Dict[str, Any]
    # ...
```

---

## 7. 部署规范

### 7.1 本地部署

```bash
# 终端 A: 后端
cd learning-planning-multi-agent
python api_server.py  # http://localhost:8000

# 终端 B: 前端
npm run dev           # http://localhost:5173
```

### 7.2 Vercel 部署

关键配置文件：
- `vercel.json` - 路由和函数配置
- `api/plan.py` - Serverless 函数
- `requirements.txt` - Python 依赖

### 7.3 健康检查

- API 健康检查: `GET /api/stats`
- Swagger 文档: `http://localhost:8000/docs`

---

## 8. 面试要点梳理

### 8.1 架构设计

**Q: 为什么选择 LangGraph 而不是自实现协调器？**
- 声明式 vs 命令式：StateGraph 让流程更清晰
- 并行执行：`plan` 后自动并行 `recommend` 和 `assess`
- 条件边：`should_regenerate` 函数定义再生逻辑
- 状态持久化：MemorySaver 支持 Human-in-the-Loop
- 生态集成：LangChain 工具链兼容

### 8.2 RAG 设计

**Q: 你们的 RAG 有什么特点？**
- Self-RAG：自动判断何时检索、何时改写、何时 fallback
- Hybrid Search：Dense（语义）+ BM25（关键词）+ RRF 融合
- CRAG 支持：可选 LLM 逐文档判断，支持知识分解
- 三级策略：KB → Tavily → LLM 生成，确保有结果
- 不相关过滤：相似度 < 0.15 直接丢弃

**Q: 为什么用 RRF 而不是加权平均？**
- 不依赖分数归一化：dense 和 sparse 的分数分布不同
- 鲁棒性更强：对异常值不敏感
- 业界标准：TREC 等竞赛常用方法

### 8.3 工程设计

**Q: 你们做了哪些工程性优化？**
- 配置外部化：阈值、轮数统一管理，支持环境变量
- 熔断器：防止 DeepSeek/Tavily 故障级联
- 请求追踪：UUID 贯穿全链路，便于问题定位
- 结构化日志：JSON 格式输出，便于监控分析
- CI 自动化：GitHub Actions 自动跑测试

### 8.4 可观测性

**Q: 如何追踪请求执行情况？**
- 每个请求生成 `request_id`（UUID 前 8 位）
- 关键事件输出 JSON 日志（invoke_start, invoke_complete 等）
- `_meta` 字段包含：
  - `iteration_count`: 迭代次数
  - `was_regenerated`: 是否经过再生
  - `request_id`: 请求标识

---

## 9. 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v2.3.0 | 2026-09-28 | 增强 Self-RAG、Cross-Encoder、质量检测、RAGAS |
| v2.2.0 | 2026-06-01 | Hybrid Search、CRAG、中文 Embedding、配置外部化、熔断器、请求追踪 |
| v2.0.0 | 2026-05-30 | LangGraph 编排、Self-RAG、6 维度评估、Vercel 部署 |
| v1.0.0 | 2026-05-26 | 基础多智能体架构、React 界面、ChromaDB 集成 |

---

## 10. 参考资料

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [ChromaDB 官方文档](https://docs.trychroma.com/)
- [RRF 融合算法](https://plg.uwaterloo.ca/~gvcormac/cormacmackay04.pdf)
- [BGE 中文 Embedding](https://github.com/FlagOpen/FlagEmbedding)
