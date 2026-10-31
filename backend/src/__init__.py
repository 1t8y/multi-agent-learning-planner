"""后端源码包。

分层约定（从下往上，上层可依赖下层，反之不行）：

    config / utils      配置与无依赖的通用工具
    memory / tools      向量库、模型加载、外部工具
    rag                 检索增强：过滤 → 召回 → 融合 → 精排 → 质量门控
    feedback            用户反馈与资源提交
    core                Agent 内核：推理、规划、反思、编排
    api                 对外 HTTP 接口

详细职责与文件对应关系见 docs/PROJECT_LAYOUT.md。
"""
