# 开发记录

> 按时间倒序记录「当时为什么这么改」，不是功能清单。功能清单见 [README](../README.md)，
> 评测数据见 [RETRIEVAL_EVAL.md](./RETRIEVAL_EVAL.md)。
> 文末是版本里程碑。
>
> 注：2026-10-31 起后端目录由 `learning-planning-multi-agent/` 改名为 `backend/`、
> 前端移入 `frontend/`。下文早于该日期的记录保留当时的目录名。

## 2026-11-19（前端全量重构：把模板味清掉）

起因：前端能跑，但一眼是生成的——整页紫蓝渐变、四张卡片四种渐变标题栏、玻璃拟态叠阴影、
emoji 当图标，检索内部指标（候选条数 / 重排置信度）直接铺在正文里。演示逻辑没问题，坏的是表达。

做法是按设计规范（Hallmark，主题 Furrow，app screen）整屏重做，不做局部修补：

- **系统**：暖纸 `#F6F2E9` + 近黑墨 + 一个番茄色。颜色 / 字号 / 间距 / 圆角全部收进 `tokens.css`（OKLCH），
  组件里不再出现色值字面量。强调色只给主按钮和焦点环。
- **版式**：结果区从四张彩卡改成四个区块，靠一条墨线 + 左对齐标题分开；学习路径做成编号台账
  （序号 / 阶段名 / 右侧时长 / 学习内容 / 阶段目标）。这是这一屏唯一能被记住的形状，也正好对应
  「四个 Agent 按阶段产出」这件事。
- **降噪**：检索细节收进「检索详情」折叠；预估周期拆成大数字 + 小注；手机端隐藏快捷键提示；
  点按目标统一到 44px。
- **技术栈**：删掉 Tailwind 与 lucide-react（`npm ci` 用的锁文件同步），样式改成手写 CSS 变量。
  产物 JS 167 KB / CSS 25 KB，净删 1071 行。

复检：静态 + 渲染检查 20 项硬违规 → 0；1 个链接、1 个输入框、28 个事件处理器逐字保留
（reformat handler 会被判成丢失，所以 JSX 重写时只改结构不改表达式）。
唯一改动的文案是页脚那句「基于多智能体协作技术 · 为您提供个性化学习规划」，换成
「评估均分低于 6 分时自动重新规划，最多 3 轮」——一句真实机制，比一句空话有用。

**中文排版一个坑**：正文宽度原来写 `68ch`。`ch` 按 "0" 的字宽算，中文一行只排得下三十来字，
页面右半会空出来。改成 `em`（一字约 1em）后正文 42–44em 才正常。

演示 GIF 随之重录（旧的是渐变版界面，已经对不上）。脚本里按文案和类名定位的那几个锚点
（`学习规划已生成` / `学习路径` / `评分：`）全都失效，改成 `.result` / `.stars__btn` /
`评价此资源` / `已记下`。新 GIF 18 帧抓取、合并后 17 帧；因为暖纸是纯色，体积从 2.9MB 降到 0.8MB。

**顺带修正一个长期写错的说法**：README 一直写「六维评估」，但 `assessment_summary` 只有
整体 + 可行性 / 内容 / 时间 / 方法，前端也只展示这四个。文档统一改成「整体 + 四维」。
真正的六维（多出 `progression_rating` / `personalization_rating`）只在
`assessment_feedback.py` 的提示词里存在，输出 schema 没有这两个字段，**LLM 多给的维度会被丢掉**——
这是待修项，不在本次范围内。

## 2026-11-13（门控实测：库外查询第一次真正走联网）

起因：11-12 的改造上线后，前端仍报「问历史、法律类问题也返回 5 条 AI 资源」。
查日志发现决定性证据——`[AdvancedRAG]` 行还是旧格式（只有 `候选/重排/质量/分数`），
新版应带 `决策=... cos=... logit=...`。**根因是后端 Python 进程在改代码之前就启动了**，
Python 不热重载模块，跑的是旧代码，不是新逻辑失效。

重启后同一查询（「复习近现代历史纲要课程」）：

