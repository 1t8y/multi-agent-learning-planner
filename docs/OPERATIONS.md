# 运行与排障

> 快速上手看 [README](../README.md)；架构细节看 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 1. 两套 Python 环境

项目有两个互不混用的虚拟环境，这是被依赖版本逼出来的设计：

| 用途 | 目录 | 依赖文件 | 内容 |
|---|---|---|---|
| 运行 + 测试（默认） | `.venv-run` | `requirements.txt` | fastapi / langgraph / chromadb / torch / pytest，**无 ragas** |
| RAGAS 离线评测 | `.venv-ragas` | `requirements-ragas.txt` | 检索子集 + ragas / datasets / langchain，**无 langgraph / fastapi** |

不能合成一套，因为 `langchain-core` 的要求互斥：

```text
langgraph 1.2.12   → langchain-core>=1.4.7,<2
langchain 0.3.30   → langchain-core>=0.3.85,<1.0.0    ← ragas 依赖的伞包
```

`ragas 0.4.3` 本身对 langchain 系列没有版本上限，卡住上限的是它依赖的 `langchain 0.3.x`。
把 langgraph 装进评测环境，`pip` 会直接报 `ResolutionImpossible`；强行装上会得到一个
「能跑但元数据不一致」的环境，下次任何 pip 操作都会失败。

```powershell
cd learning-planning-multi-agent

# 运行环境
python -m venv .venv-run
.\.venv-run\Scripts\python.exe -m pip install -r requirements.txt

# 评测环境（只在需要重跑评测时）
python -m venv .venv-ragas
.\.venv-ragas\Scripts\python.exe -m pip install -r requirements-ragas.txt
```

## 2. 端口与地址

| 服务 | 默认端口 | 覆盖方式 |
|---|---|---|
| 后端 FastAPI | 8001 | `API_PORT=8020`（也可写进 `.env`） |
| 前端 Vite | 5173 | `npm run dev -- --port 5174` |

后端默认用 8001 而不是 8000：8000 常被本机其他服务（Docker、面板工具）占用，
按 8000 访问会打到别的服务上，返回 404 或 HTML，容易误判成"接口挂了"。

前端访问请用 `http://localhost:5173`。Vite 只监听 `localhost`（IPv6），
`http://127.0.0.1:5173` 在部分机器上会 502；后端 uvicorn 绑 `0.0.0.0`，两种写法都能连。

## 3. 环境变量

放在 `learning-planning-multi-agent/.env`（由 `.env.example` 复制）：

```env
DEEPSEEK_API_KEY=your_key_here
API_BASE_URL=https://api.deepseek.com/v1/chat/completions

# 可选：本地知识库不足时补充联网搜索
TAVILY_API_KEY=your_key_here

# 增强 RAG 参数
RAG_CANDIDATE_K=10
RAG_TOP_K=5
RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=BAAI/bge-reranker-base
RAG_QUALITY_THRESHOLD=0.55

# 重排置信度门控：首位置信度低于该值时保留融合顺序（0 = 关闭）
RAG_RERANK_MIN_CONFIDENCE=0

# 结果中最少覆盖的资源类型数（0 = 关闭）
RAG_MIN_TYPES=0
```

## 4. 测试与评测命令

```powershell
cd learning-planning-multi-agent

# 快速套件：104 项，约 2 秒，不需要模型和向量库
.\.venv-run\Scripts\python.exe -B -m pytest -m "not slow"

# 集成套件：6 项，约 20 秒，需要本地 Embedding / Cross-Encoder
.\.venv-run\Scripts\python.exe -B -m pytest -m slow

# 其他回归脚本
.\.venv-run\Scripts\python.exe -B test_modules.py       # 模块冒烟
.\.venv-run\Scripts\python.exe -B test_e2e.py           # 端到端（反馈数据写临时目录）
.\.venv-run\Scripts\python.exe -B test_rag_pipeline.py  # 增强 RAG 10 个场景

# 检索消融（十档，约 2 分钟）
.\.venv-run\Scripts\python.exe -B bench_retrieval.py

# RAGAS 全量评测（约 55 分钟，需要 DeepSeek key）
$env:HF_HUB_OFFLINE=1; $env:TRANSFORMERS_OFFLINE=1
.\.venv-ragas\Scripts\python.exe -B evaluate_ragas.py --top-k 5 --mode hybrid --ragas --workers 14 --output data\evaluation\ragas_results_v3_k5.csv
```

评测中断（断网/超时）不必重跑全量：加 `--resume` 只补跑缺失题目并回填原文件。

## 5. 常见问题

**首次启动很慢（约 15 秒）**
Embedding 与 Cross-Encoder 要加载到内存。模型已做进程内单例与本地缓存优先，
只有第一个实例慢，后续请求走内存。

**页面报「无法连接后端服务」**
后端没起，或端口不一致。检查 `http://localhost:8001/api/health` 是否 200，
以及前端是否被 `VITE_API_BASE_URL` 指到了别处。

**页面报「响应不是合法 JSON / 404」**
端口被别的服务占了。8000 上常见，换 8001 或设 `API_PORT`。

**装了依赖却 import 失败**
大概率装错了环境。跑测试要用 `.venv-run`；`.venv-ragas` 里没有 fastapi / langgraph。
`python -c "import fastapi"` 用的可能是系统 Python，不是虚拟环境里的。

**改了知识库资源后检索不到**
`data/knowledge_base/*.jsonl` 改动后必须重建向量库：
`python -B rebuild_knowledge_base.py --rebuild`，否则 Chroma 与文件不一致。
同时跑 `python -B tools/build_testset.py` 更新派生评测集。

**反馈提交成功但评分没变**
资源没有知识库 `id`（联网搜索或 LLM 生成的资源）时不会写回评分——这类资源本来就不在库里。
知识库资源的 `id` 由 Self-RAG 合成阶段透传，测试 `tests/test_feedback_loop.py` 锁住了这条链路。

**想清空本地反馈数据重来**
删 `data/feedback_records.json` 与 `data/resource_submissions.json`（都是运行时生成、已被 Git 忽略），
并重置 Chroma 中资源的 `rating` / `feedback_count`：`python -B rebuild_knowledge_base.py --rebuild`。
