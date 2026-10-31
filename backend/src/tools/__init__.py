"""工具层：Agent 可调用的外部能力。

- web_search  联网搜索，知识库覆盖不足时补充
- hermes_sync 与本地 Hermes 服务的资源同步

新增工具时只需在此层实现「名称 + 入参 schema + 执行函数」，
上层 Agent 不需要改推理代码。
"""