| 指标 | 旧进程（11-13 17:18） | 新代码（重启后） |
|---|---|---|
| 候选数 | 8 | **0** |
| 质量判定 | medium / 0.6269 | **low / 0.0，decision=web** |
| 知识库资源 | 5 条 | **0 条** |
| 联网资源 | 0 | **3 条** |
| 查询改写 | — | 0 次（硬线直接跳改写） |

编排层评估 7.5~8.5、迭代 0/3，日志无 `稠密检索失败`。

**边界（别过度宣称）**：

1. 本次 5/5 库外查询都是被 **RRF 前置门槛**（dense 余弦全灭）拦下的；
   门控层「两路双低硬线」与 `rewrite` 软线分支没被真实流量触发，只有单测覆盖。
2. 联网结果 `type` 全是「文字教程」：`_infer_resource_type` 按 URL 关键词推断，
   `_merge_and_select` 也不按 `learning_preference` 过滤联网结果，用户勾了「视频」不生效；
   个别标题质量一般（「目录」「课程大纲-教务系统」），Tavily 结果没有质量筛选。
3. 编排层评估只看计划、不看资源，所以「资源全是联网的」也不会拉低评分。

## 2026-11-12（库外查询识别：用绝对量取代相对量判定）

起因：知识库只有 AI / 编程 / 数学三个领域，但旧链路**全是相对量**——Chroma 永远返回
top-k 最近邻，RRF 只按名次融合，重排只在候选内排序，`sigmoid(logit=0)` 还白送 0.5，
元数据匹配再送 0.20。结果「知识产权法」这类库外查询稳定拿到 0.62 分和 5 条无关资源，
而且因为 `kb_results` 永不为空，`_search_web` 的触发条件（`kb_empty`）从不成立。

- **先定规则再写代码**：质量报告输出 `decision = pass / rewrite / web`。
  `web` 硬线＝两路都实测且 top cosine < 0.25 且 top logit < 0.5，或 RRF 跳过融合（无候选）；
  `rewrite` 软线＝单路低于 0.28 / 0.65 或总分 < 0.55，改写最多 2 次后转联网。
- **只用绝对量**：`dense_similarity`（真实余弦）与 `rerank_score`（原始 logit）。
  不再拿 sigmoid 后的 `rerank_confidence` 当相关性，也不用它回写 `similarity`
  ——旧写法会让 `MIN_KB_SIMILARITY` 失效、前端相似度变假值。
- **链路分流**：`_evaluate_results` 按 `decision` 走三路；`web` 分支清空 `kb_results`
  后直接联网，**跳过改写**（改写救不回库里不存在的东西）；`rag_info` 新增
  `decision` 与 `no_hit_reason`，前端诊断条据此显示「跳过融合」的原因。
- **阈值要标定，不要拍脑袋**：新增 `eval/tools/calibrate_scope_thresholds.py`，
  跑库内/库外场景输出余弦与 logit 分布；换 Embedding、换重排模型、增删知识库后必须重跑。
- 质量分公式改为 `0.65*top + 0.25*avg + 0.10*match_ratio`（旧 `0.55/0.25/0.20`）：
  旧公式下库内 0.71~0.76、库外 0.60~0.64，区间几乎重叠，门控拦不住。
- 历史实验脚本（`eval/tools/experiment_quality_*`）显式关掉新门槛与联网，并标注
  「门控重构前的历史口径」，避免旧数字被当成当前结果。
- **验证**：`eval.test_rag_pipeline` 13 题（库内 10 + 库外 3）全过，库内 top id 不变、
  库外 3/3 `decision=web` 且不产生 KB 资源；新增 `tests/test_out_of_scope_gate.py`
  （不加载模型、不联网）。

同一天还做了两项与门控配套的加固，否则多线程下新链路会崩：

- **异步与并发**：7 个 async 路由里的同步 IO / Chroma 统计 / 重量级初始化改走
  `asyncio.to_thread`；配套加锁——`FeedbackManager`（`@_synchronized` + `tmp` + `os.replace`
  原子落盘）、`HybridRetriever`（LRU 与计数）、`VectorStoreManager`（`data_version` 自增、
  BM25 check-then-set 重建、`update_feedback` 读改写）、`model_loader` / `ConfigManager` /
  `GraphOrchestrator.compile` 双重检查锁。**锁与 to_thread 是配套的，不要单独删任一边。**
