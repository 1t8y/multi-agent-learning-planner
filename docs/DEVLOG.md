# 开发记录

> 按时间倒序记录「当时为什么这么改」，不是功能清单。功能清单见 [README](../README.md)，
> 评测数据见 [RETRIEVAL_EVAL.md](../learning-planning-multi-agent/RETRIEVAL_EVAL.md)。
> 文末是版本里程碑。

## 2026-10-28（接入 git 历史、CI 真跑通）

本次不动业务代码，只解决「仓库推不上去、CI 没人验证过」：

- **仓库形态**：项目此前没有自己的 `.git`（外层 `job-workspace` 是个无关的大仓），
  所以把远程 `multi-agent-learning-planner` 的 `.git` 接过来，按功能点补 8 个提交，
  而不是新开一个仓库强推覆盖历史。
- **CI 从「文件存在」到「真的绿」**：两个 job 实测 23s / 17s 通过，
  日志里 `113 passed, 6 deselected in 1.54s`，与 README 徽章一致。
  推送前先用一个只装了 7 个包的 venv 模拟 CI（`pytest python-dotenv rank_bm25 jieba
  fastapi pydantic requests`），确认快速套件不依赖 torch / chromadb / sentence-transformers，
  避免出现「本地全绿、CI 装依赖装到超时」。

踩到的四个坑：

1. **换行**：仓库里是 LF、Windows 工作区是 CRLF。一开始把 `core.autocrlf` 设成 `false`，
   提交进去的全是 CRLF，`git diff` 里每个文件都是整篇重写（`-w` 之后只剩 7 行真实差异，
   才反推出是换行问题）。改成 `input` 并加 `.gitattributes`（`* text=auto`、二进制与
   `*.jsonl/*.csv` 显式声明）后，diff 恢复成真实改动。
2. **fine-grained PAT 缺 `workflow` 权限**：`git push` 被拒，
   `refusing to allow a Personal Access Token to create or update workflow`。
   这个权限只能在 GitHub token 设置里开，本地无法绕过。
3. **SSH 端口被网络挡**：`ssh -T git@github.com` 直接 `Connection refused`（22 端口不通），
   所以继续用 HTTPS + PAT，没有引入 SSH 密钥。
4. **仓库主页残留失效链接**：仓库的 `homepage` 还指向 `ai-beige-eta.vercel.app`，
   访问已经超时——正是「README 说不提供线上 demo、仓库主页却挂着一个死链接」的矛盾。
   清这个字段需要 token 的 Administration 权限，本次没开，留给仓库设置页手动处理。

顺带把三个官方 action 从 `v4`/`v5` 升到 `v7`，消掉 Node.js 20 弃用告警。

## 2026-10-28（演示素材：GIF 录制脚本 + 演示脚本）

```text
assets/demo.gif                 ← 新增：1000×625 / 60s / 16 帧 / 2.9MB
scripts/record-demo.mjs         ← 新增：CDP 驱动无头 Edge 跑真实交互并抓帧
scripts/build_demo_gif.py       ← 新增：抓帧 → GIF（时长归一、逐帧调色板）
docs/demo-script.md             ← 新增：分镜、三个实测用例、常见追问的回答
requirement_extractor.py        ← 修：LLM 抽对的学习目标被关键词残片覆盖
tests/test_requirement_defaults.py ← 新增 9 项（残片判定 + 两路合并优先级）
```

本次变化：

- **录屏用脚本而不是录屏软件**：本机没有 ffmpeg，逐帧抓图反而更可控——能精确停在被讲解的那一屏，
  帧间隔按真实耗时归一。`record-demo.mjs` 通过 CDP 输入需求、点生成、滚到各区块、打星提交反馈，
  抓到的都是真实后端响应。
- **必须用 `--headless=old`**：本机 `--headless=new` 截出来是全白图（渲染进程没真正出图），
  排查时先用最小探针确认再改主脚本。
- **GIF 三个坑**：`optimize=True` 的增量帧配 `disposal=2` 会留灰色残块；全局单张调色板会把浅靛蓝按钮
  和渐变色头压成灰块（改逐帧自适应 200 色）；时长不足 60 秒时补在最后一帧会让结尾僵住十几秒
  （改逐帧分摊）。
- **演示会写真实数据**：录制过程中提交的反馈会落进 `data/feedback_records.json` 并改资源评分，
  录之前备份、录完还原——否则下一轮录制时卡片上已经带着上一轮的星级，不像首次使用。
