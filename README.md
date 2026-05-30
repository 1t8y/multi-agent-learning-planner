# 多智能体学习规划助手

## 项目介绍

这是一个基于多智能体架构的智能学习规划系统，通过多个专业化Agent协同工作，为用户提供个性化的学习路径规划、资源推荐和效果评估服务。

### 核心特性

- 🤖 **多智能体协作**：4个专业化子Agent + 1个协调器
- 📊 **动态规划**：根据用户时间期望生成不同深度的学习路径
- 🔗 **状态同步**：与Hermes Kanban实时同步任务状态
- 📝 **结构化输出**：JSON格式的结构化数据，易于程序处理
- 💻 **友好交互**：命令行交互界面，即装即用
- 🎨 **Web界面**：提供React前端界面

## 功能列表

### 1. 需求分析
- 从用户自然语言输入中提取结构化学习需求
- 支持提取：学习目标、现有基础、每日可用时间、学习偏好、时间期望
- 智能验证和清理提取结果

### 2. 学习规划
- 基于需求生成个性化学习计划
- 根据时间期望动态调整阶段数量和内容深度
- 提供分阶段的学习路径和里程碑

### 3. 资源推荐
- 根据学习计划和阶段推荐匹配的学习资源
- 支持多种资源类型：视频教程、文字教程、实战项目、文档资料
- 提供资源难度和推荐理由

### 4. 评估反馈
- 对学习计划进行全面评估
- 提供多维度评分：可行性、内容、时间、方法
- 生成阶段性评估指标和调整建议

### 5. Hermes集成
- 自动同步任务状态到Hermes Kanban
- 支持claim + complete工作流程
- 实时跟踪各Agent执行状态

## 技术栈

### 后端技术

| 技术 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 核心开发语言 |
| DeepSeek API | v1 | AI模型服务 |
| python-dotenv | 1.0.0+ | 环境变量管理 |
| requests | 2.31.0+ | HTTP请求库 |

### 前端技术

| 技术 | 说明 |
|------|------|
| React | 前端框架 |
| TypeScript | 类型系统 |
| TailwindCSS | 样式框架 |
| Zustand | 状态管理 |
| Vite | 构建工具 |

### 外部集成

| 服务 | 说明 |
|------|------|
| Hermes | 任务看板系统 |
| Trae IDE | 开发环境 |

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户输入                             │
│  "我是零基础，想学Python，每天2小时，视频学习，一周入门"  │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    协调器 (Coordinator)                  │
│  • 调度各Agent执行顺序                                    │
│  • 处理Agent间数据传递                                    │
│  • 集成Hermes状态同步                                    │
│  • 收集性能指标                                          │
└──────────────────────┬────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   需求分析Agent   │ │   课程规划Agent  │ │   资源推荐Agent   │
│  Extractor      │ │  Planner        │ │  Recommender    │
│  - 提取学习目标  │ │  - 生成学习计划  │ │  - 推荐学习资源  │
│  - 验证输入     │ │  - 划分学习阶段  │ │  - 匹配难度    │
│  - 清理数据     │ │  - 设置里程碑    │ │  - 提供理由    │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                             ▼
                  ┌─────────────────┐
                  │  评估反馈Agent    │
                  │  Assessor       │
                  │  - 评估计划合理性 │
                  │  - 提供调整建议   │
                  │  - 生成评估指标   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   学习规划结果    │
                  │  - 需求分析      │
                  │  - 学习计划      │
                  │  - 推荐资源      │
                  │  - 评估反馈      │
                  └─────────────────┘
```

## 快速开始

### 环境要求

- Python 3.8+ 或 Node.js 18+（前端）
- DeepSeek API密钥
- Hermes CLI（可选，用于任务同步）

### 安装步骤

#### 1. 克隆项目

```bash
cd c:\ai学习
git clone <repository_url>
cd learning-planning-multi-agent
```

#### 2. 安装Python依赖

```bash
# 后端依赖
cd learning-planning-multi-agent
pip install -r requirements.txt

