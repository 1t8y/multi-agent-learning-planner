# -*- coding: utf-8 -*-
"""
LangGraph 多智能体编排器
替代原 agent_coordinator.py 的线程式编排，使用 LangGraph StateGraph
实现 Agent 工作流的声明式定义和执行

工作流图:
    extract ──→ plan ──→ recommend ──→ merge
                       └─→ assess   ──→ merge
    merge ──(score<6)→ plan (regenerate, max 3 iterations)
    merge ──(score≥6)→ END

核心特性：
- 声明式状态图：节点和边一目了然
- 自动并行：recommend 和 assess 在 plan 后自动并行执行
- 条件再生：评估分数低于阈值时自动返回 plan 重新生成
"""

import json
import logging
from typing import TypedDict, Optional, List, Dict, Any, Literal

logging.basicConfig(level=logging.INFO, format="[GraphOrch] %(message)s")
logger = logging.getLogger(__name__)

# ── LangGraph 软依赖 ──
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("langgraph 未安装，请运行: pip install langgraph")
    # 创建占位类型以供类型检查
    StateGraph = None  # type: ignore
    END = "__end__"
    MemorySaver = None  # type: ignore

# ── Agent 导入 ──
from requirement_extractor import RequirementExtractorAgent
from course_planner import CoursePlannerAgent
from resource_recommender import ResourceRecommenderAgent
from assessment_feedback import AssessmentFeedbackAgent

# ── 再生阈值 ──
REGENERATION_THRESHOLD = 6.0   # 平均分数低于此值触发再生
MAX_REGENERATION_ROUNDS = 3    # 最多再生次数


# ══════════════════════════════════════════════════════════════════════
# 状态定义
# ══════════════════════════════════════════════════════════════════════

# 使用 Annotated 声明允许并行分支写入不同键，避免合并冲突
try:
    from typing import Annotated
except ImportError:
    # Python < 3.9 回退
    Annotated = None  # type: ignore


class LearningState(TypedDict, total=False):
    """多智能体学习规划流水线的共享状态"""
    # 输入（仅 extract 写入，串行安全）
    user_input: str

    # 各节点输出（每个节点只写自己负责的字段）
    requirement_data: Dict[str, Any]
    plan_data: Dict[str, Any]
    resource_data: Dict[str, Any]
    assessment_data: Dict[str, Any]

    # 综合输出（仅 merge 写入）
    result: Dict[str, Any]

    # 再生控制（plan 读，merge 写）
    iteration_count: int
    assessment_feedback_for_regeneration: str
    _need_regenerate: bool

    # 错误
    error: str


# ══════════════════════════════════════════════════════════════════════
# 节点函数
# ══════════════════════════════════════════════════════════════════════