- **顺带修的真 bug**：合并 LLM 与关键词两路结果时，`learning_objective` 按「更长更具体」取胜，
  结果 LLM 正确抽出的「系统学习概率论与数理统计，为机器学习打底」被关键词残片
  「5小时，想系统学概率论…喜欢看文字资料」覆盖，页面上直接显示残片。
  现在关键词结果若带人称/时间/偏好修饰（`_looks_like_raw_clause`）就让位给 LLM，只在 LLM 缺失时才兜底。

## 2026-10-28（需求五字段补全 + 提示词死引用清理）

```text
learning-planning-multi-agent/
├── requirement_extractor.py    ← 五字段默认值推断、学习意图闸门、学习目标清理
├── base_agent.py               ← 删除"优先读提示词文件"逻辑，提示词只来自代码
├── course_planner.py           ┐
├── resource_recommender.py     ├ 删除 PROMPT_FILE 常量与 _get_prompt_path 覆写
├── assessment_feedback.py      ┘
├── hermes_sync.py              ← 删除只读提示词文件的 get_agent_task_id（无人调用的死方法）
└── tests/
    ├── test_requirement_defaults.py  ← 新增：10 组输入五字段非 null、时间词映射、非学习输入
    └── test_agent_prompts.py         ← 新增：提示词唯一来源、无 .trae 引用
```

本次变化：

- 时间期望补「尽快 / 马上 / 越快越好 / 突击 / 学期 / 本月内」等说法；未提及时默认「长期学习」。
- 其余字段未提及按保守默认值补齐：零基础 / 1小时 / 视频。只在识别到学习意图时生效。
- 关键词回退的学习目标清理：时间片（「三个月内」）、动词壳（「学会」「精通」）、标点残留都剥掉。
- 非学习输入（「今天天气怎么样」）不再被回退策略当成学习目标——加了 `_has_learning_intent` 闸门。

## 2026-10-28（依赖环境拆分：运行 / 评测两套）

```text
learning-planning-multi-agent/
├── requirements.txt            ← 运行+测试依赖（补 pytest，此前文档让跑测试却装不到）
├── requirements-ragas.txt      ← 评测环境依赖：检索子集 + ragas 栈，独立自包含（core 0.3.86）
├── .venv-run/                  ← 运行与测试环境（fastapi/langgraph/chromadb/torch/pytest，无 ragas）
└── .venv-ragas/                ← RAGAS 评测环境（ragas/datasets/langchain，无 langgraph/fastapi）
```

本次变化：

- 原单一 `.venv` 拆成两套：`.venv-run` 按 `requirements.txt` 新建，`.venv-ragas` 按
  `requirements-ragas.txt` 重建（原来那个 `.venv` 里 langgraph 已把 langchain-core 升到 1.7.0，
  与 langchain 0.3.x 声明的 <1.0.0 不一致，能跑但不可复现）。
- 冲突的真实来源不是清单里写的「ragas 要求 core<1.0」：ragas 0.4.3 对 langchain 系列没有版本上限，
  上限来自它依赖的 `langchain 0.3.30`（`>=0.3.85,<1.0.0`），而 `langgraph 1.2.12` 要求
  `langchain-core>=1.4.7`。两者互斥，所以评测环境必须独立、不能叠加运行依赖。
- `requirements.txt` 补 `pytest==9.1.1`：原先只有 CI 单独 `pip install pytest`，按 README 装完环境跑不了测试。
- `.gitignore` 增加 `.venv-run/`、`.venv-ragas/`。

## 2026-10-26（v2.4.0 数据扩容、架构收敛与评测闭环）

```text
learning-planning-multi-agent/
├── vector_store_core.py       ← 收敛所有检索实现：过滤 / 真 RRF / 缓存 / 去重 / 多样性
├── vector_store.py            ← 退化为纯导出层，删除运行期 monkey-patch
├── model_loader.py            ← 新增：Embedding 与 Cross-Encoder 单例加载，本地缓存优先
├── retrieval_metrics.py       ← 新增：Hit@k / MRR@k / P@k，支持一题多答案
├── bench_retrieval.py         ← 新增：六档消融与延迟基准
├── reranker.py                ← 改为走模型加载器
├── advanced_self_rag.py       ← 传递 min_types 多样性约束
├── config.py                  ← 新增 rag.min_types
├── feedback_manager.py        ← 数据目录可替换，测试不再污染生产文件
├── api_server.py              ← 新增 /api/health（知识库、缓存、模型状态）
├── test_e2e.py                ← 反馈数据写入临时目录
├── pytest.ini                 ← 新增：快速/集成分层
├── tests/                     ← 新增：64 项 pytest 测试
├── tools/build_testset.py     ← 新增：从知识库派生完整评测集
├── RETRIEVAL_EVAL.md          ← 新增：检索评测报告
└── data/
    ├── knowledge_base/learning_resources.jsonl   ← 10 → 60 条
    └── evaluation/
        ├── testset_queries.jsonl  ← 新增：67 条手写问题与期望资源
        ├── ragas_testset_v3.jsonl ← 新增：97 题完整评测集
        └── bench_retrieval.json    ← 新增：消融明细与延迟
```