# 前端依赖（可选）
cd ..
npm install
```

#### 3. 配置环境变量

在后端目录创建 `.env` 文件：

```bash
# DeepSeek API配置
DEEPSEEK_API_KEY=your_api_key_here

# Hermes配置（可选）
HERMES_API_KEY=your_hermes_key_here
API_BASE_URL=https://api.deepseek.com/v1/chat/completions
```

#### 4. 配置Hermes同步（可选）

编辑 `.trae/config/hermes_sync.json`：

```json
{
  "cli_path": "hermes",
  "api_base_url": "http://127.0.0.1:8642",
  "sync_mode": "trae_to_hermes",
  "agent_task_mappings": {}
}
```

#### 5. 运行系统

**命令行版本**：
```bash
cd learning-planning-multi-agent
python agent_coordinator.py
```

**Web界面版本**：
```bash
cd c:\ai学习
npm run dev
```

### 使用示例

#### 命令行版本

```bash
# 启动系统
python agent_coordinator.py

# 输入学习需求
您: 我是零基础，想学习Python编程，每天能学2小时，喜欢看视频学习，希望一周内快速入门

# 查看结果
# 系统会输出完整的：
# - 需求分析结果
# - 学习计划（分阶段）
# - 推荐资源
# - 评估反馈

# 退出系统
您: exit
```

#### Web界面版本

1. 打开浏览器访问 `http://localhost:5173`
2. 在输入框中输入学习需求
3. 点击"生成学习规划"按钮
4. 查看生成的规划结果

## 项目结构

```
learning-planning-multi-agent/          # 后端目录
├── agent_coordinator.py          # 多智能体协调器
│   └── 负责调度各Agent、并行处理、状态同步
│
├── requirement_extractor.py     # 需求分析Agent
│   └── 从用户输入中提取结构化需求
│
├── course_planner.py            # 课程规划Agent
│   └── 基于需求生成学习计划
│
├── resource_recommender.py      # 资源推荐Agent
│   └── 为学习阶段推荐匹配资源
│
├── assessment_feedback.py        # 评估反馈Agent
│   └── 评估计划并提供建议
│
├── base_agent.py                # 基础Agent类
│   └── 提供通用功能和接口
│
├── config.py                   # 配置管理
│   └── 统一配置加载和管理
│
├── hermes_sync.py              # Hermes同步
│   └── 与Kanban状态同步
│
├── requirements.txt              # Python依赖
│
└── README.md                   # 项目文档

c:\ai学习/                       # 前端目录
├── src/
│   ├── components/            # React组件
│   │   ├── ResultCard.tsx     # 结果卡片组件
│   │   ├── ResultSection.tsx  # 结果展示区
│   │   ├── RequirementResult.tsx
│   │   ├── PlanResult.tsx
│   │   ├── ResourcesResult.tsx
│   │   ├── AssessmentResult.tsx
│   │   ├── InputSection.tsx
│   │   ├── Header.tsx
│   │   └── LoadingSpinner.tsx
│   ├── store/
│   │   └── planStore.ts       # 状态管理
│   ├── types/
│   │   └── index.ts          # 类型定义
│   ├── utils/
│   │   └── api.ts            # API工具
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts

.trae/                          # Trae配置目录
├── agents/                     # Agent提示词配置
│   ├── requirement-extractor-agent.md
│   ├── course-planner-agent.md
│   ├── resource-recommender-agent.md
│   ├── assessment-feedback-agent.md
│   └── agent_coordinator.md
│
└── config/
    └── hermes_sync.json       # Hermes同步配置
```

## 配置说明

### Agent配置文件

各Agent的提示词配置位于 `.trae/agents/` 目录：

- `requirement-extractor-agent.md` - 需求分析提示词
- `course-planner-agent.md` - 课程规划提示词
- `resource-recommender-agent.md` - 资源推荐提示词
- `assessment-feedback-agent.md` - 评估反馈提示词
- `agent_coordinator.md` - 协调器提示词

### Hermes任务映射

在每个Agent配置文件中添加：