class GraphOrchestrator:
    """
    LangGraph 学习规划编排器

    用法:
        orch = GraphOrchestrator()
        app = orch.compile()
        result = app.invoke({"user_input": "我想学Python，零基础，每天2小时"})
    """

    def __init__(self):
        """初始化四个子Agent并编译状态图"""
        logger.info("初始化 LangGraph 编排器...")

        self.extractor = RequirementExtractorAgent()
        self.planner = CoursePlannerAgent()
        self.recommender = ResourceRecommenderAgent()
        self.assessor = AssessmentFeedbackAgent()

        self._graph = None
        self._compiled = False

        logger.info("四个子Agent加载完成")

    # ── 节点1：需求提取 ──
    def _node_extract(self, state: LearningState) -> dict:
        """从用户原始输入中提取结构化需求"""
        user_input = state.get("user_input", "")
        logger.info(f"[extract] 输入: {user_input[:80]}...")

        try:
            requirement_data = self.extractor.extract(user_input)
            logger.info(f"[extract] 学习目标: {requirement_data.get('learning_objective')}")
            return {"requirement_data": requirement_data}
        except Exception as e:
            logger.error(f"[extract] 失败: {e}")
            return {"error": f"需求提取失败: {e}", "requirement_data": {}}

    # ── 节点2：课程规划 ──
    def _node_plan(self, state: LearningState) -> dict:
        """基于需求数据生成学习计划（支持再生反馈）"""
        requirement = state.get("requirement_data", {})

        if not requirement.get("learning_objective"):
            logger.warning("[plan] 缺少学习目标，跳过规划")
            return {"plan_data": {"error": "缺少学习目标"}}

        # 如果处于再生模式，在输入中附加评估反馈
        feedback_text = state.get("assessment_feedback_for_regeneration", "")
        if feedback_text and state.get("iteration_count", 0) > 0:
            logger.info(f"[plan] 再生模式 (第{state['iteration_count']}轮)，附加评估反馈")
            requirement = {
                **requirement,
                "_regeneration_feedback": feedback_text,
                "_iteration": state.get("iteration_count", 0),
            }

        try:
            plan_data = self.planner.plan(requirement)
            stage_count = plan_data.get("learning_path", {}).get("stage_count", 0)
            logger.info(f"[plan] 生成 {stage_count} 个阶段")
            return {"plan_data": plan_data, "assessment_feedback_for_regeneration": ""}
        except Exception as e:
            logger.error(f"[plan] 失败: {e}")
            return {"plan_data": {"error": str(e)}, "assessment_feedback_for_regeneration": ""}

    # ── 节点3：资源推荐（与评估并行）──
    def _node_recommend(self, state: LearningState) -> dict:
        """推荐学习资源"""
        requirement = state.get("requirement_data", {})
        plan = state.get("plan_data", {})

        if plan.get("error") or requirement.get("error"):
            logger.warning("[recommend] 上游数据无效，跳过推荐")
            return {"resource_data": {"resources": [], "rag_info": {}}}

        try:
            resource_data = self.recommender.recommend(requirement, plan)
            res_count = len(resource_data.get("resources", []))
            rag = resource_data.get("rag_info", {})
            logger.info(f"[recommend] 推荐 {res_count} 个资源 | 来源: {rag.get('source_info', 'N/A')}")
            return {"resource_data": resource_data}
        except Exception as e:
            logger.error(f"[recommend] 失败: {e}")
            return {"resource_data": {"resources": [], "rag_info": {}, "error": str(e)}}

    # ── 节点4：评估反馈（与推荐并行）──
    def _node_assess(self, state: LearningState) -> dict:
        """评估学习计划"""
        requirement = state.get("requirement_data", {})
        plan = state.get("plan_data", {})

        if plan.get("error") or requirement.get("error"):
            logger.warning("[assess] 上游数据无效，跳过评估")
            return {"assessment_data": {
                "assessment_summary": {"overall_rating": "无法评估", "score_average": 0},
                "assessment_metrics": [],
                "adjustment_suggestions": [],
            }}

        try:
            assessment_data = self.assessor.assess(requirement, plan)
            summary = assessment_data.get("assessment_summary", {})
            scores = [v for k, v in summary.items() if isinstance(v, (int, float)) and k.endswith("_rating")]
            avg_score = sum(scores) / len(scores) if scores else 0
            summary["score_average"] = round(avg_score, 1)
            logger.info(f"[assess] 综合评分: {summary.get('overall_rating')} (均分: {avg_score:.1f})")
            return {"assessment_data": assessment_data}
        except Exception as e:
            logger.error(f"[assess] 失败: {e}")
            return {"assessment_data": {
                "assessment_summary": {"overall_rating": "评估失败", "score_average": 0},
                "adjustment_suggestions": [],
            }}

    # ── 节点5：结果整合 + 再生控制 ──
    def _node_merge(self, state: LearningState) -> dict:
        """整合所有Agent结果，并在节点内递增再生计数器（条件边函数无法持久化状态）"""
        logger.info("[merge] 整合结果...")

        assessment = state.get("assessment_data", {})
        summary = assessment.get("assessment_summary", {})
        avg_score = summary.get("score_average", 0)
        iteration = state.get("iteration_count", 0)

        # 判断是否需要再生，如果需要则递增计数器
        need_regenerate = (
            avg_score > 0
            and avg_score < REGENERATION_THRESHOLD
            and iteration < MAX_REGENERATION_ROUNDS
        )
        if need_regenerate:
            iteration += 1

        # 构建再生反馈
        suggestions = assessment.get("adjustment_suggestions", [])
        if suggestions:
            feedback_parts = []
            for s in suggestions[:3]:
                feedback_parts.append(
                    f"[{s.get('priority', '')}] {s.get('area', '')}: {s.get('suggestion', '')}"
                )
            feedback_text = "; ".join(feedback_parts)
        else:
            feedback_text = f"当前评分 {avg_score:.1f}/10 过低，请优化学习计划的深度、阶段划分和可执行性"

        logger.info(f"[merge] 均分: {avg_score:.1f}, 迭代: {iteration}/{MAX_REGENERATION_ROUNDS}, 再生: {need_regenerate}")

        return {
            "result": {
                "requirement_data": state.get("requirement_data", {}),
                "plan": state.get("plan_data", {}),
                "resources": state.get("resource_data", {}),
                "assessment": state.get("assessment_data", {}),
            },
            # 在节点内递增，条件边函数只能在读取
            "iteration_count": iteration,
            "assessment_feedback_for_regeneration": feedback_text if need_regenerate else "",
            "_need_regenerate": need_regenerate,
        }

    # ── 条件边：判断是否需要重新生成 ──
    def _should_regenerate(self, state: LearningState) -> Literal["regenerate", "done"]:
        """
        读取 _node_merge 中已更新的状态，决定是否重新生成

        条件边函数只能**读取**状态，不能修改。
        """
        iteration = state.get("iteration_count", 0)

        # 读取 merge 节点设置的需要再生标志
        if state.get("_need_regenerate", False):
            logger.info(f"[merge] 触发再生 (第{iteration}轮)")
            return "regenerate"

        if iteration >= MAX_REGENERATION_ROUNDS:
            logger.info(f"[merge] 已达最大再生次数 ({MAX_REGENERATION_ROUNDS})")

        logger.info(f"[merge] 流水线完成 (迭代: {iteration})")
        return "done"

    # ── 编译状态图 ──
    def compile(self):
        """
        构建并编译 LangGraph 状态图

        Returns:
            编译后的可执行图
        """
        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError("langgraph 未安装，请运行: pip install langgraph langgraph-checkpoint")

        if self._compiled:
            return self._graph

        logger.info("构建 LangGraph 状态图...")

        # 创建图
        graph = StateGraph(LearningState)

        # 注册节点
        graph.add_node("extract", self._node_extract)
        graph.add_node("plan", self._node_plan)
        graph.add_node("recommend", self._node_recommend)
        graph.add_node("assess", self._node_assess)
        graph.add_node("merge", self._node_merge)

        # ── 定义边（流转路径） ──
        # 串行: extract → plan
        graph.add_edge("extract", "plan")

        # 并行分支: plan → recommend 和 plan → assess
        graph.add_edge("plan", "recommend")
        graph.add_edge("plan", "assess")

        # 汇聚: recommend → merge, assess → merge
        graph.add_edge("recommend", "merge")
        graph.add_edge("assess", "merge")

        # 条件边: merge → plan (再生) 或 merge → END (完成)
        graph.add_conditional_edges(
            "merge",
            self._should_regenerate,
            {
                "regenerate": "plan",
                "done": END,
            }
        )

        # 设置入口
        graph.set_entry_point("extract")

        # 编译（带内存检查点）
        self._graph = graph.compile()
        self._compiled = True

        logger.info("LangGraph 状态图编译完成")
        return self._graph

    # ── 便捷方法 ──
    def invoke(self, user_input: str) -> Dict[str, Any]:
        """
        执行完整的学习规划流程

        Args:
            user_input: 用户的学习需求原始文本

        Returns:
            包含所有Agent结果的字典
        """
        if not self._compiled:
            self.compile()

        initial_state: LearningState = {
            "user_input": user_input,
            "requirement_data": {},
            "plan_data": {},
            "resource_data": {},
            "assessment_data": {},
            "result": {},
            "iteration_count": 0,
            "assessment_feedback_for_regeneration": "",
            "error": "",
        }

        logger.info(f"开始执行流程: {user_input[:80]}...")
        final_state = self._graph.invoke(initial_state)

        # 返回结构化的结果
        result = final_state.get("result", {})
        if final_state.get("error"):
            result["error"] = final_state["error"]

        # 添加迭代信息
        result["_meta"] = {
            "iteration_count": final_state.get("iteration_count", 0),
            "was_regenerated": final_state.get("iteration_count", 0) > 0,
        }

        return result

    def get_agent_metrics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有Agent的性能指标"""
        return {
            "extractor": self.extractor.get_metrics() if hasattr(self.extractor, "get_metrics") else {},
            "planner": self.planner.get_metrics() if hasattr(self.planner, "get_metrics") else {},
            "recommender": self.recommender.get_metrics(),
            "assessor": self.assessor.get_metrics(),
        }

    def print_status(self):
        """打印系统状态"""
        print("\n" + "=" * 60)
        print("学习规划多智能体系统 (LangGraph)")
        print("=" * 60)
        print(f"LangGraph: {'已就绪' if self._compiled else '待编译'}")
        print(f"Agent 数量: 4 (extract → plan → recommend∥assess → merge)")
        print(f"再生策略: 均分 < {REGENERATION_THRESHOLD} 时重新生成 (最多 {MAX_REGENERATION_ROUNDS} 轮)")
        print("=" * 60 + "\n")


# ══════════════════════════════════════════════════════════════════════
# 模块入口
# ══════════════════════════════════════════════════════════════════════

def init_orchestrator() -> GraphOrchestrator:
    """初始化 LangGraph 编排器"""
    orch = GraphOrchestrator()
    orch.compile()
    orch.print_status()
    return orch


def main():
    """交互式测试入口"""
    try:
        orch = init_orchestrator()

        print("欢迎使用学习规划多智能体系统 (LangGraph版)！")
        print("示例：我是零基础，想学习Python编程，每天能学2小时，喜欢看视频")

        while True:
            user_input = input("\n您: ")
            if user_input.lower() in ("exit", "quit"):
                print("再见！")
                break
            if not user_input.strip():
                continue

            result = orch.invoke(user_input)

            print("\n" + "=" * 60)
            print("【学习规划结果】")
            print("=" * 60)

            req = result.get("requirement_data", {})
            print(f"\n学习目标: {req.get('learning_objective', 'N/A')}")
            print(f"现有基础: {req.get('current_foundation', 'N/A')}")
            print(f"每日时间: {req.get('daily_available_time', 'N/A')}")
            print(f"学习偏好: {req.get('learning_preference', 'N/A')}")
            print(f"时间期望: {req.get('time_expectation', 'N/A')}")

            if result.get("error"):
                print(f"\n错误: {result['error']}")
                continue

            plan = result.get("plan", {})
            stages = plan.get("learning_path", {}).get("stages", [])
            if stages:
                print(f"\n学习阶段 ({len(stages)}个):")
                for i, s in enumerate(stages, 1):
                    print(f"  {i}. {s.get('stage_name', '')}")
                    print(f"     内容: {s.get('study_content', '')}")
                    print(f"     时长: {s.get('time_allocation', '')}")
                    print(f"     里程碑: {s.get('milestone', '')}")

            resources = result.get("resources", {})
            res_list = resources.get("resources", [])[:3]
            if res_list:
                print(f"\n推荐资源 ({len(res_list)}个):")
                rag = resources.get("rag_info", {})
                print(f"  来源: {rag.get('source_info', 'N/A')}")
                for i, r in enumerate(res_list, 1):
                    source_tag = (
                        "📚本地库" if r.get("source") == "knowledge_base"
                        else "🌐网络" if r.get("source") == "web_search"
                        else "🤖AI生成"
                    )
                    print(f"  {i}. {source_tag} {r.get('title', 'N/A')}")

            assessment = result.get("assessment", {})
            summary = assessment.get("assessment_summary", {})
            if summary:
                print(f"\n评估结果:")
                print(f"  综合评分: {summary.get('score_average', 'N/A')}/10")
                for k, v in summary.items():
                    if k.endswith("_rating") and isinstance(v, (int, float)):
                        print(f"  {k}: {v}/10")

            meta = result.get("_meta", {})
            if meta.get("was_regenerated"):
                print(f"\n⚠️ 该计划经过 {meta['iteration_count']} 轮重新生成优化")

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()