本次变化：

- **数据**：知识库 10 → 60 条（AI 24 / 编程 22 / 数学 14），覆盖三档难度和四种资源类型；
  评测集 30 → 97 题，覆盖全部 60 条资源。领域只保留 `_detect_field` 能识别的三类，避免孤儿数据。
- **修复**：BM25 通路原先不应用 `field`/`level`/`resource_types` 过滤，混合检索会把越界资源带回来；
  `description` 返回时把标题重复拼了一遍；`BGEEmbeddingFunction` 缺 `embed_query`，导致稠密检索
  静默失败、整条链路退化为纯 BM25（回归测试仍是 10/10，属于假通过）。
- **融合**：原来的「RRF」实际是 `dense 分 + 经验 boost + 1/(60+rank)` 常量偏移，排序完全由 dense 主导。
  改为标准 `Σ w/(k+rank)`，原始 `similarity` / `bm25_score` 不再被覆盖，另记 `fused_score` 与两路排名。
- **架构**：`vector_store.py` 曾是运行期 monkey-patch 层，导入顺序不同则补丁失效。已合并进核心。
- **效率**：Embedding 模型、Chroma 客户端、BM25 索引、Cross-Encoder 全部进程内共享；
  `test_modules.py` 全量耗时 76s → 16s；模型加载改为本地缓存优先，消除了代理环境下的联网超时重试。
- **测试**：pytest 58 项快速 + 6 项集成；快速套件用内存假集合，1.5 秒跑完，不需要 torch 和 Chroma。
- **评测结论**：hybrid 相比单路 Hit@1 +0.06 且零未命中；过滤再加 +0.06（理想上限）；
  **重排是负收益**（Hit@1 −0.02，延迟 ×40），保留原因是质量门控依赖 `rerank_confidence`，详见
  `RETRIEVAL_EVAL.md` 第 3.3 节。

## 2026-09-24（增强 RAG 全链路）

```text
learning-planning-multi-agent/
├── advanced_self_rag.py       ← 查询正向化、元数据过滤、重排和质量门控
├── reranker.py                ← Cross-Encoder 候选精排
├── rag_quality.py             ← 运行时 RAG 质量检测与问题归因
├── test_rag_pipeline.py       ← 10 个资源推荐场景回归测试
├── vector_store.py            ← 兼容层增加 resource_types 过滤
├── vector_store_core.py       ← Chroma 多字段 $and 过滤
├── resource_recommender.py    ← 传递偏好并返回质量/重排信息
├── self_rag_recommender.py    ← 优先初始化增强 Self-RAG
├── evaluate_ragas.py          ← RAGAS 离线评测入口
└── data/evaluation/
    └── ragas_results_k5.csv   ← top-k=5 完整评测结果
```

本次变化：

- 新增 `AdvancedSelfRAGRecommender`，完整串起正向查询、过滤、重排和质量门控
- Cross-Encoder 使用 `BAAI/bge-reranker-base`，推理在本机完成
- Chroma 和 BM25 支持 `field`、`level`、`resource_types` 组合过滤
- 需求中的 `learning_preference` 和 `time_expectation` 已传入 RAG
- 前端资源区展示检索质量、候选数量和 Cross-Encoder 重排状态
- RAGAS 30 条评测和增强 RAG 10 场景测试均通过

## 2026-09-24（RAGAS v2 测试集审核通过）

```text
learning-planning-multi-agent/
├── evaluate_ragas.py                ← 检索指标与 RAGAS 评测入口（新增）
├── requirements-ragas.txt           ← 隔离 RAGAS 环境依赖（新增）
├── .venv/                           ← 当时的本地隔离评测环境（2026-10-28 拆分为 .venv-run / .venv-ragas）
└── data/
    └── evaluation/
        ├── ragas_testset.jsonl      ← 旧版占位测试集，保留未使用
        ├── ragas_testset_v2.jsonl   ← 30 条已审核资源推荐测试题
        └── ragas_results.csv        ← 30 条 RAGAS 评测明细（新增）
```