```yaml
---
agent_name: requirement-extractor
hermes_task_id: "t_d7888e7c"
---
```

### Hermes Kanban 看板

**看板名称**：`multi-agent-learning-assistant`（多智能体学习规划助手开发）

**配置的任务**：

| 任务ID | 任务名称 | 说明 |
|--------|---------|------|
| `t_d7888e7c` | 需求分析子Agent | 提取用户学习需求 |
| `t_61df9356` | 课程规划子Agent | 生成学习计划 |
| `t_924a1cdc` | 资源推荐子Agent | 推荐学习资源 |
| `t_643f6130` | 评估反馈子Agent | 评估计划并建议 |
| `t_20d4bcff` | 主协调Agent | 协调各Agent |

### Hermes命令参考

```bash
# 查看所有看板
hermes kanban boards

# 切换到项目看板
hermes kanban boards switch multi-agent-learning-assistant

# 查看任务列表
hermes kanban list

# 查看任务详情
hermes kanban show <task_id>

# 查看任务运行历史
hermes kanban runs <task_id>

# 查看任务日志
hermes kanban log <task_id>

# 查看统计信息
hermes kanban stats
```

## API接口

### Python API

```python
from agent_coordinator import LearningPlanningCoordinator

# 初始化协调器
coordinator = LearningPlanningCoordinator(enable_hermes_sync=True)

# 处理用户请求
result = coordinator.process("你的学习需求")

# result包含：
# - requirement_data: 需求分析结果
# - plan: 学习计划
# - resources: 推荐资源
# - assessment: 评估反馈

# 获取性能指标
metrics = coordinator.get_agent_metrics()
```

## 性能指标

系统提供详细的性能监控：

```python
metrics = coordinator.get_agent_metrics()
# 输出：
# {
#   'extractor': {
#     'call_count': 5,
#     'error_count': 0,
#     'success_rate': 1.0,
#     'last_execution_time': 1.23
#   },
#   'planner': {...},
#   'recommender': {...},
#   'assessor': {...}
# }
```

## 常见问题

### 1. API调用失败

**问题**：DeepSeek API调用失败
**解决**：
- 检查 `DEEPSEEK_API_KEY` 是否正确配置
- 确认网络能够访问API服务
- 查看是否达到API调用限制

### 2. Hermes同步失败

**问题**：Hermes任务状态未更新
**解决**：
- 确认Hermes CLI已安装并可用
- 检查 `hermes_task_id` 配置是否正确
- 验证任务ID在Kanban中存在

### 3. 导入错误

**问题**：ModuleNotFoundError
**解决**：
```bash
pip install -r requirements.txt
```

### 4. 前端构建失败

**问题**：npm build失败
**解决**：
```bash
# 清理缓存
rm -rf node_modules/.vite

# 重新安装
npm install
npm run build
```

## 部署说明

### 本地部署

```bash
# 克隆项目
git clone <repo>
cd learning-planning-multi-agent

# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.example .env
# 编辑.env填入API密钥

# 运行
python agent_coordinator.py
```

### Web界面部署

```bash
# 安装前端依赖
cd c:\ai学习
npm install

# 开发模式
npm run dev

# 生产构建
npm run build

# 预览生产版本
npm run preview
```

### 生产环境

1. 使用虚拟环境隔离Python依赖
2. 配置反向代理（如Nginx）
3. 设置环境变量而非 `.env` 文件
4. 配置日志记录
5. 设置进程管理（如systemd、pm2）

### Docker部署（可选）

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "agent_coordinator.py"]
```

## 更新日志

### v1.0.0 (2026-05-26)
- 实现基础多智能体架构
- 支持需求分析、课程规划、资源推荐、评估反馈
- 集成Hermes Kanban状态同步
- 支持时间期望动态规划
- 添加React Web界面
- 统一配置管理系统

## 贡献指南

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 联系方式

- 项目主页：[GitHub Repository]
- 问题反馈：[Issues Page]

---

**使用多智能体学习规划助手，让学习更高效！** 📚✨
