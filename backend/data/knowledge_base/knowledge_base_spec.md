# 学习资源知识库规范

> 状态：待人工审核  
> 版本：v0.2  
> 用途：为资源推荐、Self-RAG 和 RAGAS 提供结构化学习资源

## 1. 知识库定位

本项目知识库存的是“可以推荐给用户的学习资源”，不是领域知识正文。

正确内容：

- 视频教程
- 文字教程
- 官方文档
- 实战项目
- 课程或书籍

错误内容：

- 概念解释
- 课程笔记
- 独立知识卡
- 没有 URL 的技术说明

## 2. 用户输入

前端向 `POST /api/plan` 提交：

```json
{"userInput": "我是零基础，想学Python，每天2小时，喜欢视频，一个月内上手"}
```

需求分析输出：

| 字段 | 示例 |
|---|---|
| `learning_objective` | 学习 Python |
| `current_foundation` | 零基础 |
| `daily_available_time` | 2小时 |
| `learning_preference` | 视频 |
| `time_expectation` | 短期学习 |

## 3. 输入与资源字段对齐

| 用户需求 | 资源字段 | 用途 |
|---|---|---|
| `learning_objective` | `title`、`description`、`tags` | 匹配学习主题 |
| 领域判断结果 | `field` | 过滤知识领域 |
| `current_foundation` | `level` | 匹配资源难度 |
| `learning_preference` | `resource_type` | 优先匹配视频、文字或实操 |
| `time_expectation` | `duration` | 后续用于匹配学习周期 |

当前代码未完整使用 `learning_preference` 和 `duration`，这是后续代码优化项，不通过扩充知识库伪装解决。

## 4. 资源字段

每行 JSON 保存一个学习资源：

| 字段 | 说明 |
|---|---|
| `id` | 稳定唯一 ID |
| `title` | 资源标题 |
| `description` | 可检索的资源和内容说明 |
| `resource_type` | 视频教程、文字教程、实战项目、文档资料 |
| `field` | AI、编程、数学等 |
| `level` | beginner、intermediate、advanced |
| `url` | 可访问的资源地址 |
| `tags` | 检索标签 |
| `source` | system、catalog_draft 或用户反馈 |
| `rating` | 初始评分，草稿默认 0 |
| `feedback_count` | 反馈数量，草稿默认 0 |
| `created_at` | 创建时间 |
| `review_status` | pending、approved、rejected |

## 5. 推荐输出

资源 Agent 输出：

```json
{
  "phase": "第一阶段：基础入门",
  "type": "视频教程",
  "title": "Python基础教程",
  "description": "系统学习 Python 基础",
  "duration": "2-4小时",
  "difficulty": "初级",
  "recommendation_reason": "来自本地知识库，相似度 0.82",
  "url": "https://example.com",
  "source": "knowledge_base"
}
```

## 6. 审核与入库

1. 新资源先使用 `catalog_draft` 和 `pending`。
2. 用户检查标题、描述、类型、领域、难度和 URL。
3. 确认后改为 `system` 和 `approved`。
4. 只有 `approved` 资源允许写入正式 ChromaDB。
5. 资源增删后必须重建 `chroma_db`。
6. RAGAS 测试问题必须围绕资源推荐生成。
7. `reference_contexts` 使用对应资源记录，不使用独立知识卡。