本次变化：

- 新增 30 条资源推荐测试题，10 条已审核学习资源各覆盖 3 题
- 每题包含 `ground_truth`、`reference_contexts` 和 `expected_source_ids`
- 全部 30 条题目的 `review_status` 已由 `pending` 更新为 `approved`
- 旧版 `ragas_testset.jsonl` 保持原样，暂不参与评测
- 新增 `evaluate_ragas.py`，默认计算 Hit@1、Hit@3、MRR@3，加 `--ragas` 后运行 RAGAS
- 新增 `requirements-ragas.txt`，RAGAS 在当时那个单一 `.venv` 中隔离运行（2026-10-28 已拆分为两套环境）
- 完整 RAGAS 结果写入 `ragas_results.csv`，API Key 仅保存在被忽略的本地 `.env`
- `config.py` 现在优先读取项目本地 `.env`，并保留旧目录结构回退

## 2026-09-23（检索与知识库修复）

```text
learning-planning-multi-agent/
├── data/
│   ├── knowledge_base/
│   │   ├── knowledge_base_spec.md    ← 学习资源字段和输入输出对齐规范
│   │   └── learning_resources.jsonl  ← 10 条已审核学习资源
│   └── evaluation/
│       └── ragas_testset.jsonl       ← RAGAS 问题占位草稿
├── vector_store_core.py              ← 原 ChromaDB 存储与检索核心
├── vector_store.py                   ← 兼容适配层，修正过滤和 RRF 字段
├── rebuild_knowledge_base.py         ← 校验或重建 ChromaDB
└── PROJECT_MAP.md
```

本次变化：

- 将原 `vector_store.py` 重命名为 `vector_store_core.py`。
- 新增兼容适配层 `vector_store.py`，其他模块导入路径不变。
- 修复 BM25 未应用 `field/level` 过滤的问题。
- 修复 RRF 合并后丢失 `type/field/level` 的问题。
- 将原始相似度保留在 `similarity`，融合排名使用 `rrf_score`。
- 四组检索验证通过：Python、机器学习、Transformer、React。

## 2026-09-23（学习资源知识库）

```text
learning-planning-multi-agent/
├── data/
│   ├── knowledge_base/
│   │   ├── knowledge_base_spec.md
│   │   └── learning_resources.jsonl
│   └── evaluation/
│       └── ragas_testset.jsonl
└── PROJECT_MAP.md
```

本次变化：

- 删除错误的知识卡和旧规范。
- 新增 10 条已审核学习资源。
- 明确知识库存放学习资源，不存放领域知识正文。

---

## 版本里程碑

| 版本 | 日期 | 主题 |
|---|---|---|
| v2.6.4 | 2026-10-28 | 演示 GIF + 演示脚本（CDP 抓帧合成）；修需求提取合并把 LLM 结果覆盖成关键词残片；pytest 119 项 |
| v2.6.3 | 2026-10-28 | 需求五字段补默认值 + 学习意图闸门；删除外置提示词目录死引用；pytest 110 项 |
| v2.6.2 | 2026-10-28 | 后端默认端口 8000 → 8001（`API_PORT` 可覆盖）；删除云端部署声称与遗留产物 |
| v2.6.1 | 2026-10-27 | 「贡献新资源」接真实接口；后端补提交白名单校验、修 `HTTPException` 被吞成 500、支持指定难度 |
| v2.6.0 | 2026-10-27 | 反馈按钮接真实接口；资源 `id` / `rating` / `feedback_count` 透传；新增单资源统计端点；移除前端 mock 回退 |
| v2.5.0 | 2026-10-26 | RAGAS 全量重跑（97 题）+ 同题对照；评测中断可续跑；重排置信度门控；消融扩到 10 档 |
| v2.4.0 | 2026-10-26 | 知识库 10 → 60 条、评测集 30 → 97 题；标准 RRF 替换伪融合；模型单例（冷启动 76s → 16s）；pytest + CI |
| v2.3.0 | 2026-09-28 | 增强 Self-RAG、Cross-Encoder 重排、运行时质量检测、RAGAS 0.4.3 |
| v2.2.0 | 2026-06-01 | Hybrid Search、CRAG、中文 Embedding、配置外部化、熔断器 |
| v2.0.0 | 2026-05-30 | LangGraph 编排、Self-RAG、六维评估 |
| v1.0.0 | 2026-05-26 | React 前端 + FastAPI 后端 + ChromaDB 混合检索 + 反馈闭环 |