- **边界与数据流**：`agent_coordinator` 引用已删除的 `self.hermes_sync` 会让 CLI 直接崩；
  评估异常分支补齐字段与正常分支同构；`_attach_scores` 改按 id 匹配（按标题会丢资源 id，
  前端反馈就写不回去）；缓存读写用 `_copy_result` 断开嵌套引用。
- **联网兜底重写**：`web_search.py` 改为 SDK 优先、REST 直连备用，15 s 超时，
  两通道都失败抛 `WebSearchError`——联网失败不能拖住整条规划链路。

验证：pytest 全量通过（当时 119 项）；`eval.test_rag_pipeline` 10/10（改造前口径）、
十档消融指标与基线一致（最优 `MRR@5=0.9897`）；前端 `npm run build` +
`verify:api-errors` 9/9；30 路并发反馈落盘 30/30、各路由响应键集合不变。

## 2026-11-11（服务日志自动落盘）

起因：排障时只能靠终端滚动输出，`Ctrl+C` 之后什么都留不下；而 uvicorn 在 Windows
关闭阶段会重放捕获的信号，打出一段 `KeyboardInterrupt` / `CancelledError` 噪音，
没有日志就无法判断是启动失败还是关闭噪音。

- `src/utils/file_log.py`：`enable_file_logging()` 用 `_Tee` 包住 `sys.stdout/stderr`，
  终端照常输出，文件按行加时间戳写 `backend/logs/server.log`，5 MB 轮转；
  `FILE_LOG_ENABLED=0` 可关闭。uvicorn CLI 启动时已有的 `StreamHandler` 用 `setStream`
  指向 Tee，否则 CLI 日志漏记。
- `src/paths.py` 增 `LOG_DIR`；`.gitignore` 加 `backend/logs/`。
- 用法与常见报错对照写在本机 `docs/LOGGING_GUIDE.md`（含个人排障习惯，不入库）。

## 2026-11-04（检索策略从 memory 抽到 rag/retrieval.py）

起因：RRF 融合属于 RAG 的检索环节，却放在 `memory/` 里，概念上说不通；
`vector_store_core.py` 也因此长到 1001 行，一个类同时管数据库和排序策略。

- **重新划分的界**：`memory` 只回答「怎么存、怎么取回一批原始候选」；
  `rag/retrieval.py` 回答「怎么把候选组合成最终结果」。
  换存储不影响排序策略，调排序策略不碰数据库代码。
- **搬走**：`search()` 的三路分派、`_rrf_merge`、`_dedupe`、`_diversify`、
  `_normalize_sparse`、查询缓存与检索计数 → `HybridRetriever`，
  同时把四个算法改成模块级纯函数（`rrf_merge` / `dedupe` / `diversify` / `normalize_sparse`），
  测试可以直接测算法而不必先造一个假向量库。
- **留在 memory**：Chroma 读写、BM25 索引维护、`_build_where`（Chroma 语法适配）、
  `_dense_search` / `_sparse_search` 两个原始召回。
- **缓存失效改成「数据版本号」**：写库时 `data_version += 1`，检索器的缓存键带上它，
  旧条目自然不命中。好处是存储层不必反过来操作缓存对象（否则依赖方向就反了）。
  评分回写只 bump 版本、不重建 BM25，避免一次反馈引发全量索引重建。
- **统计拆两份**：`store.get_stats()` 只报资源分布，`retriever.get_retrieval_stats()`
  报命中率与延迟，`/api/stats` 与 `/api/health` 合并后输出——**响应字段与重构前完全一致**。
- **验证**：pytest 119 全绿（数量未变）；`eval.test_rag_pipeline` 10/10；
  十档消融指标逐项一致（0.8454 / 0.8866 / 0.9072 / 0.9175 / 0.9691，MRR 全同）；
  真实 `POST /api/plan` 200 / 17.1s；`/api/stats` 的 `hybrid_calls` 随请求从 0 涨到 1。

