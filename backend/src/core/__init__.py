"""Agent 内核层。

- base_agent            所有子 Agent 的基类：LLM 调用、JSON 解析、提示词、指标
- requirement_extractor 需求提取 Agent：把口语描述抽成五字段需求
- course_planner        课程规划 Agent：把目标拆成阶段
- resource_recommender  资源推荐 Agent：调 RAG 链路拿资源并整合
- assessment_feedback   评估反馈 Agent：给计划打分，低分触发重生成
- graph_orchestrator    LangGraph 编排：节点、条件边、迭代上限
- agent_coordinator     线程式编排（无 LangGraph 环境的后备方案）
"""
