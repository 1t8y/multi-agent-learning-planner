# 🤖 多智能体学习规划助手

[![Vercel](https://img.shields.io/badge/Vercel-Deployed-black?logo=vercel)](https://ai-beige-eta.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2-ff6b35)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4-4169E1)](https://www.trychroma.com/)

> 基于 **LangGraph** 状态图编排 + **Self-RAG** 智能检索的多智能体学习规划系统。
> 从用户自然语言输入到完整的学习规划、资源推荐、评估反馈，全流程自动化。
> 已部署上线：**[ai-beige-eta.vercel.app](https://ai-beige-eta.vercel.app)**

---

## 🏗️ 系统架构

```
用户输入（自然语言）
    │
    ▼
┌─────────────────────────────────────────────────┐
│            LangGraph 状态图编排                   │
│                                                  │
│   extract → plan → recommend ∥ assess → merge   │
│                      ↑_______________|           │
│                   (评估<6分 → 自动再生)            │
└─────────────────────────────────────────────────┘
    │              │              │
    ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────────┐
│需求分析 │  │ 课程规划  │  │ 资源推荐 ∥ 评估│
│Agent   │  │ Agent    │  │ Agent  Agent  │
│LLM+关键词│  │ LLM生成  │  │ Self-RAG+LLM │
└────────┘  └──────────┘  └──────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ┌──────────┐      ┌────────────┐
              │ChromaDB  │      │ Tavily 网络 │
              │本地知识库 │      │ 搜索 (可选) │
              └──────────┘      └────────────┘
```

## ✨ 核心特性

### 🧠 多智能体协作
- **4 个专业化 Agent**：需求分析、课程规划、资源推荐、评估反馈
- **LangGraph StateGraph 编排**：声明式状态图，支持并行执行和条件再生
- **自动再生机制**：评估分数低于阈值时自动返回重新生成（最多 3 轮）

### 🔍 Self-RAG 智能检索
- **三级资源获取策略**：本地 ChromaDB 知识库 → Tavily 网络搜索 → LLM 智能生成
- **查询自动改写**：检索结果不足时自动改写查询重试（最多 2 次）
- **来源清晰标注**：每个资源标注 `knowledge_base` / `web_search` / `llm_generated`

### 📊 6 维度评估体系
- 目标可行性 · 内容合理性 · 时间安排 · 方法适配性 · 进阶逻辑 · 个性化匹配
- 评分低于阈值自动触发计划再生

### 🎨 现代 Web 界面
- React 18 + TypeScript + TailwindCSS
- Zustand 状态管理
- 实时加载动画和结果展示

### ☁️ 一键部署
- **Vercel Serverless** 架构，前端静态 + Python API 函数
- 本地开发支持完整 ChromaDB 向量检索

---

## 🚀 在线演示

**访问地址**：https://ai-beige-eta.vercel.app

输入示例：
- `我是零基础，想学习Python编程，每天能学2小时，希望一个月内能上手`
- `我想快速入门前端开发，目标是可以自己开发小项目`
- `我想在三个月内学习法考的全部内容`

---

## 📦 本地运行

### 环境要求
- Python 3.12+
- Node.js 18+
- DeepSeek API Key

### 1. 克隆项目
```bash
git clone https://github.com/1t8y/multi-agent-learning-planner.git
cd multi-agent-learning-planner
```

### 2. 安装依赖
```bash
# 后端
cd learning-planning-multi-agent
pip install -r requirements.txt

# 前端
cd ..
npm install
```

### 3. 配置 API Key
在 `learning-planning-multi-agent/` 下创建 `.env`：
```env
DEEPSEEK_API_KEY=sk-your-key-here
TAVILY_API_KEY=tvly-your-key-here   # 可选，用于网络搜索
```

### 4. 启动
```bash
# 终端 A：启动后端
cd learning-planning-multi-agent
python api_server.py                 # http://localhost:8000

# 终端 B：启动前端
npm run dev                          # http://localhost:5173
```

或者直接命令行测试：
```bash
python graph_orchestrator.py
```

---

## 🧩 项目结构

```
├── api/
│   └── plan.py                      # Vercel Serverless 函数
├── src/                             # React 前端
│   ├── components/
│   │   ├── InputSection.tsx         # 输入组件
│   │   ├── ResultSection.tsx        # 结果展示
│   │   ├── RequirementResult.tsx    # 需求分析卡片
│   │   ├── PlanResult.tsx           # 学习计划卡片
│   │   ├── ResourcesResult.tsx      # 资源推荐卡片
│   │   └── AssessmentResult.tsx     # 评估反馈卡片
│   ├── store/planStore.ts           # Zustand 状态管理
│   ├── utils/api.ts                 # API 调用封装
│   └── types/                       # TypeScript 类型
├── learning-planning-multi-agent/   # Python 后端
│   ├── graph_orchestrator.py        # LangGraph 编排器（核心）
│   ├── requirement_extractor.py     # 需求分析 Agent
│   ├── course_planner.py            # 课程规划 Agent
│   ├── resource_recommender.py      # 资源推荐 Agent
│   ├── assessment_feedback.py       # 评估反馈 Agent（6维度）
│   ├── self_rag_recommender.py      # Self-RAG 检索工作流
│   ├── vector_store.py              # ChromaDB 向量数据库管理
│   ├── web_search.py                # Tavily 网络搜索
│   ├── feedback_manager.py          # 用户反馈管理
│   ├── base_agent.py                # Agent 基类
│   ├── config.py                    # 配置管理
│   ├── api_server.py                # FastAPI 服务
│   └── agent_coordinator.py         # 传统线程版协调器（备用）
├── vercel.json                      # Vercel 部署配置
├── requirements.txt                 # Python 依赖
├── vite.config.ts
└── package.json
```

---

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| **Agent 编排** | LangGraph StateGraph（状态图 + 条件边 + 并行分支） |
| **AI 模型** | DeepSeek API（chat 模型，支持工具调用和 JSON 输出） |
| **向量数据库** | ChromaDB（本地持久化，相似度检索 + 领域过滤） |
| **网络搜索** | Tavily Search API（可选，补充知识库不覆盖的资源） |
| **后端框架** | FastAPI + Uvicorn（完整 REST API + Swagger 文档） |
| **前端框架** | React 18 + TypeScript + Vite |
| **样式** | TailwindCSS |
| **状态管理** | Zustand |
| **部署** | Vercel（前端静态 + Python Serverless） |

---

## 📊 Agent 工作流

### LangGraph 状态图

```python
graph = StateGraph(LearningState)

graph.add_node("extract", requirement_extractor)
graph.add_node("plan", course_planner)
graph.add_node("recommend", resource_recommender)   # 与 assess 并行
graph.add_node("assess", assessment_feedback)        # 与 recommend 并行
graph.add_node("merge", result_merger)

graph.add_edge("extract", "plan")
graph.add_edge("plan", "recommend")   # 并行分支
graph.add_edge("plan", "assess")      # 并行分支
graph.add_edge("recommend", "merge")
graph.add_edge("assess", "merge")
graph.add_conditional_edges("merge", should_regenerate, {
    "regenerate": "plan",   # 分数 < 6 → 重新生成
    "done": END
})

app = graph.compile()
result = app.invoke({"user_input": "..."})
```

### Self-RAG 检索流程

```
用户查询 → 构建检索Query → ChromaDB检索
                              │
                    相似度 ≥ 0.5? ──是──→ 直接推荐 ✅
                              │
                             否
                              │
                    改写Query重试(最多2次)
                              │
                    仍不足? ──是──→ Tavily网络搜索 🌐
                              │
                    仍不足? ──是──→ LLM智能生成 🤖
```

---

## 📝 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/plan` | 生成学习规划（核心接口） |
| `POST` | `/api/feedback` | 提交资源反馈 |
| `POST` | `/api/resources/submit` | 提交新资源 |
| `GET` | `/api/stats` | 系统统计信息 |
| `GET` | `/api/resources/pending` | 待审核资源列表 |

### 请求示例
```json
POST /api/plan
{ "userInput": "我是零基础，想学Python，每天2小时，一个月内上手" }
```

### 响应结构
```json
{
  "requirement_data": {
    "learning_objective": "学习Python编程",
    "current_foundation": "零基础",
    "daily_available_time": "2小时",
    "time_expectation": "短期学习"
  },
  "plan": {
    "learning_path": { "stages": [...] }
  },
  "resources": {
    "resources": [...],
    "rag_info": {
      "source_info": "知识库2个 + 网络3个",
      "kb_relevance": 0.75
    }
  },
  "assessment": {
    "assessment_summary": {
      "score_average": 7.5,
      "feasibility_rating": 8,
      "content_rating": 7,
      ...
    }
  }
}
```

---

## 🔄 更新日志

### v2.0.0 (2026-05-30)
- 🆕 **LangGraph 编排**：替换线程式协调器，支持声明式状态图、并行执行、条件再生
- 🆕 **Self-RAG 智能检索**：ChromaDB → 查询改写 → Tavily → LLM 三级策略
- 🆕 **6 维度评估**：新增进阶逻辑、个性化匹配评估维度
- 🆕 **Vercel 部署**：Serverless 架构，前端 + Python API 在线可访问
- 🆕 **前端 API 动态 URL**：开发/生产环境自适应
- 🔧 修复需求提取：LLM 主提取 + 通用正则备份
- 🔧 修复资源推荐：过滤不相关 KB 结果，智能回退 LLM 生成
- 🔧 修复再生死循环：迭代计数器放入节点函数

### v1.0.0 (2026-05-26)
- 基础多智能体架构（4 Agent + 协调器）
- React Web 界面 + FastAPI 后端
- ChromaDB 向量数据库集成
- 用户反馈闭环（好评 ≥ 2 自动入库）

---

## 📄 许可证

MIT License

---

**Built with ❤️ for learning. Deployed on [Vercel](https://ai-beige-eta.vercel.app).**