## 2026-10-31（后端分层重构 + 全量中文注释）

上一轮受「只改目录不改代码」约束，后端 29 个模块只能平铺。这次允许改代码，
所以按职责重新分层，并把注释补到「一眼能看懂」的程度。

- **分层**：`backend/src/{core,memory,rag,tools,feedback,api,utils}`，
  评测脚本进 `eval/`、离线脚本进 `scripts/`；依赖方向固定为
  `config/utils → memory/tools → rag → feedback/core → api`，避免导入成环。
- **必须一起改的四处**（不改不会报 ImportError，而是静默走错路径，更难查）：
  - `config._get_project_root()`：文件下移一层后，上溯两级的落点从仓库根变成 `backend/`，
    正好对上 `.env` 与 `data/`，这点要专门确认而不是想当然。
  - `api_server` 启动时的 `os.chdir`：原来切到自身目录（当时等于 `backend/`），
    下移后必须显式切到 `BACKEND_ROOT`，否则 `data/`、`chroma_db/` 全部指错。
  - 各评测脚本的 `ROOT = Path(__file__).parent`：下移后指向子目录，
    统一换成 `src.paths.BACKEND_ROOT`，并新增 `src/paths.py` 收敛路径常量。
  - `eval/test_modules.py` 用 `__import__('config')` 动态导入：分层后必然失败，
    改为正常导入，同时拆掉 lambda 套 lambda 的写法（检查项与输出格式完全不变）。
- **注释**：AST 统计 433 个类/函数，原有 400 个已是中文 docstring，补了 33 个缺口；
  前端 18 个文件原本几乎零注释，补齐文件头、组件说明、props 字段与关键分支。
  只加注释，未改任何逻辑。
- **验证**：pytest 119 全绿；`eval.test_rag_pipeline` 10/10；
  `eval.bench_retrieval` 十档指标与重构前逐项一致（0.8454 / 0.8866 / 0.9072 / 0.9175 / 0.9691）；
  真实 `POST /api/plan` 200、17.9s，五字段 / 5 阶段 / 2 条资源 / 评分 8.2 均正常；
  前端 `tsc && vite build` 产物大小与重构前完全相同（186.49 kB），说明注释未进入构建产物。

## 2026-10-31（目录结构调整：前后端分区）

目标是把仓库入口理干净，不改任何业务代码。

- **分了什么**：后端整体改名为 `backend/`；前端（`index.html`、`src/`、构建配置、
  `verify-api-errors.mjs`）移入 `frontend/`；`RETRIEVAL_EVAL.md` 归到 `docs/`；
  演示录制与 GIF 合成脚本留在根 `scripts/`。根目录只剩 `README.md` 与六个分区。
- **为什么没拆成 `src/agent_core/` `memory/` `tools/`**：后端根目录 29 个模块全部是顶层平铺
  绝对导入（`from config import config`、`from base_agent import BaseAgent`），
  `config.py` 还用 `Path(__file__)` 上溯两级定位项目根。移进子包会让所有 import 断开、
  并让路径推导偏移一级，必须改代码才能维持——这与「只调整目录、不改代码」冲突，
  所以保留平铺，把约束写进 [PROJECT_LAYOUT.md](./PROJECT_LAYOUT.md)。
- **路径连带修改**：CI 的 `working-directory`、`.gitignore` 中的后端前缀、
  README 与 docs 里的 `cd` 命令、`RETRIEVAL_EVAL.md` 的链接。
- **验证**：两套 venv 重命名后 `sys.prefix` 自愈正常；后端 `pytest` 119 项全绿；
  `test_rag_pipeline.py` 10 个场景通过；前端 `tsc && vite build` 与
  `npm run verify:api-errors` 通过。

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
| v2.7.0 | 2026-11-19 | 前端全量重构（去模板味、删 Tailwind/lucide、手写 CSS 台账版式）；演示 GIF 重录（17 帧 / 0.8MB）；文档「六维」改为「整体 + 四维」 |
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
