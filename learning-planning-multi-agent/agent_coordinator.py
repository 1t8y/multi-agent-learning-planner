"""
学习规划多智能体协调器
负责调度和协调所有子Agent，完成完整的学习规划流程

核心功能：
- 协调四个子Agent的执行顺序
- 处理Agent间的数据传递
- 支持并行处理提高效率
- 集成Hermes Kanban状态同步
- 收集和管理各Agent的性能指标
"""

import os
import json
import threading
from queue import Queue
from typing import Dict, Any, Optional, Tuple

# 导入子Agent
from requirement_extractor import RequirementExtractorAgent
from course_planner import CoursePlannerAgent
from resource_recommender import ResourceRecommenderAgent
from assessment_feedback import AssessmentFeedbackAgent

# 导入Hermes同步客户端
try:
    from hermes_sync import HermesSyncClient
    HERMES_AVAILABLE = True
except ImportError:
    HERMES_AVAILABLE = False
    print("[协调器] Hermes Sync 模块未导入，跳过状态同步")


class LearningPlanningCoordinator:
    """
    学习规划多智能体系统的主协调器
    
    工作流程：
    1. 接收用户输入
    2. 调用需求分析子Agent提取结构化需求
    3. 调用课程规划子Agent生成学习计划
    4. 并行调用资源推荐和评估反馈子Agent
    5. 整合所有结果返回给用户
    6. 同步各Agent状态到Hermes Kanban
    
    Attributes:
        extractor: 需求分析Agent
        planner: 课程规划Agent
        recommender: 资源推荐Agent
        assessor: 评估反馈Agent
        hermes_sync: Hermes同步客户端（可选）
        agent_name_mapping: Agent名称到配置名称的映射
    """
    
    def __init__(self, enable_hermes_sync: bool = True):
        """
        初始化协调器
        
        Args:
            enable_hermes_sync: 是否启用Hermes状态同步
        """
        print("[协调器] 初始化多智能体学习规划系统...")
        
        # 初始化子Agent
        self.extractor = RequirementExtractorAgent()
        self.planner = CoursePlannerAgent()
        self.recommender = ResourceRecommenderAgent()
        self.assessor = AssessmentFeedbackAgent()
        
        # 初始化Hermes同步（如果可用）
        self.hermes_sync = None
        if HERMES_AVAILABLE and enable_hermes_sync:
            try:
                self.hermes_sync = HermesSyncClient()
                print("[协调器] Hermes Sync 已启用")
            except Exception as e:
                print(f"[协调器] Hermes Sync 初始化失败: {e}")
        
        # Agent名称映射（用于Hermes任务ID查找）
        self.agent_name_mapping = {
            'extractor': 'requirement-extractor-agent',
            'planner': 'course-planner-agent',
            'recommender': 'resource-recommender-agent',
            'assessor': 'assessment-feedback-agent',
            'coordinator': 'agent_coordinator'
        }
        
        print("[协调器] 多智能体学习规划系统初始化完成")
    
    def _notify_agent_complete(self, agent_key: str, status: str = 'completed') -> None:
        """
        通知Agent执行完成，同步状态到Hermes Kanban
        
        Args:
            agent_key: Agent的内部键名
            status: 状态（running/completed/failed）
        """
        if not self.hermes_sync:
            return
        
        agent_name = self.agent_name_mapping.get(agent_key)
        if not agent_name:
            print(f"[协调器] 未知的Agent: {agent_key}")
            return
        
        task_id = self.hermes_sync.get_agent_task_id(agent_name)
        if not task_id:
            print(f"[协调器] 未找到Agent {agent_name} 的Hermes任务ID")
            return
        
        print(f"[协调器] 同步Agent {agent_name} 状态到Hermes: {status}")
        self.hermes_sync.update_job_status(task_id, status)
    
    def _parallel_process(self, requirement_data: Dict, plan_data: Dict) -> Tuple[Dict, Dict]:
        """
        并行处理资源推荐和评估反馈任务
        
        Args:
            requirement_data: 学习需求数据
            plan_data: 学习计划数据
            
        Returns:
            资源推荐结果和评估反馈结果的元组
        """
        results = Queue()
        
        def run_recommender():
            """运行资源推荐Agent"""
            try:
                result = self.recommender.recommend(requirement_data, plan_data)
                results.put(('resource', result, 'completed'))
            except Exception as e:
                print(f"[协调器] 资源推荐失败: {str(e)}")
                results.put(('resource', {"resources": []}, 'failed'))
        
        def run_assessor():
            """运行评估反馈Agent"""
            try:
                result = self.assessor.assess(requirement_data, plan_data)
                results.put(('assessment', result, 'completed'))
            except Exception as e:
                print(f"[协调器] 评估反馈失败: {str(e)}")
                results.put(('assessment', {
                    "assessment_summary": {
                        "overall_rating": "获取失败",
                        "feasibility_rating": 0,
                        "content_rating": 0,
                        "time_rating": 0,
                        "method_rating": 0
                    },
                    "assessment_metrics": [],
                    "adjustment_suggestions": [],
                    "recommendations": []
                }, 'failed'))
        
        # 创建并启动线程
        t1 = threading.Thread(target=run_recommender, name="ResourceRecommender")
        t2 = threading.Thread(target=run_assessor, name="AssessmentFeedback")
        
        t1.start()
        t2.start()
        
        # 等待线程完成
        t1.join()
        t2.join()
        
        # 收集结果
        resource_result = None
        assessment_result = None
        
        while not results.empty():
            key, value, status = results.get()
            if key == 'resource':
                resource_result = value
                self._notify_agent_complete('recommender', status)
            elif key == 'assessment':
                assessment_result = value
                self._notify_agent_complete('assessor', status)
        
        # 返回结果，提供默认值以防线程执行失败
        return (
            resource_result or {"resources": []},
            assessment_result or {
                "assessment_summary": {},
                "assessment_metrics": [],
                "adjustment_suggestions": [],
                "recommendations": []
            }
        )
    
    def process(self, user_input: str) -> Dict:
        """
        处理用户输入，执行完整的学习规划流程
        
        Args:
            user_input: 用户的学习需求描述
            
        Returns:
            包含需求分析、学习计划、资源推荐和评估反馈的完整结果
        """
        print("\n" + "="*70)
        print("[协调器] 开始处理用户请求...")
        print("="*70)
        
        # 标记协调器开始运行
        self._notify_agent_complete('coordinator', 'running')
        
        # 步骤1：需求分析
        print("\n【步骤1】调用需求分析子Agent...")
        try:
            requirement_data = self.extractor.extract(user_input)
            print(f"[提取结果] {json.dumps(requirement_data, ensure_ascii=False)}")
            self._notify_agent_complete('extractor', 'completed')
        except Exception as e:
            print(f"[提取失败] {str(e)}")
            self._notify_agent_complete('extractor', 'failed')
            return {
                "error": "无法提取有效学习目标",
                "requirement_data": {},
                "plan": None,
                "resources": None,
                "assessment": None
            }
        
        # 验证需求数据
        if not requirement_data.get("learning_objective"):
            return {
                "error": "无法提取有效学习目标",
                "requirement_data": requirement_data,
                "plan": None,
                "resources": None,
                "assessment": None
            }
        
        # 步骤2：课程规划
        print("\n【步骤2】调用课程规划子Agent...")
        try:
            plan_data = self.planner.plan(requirement_data)
            print(f"[规划结果] {json.dumps(plan_data, ensure_ascii=False)}")
            self._notify_agent_complete('planner', 'completed')
        except Exception as e:
            print(f"[规划失败] {str(e)}")
            self._notify_agent_complete('planner', 'failed')
            return {
                "error": "课程规划失败",
                "requirement_data": requirement_data,
                "plan": None,
                "resources": None,
                "assessment": None
            }
        
        # 步骤3：并行调用资源推荐和评估反馈
        print("\n【步骤3】并行调用资源推荐和评估反馈子Agent...")
        resource_data, assessment_data = self._parallel_process(requirement_data, plan_data)
        
        print(f"[资源推荐结果] {json.dumps(resource_data, ensure_ascii=False)}")
        print(f"[评估反馈结果] {json.dumps(assessment_data, ensure_ascii=False)}")
        
        # 步骤4：整合结果
        print("\n【步骤4】整合所有子Agent结果...")
        self._notify_agent_complete('coordinator', 'completed')
        
        return {
            "requirement_data": requirement_data,
            "plan": plan_data,
            "resources": resource_data,
            "assessment": assessment_data
        }
    
    def get_agent_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有Agent的性能指标
        
        Returns:
            包含各Agent指标的字典
        """
        return {
            'extractor': self.extractor.get_metrics() if hasattr(self.extractor, 'get_metrics') else {},
            'planner': self.planner.get_metrics() if hasattr(self.planner, 'get_metrics') else {},
            'recommender': self.recommender.get_metrics(),
            'assessor': self.assessor.get_metrics()
        }
    
    def validate_agent_outputs(self, result: Dict) -> Dict[str, bool]:
        """
        验证Agent输出的有效性
        
        Args:
            result: 处理结果
            
        Returns:
            各输出项的验证结果
        """
        return {
            'resources_valid': self.recommender.validate_result(result.get('resources', {})),
            'assessment_valid': self.assessor.validate_result(result.get('assessment', {}))
        }
    
    def print_system_status(self):
        """打印系统状态摘要"""
        print("\n" + "="*70)
        print("学习规划多智能体系统状态")
        print("="*70)
        print("已加载的Agent:")
        print(f"  • 需求分析: {self.extractor.__class__.__name__}")
        print(f"  • 课程规划: {self.planner.__class__.__name__}")
        print(f"  • 资源推荐: {self.recommender.__class__.__name__}")
        print(f"  • 评估反馈: {self.assessor.__class__.__name__}")
        print(f"Hermes Sync: {'已启用' if self.hermes_sync else '未启用'}")
        print("="*70 + "\n")


def main():
    """主函数，启动交互式学习规划系统"""
    try:
        coordinator = LearningPlanningCoordinator()
        coordinator.print_system_status()
        
        print("欢迎使用学习规划多智能体系统！")
        print("请输入您的学习需求（输入 'exit' 或 'quit' 退出）")
        print("示例：我是零基础，想学习Python编程，每天能学2小时，喜欢看视频学习")
        print("-" * 70)
        
        while True:
            user_input = input("\n您: ")
            
            if user_input.lower() in ["exit", "quit"]:
                print("\n系统运行统计:")
                metrics = coordinator.get_agent_metrics()
                for agent_name, metric in metrics.items():
                    print(f"  {agent_name}:")
                    print(f"    - 调用次数: {metric.get('call_count', 0)}")
                    print(f"    - 错误次数: {metric.get('error_count', 0)}")
                    print(f"    - 成功率: {metric.get('success_rate', 0):.2%}")
                print("感谢使用，再见！")
                break
            
            if not user_input.strip():
                print("请输入有效的学习需求")
                continue
            
            try:
                result = coordinator.process(user_input)
                
                # 打印结果
                print("\n" + "="*70)
                print("【学习规划结果】")
                print("="*70)
                
                # 需求信息
                print("\n一、提取的需求信息：")
                req = result["requirement_data"]
                print(f"• 学习目标: {req.get('learning_objective', '未指定')}")
                print(f"• 现有基础: {req.get('current_foundation', '未指定')}")
                print(f"• 每日可用时间: {req.get('daily_available_time', '未指定')}")
                print(f"• 学习偏好: {req.get('learning_preference', '未指定')}")
                print(f"• 时间期望: {req.get('time_expectation', '未指定')}")
                
                # 错误处理
                if result.get("error"):
                    print(f"\n错误: {result['error']}")
                    continue
                
                # 学习计划
                plan = result["plan"]
                print("\n二、学习计划：")
                print(f"• 目标可行性: {plan.get('goal_feasibility', '-')}")
                print(f"• 预估周期: {plan.get('estimated_duration', '-')}")
                
                learning_path = plan.get("learning_path", {})
                stages = learning_path.get("stages", [])
                if stages:
                    print(f"\n• 学习阶段 ({learning_path.get('stage_count', len(stages))}个阶段):")
                    for i, stage in enumerate(stages, 1):
                        print(f"\n  阶段{i}: {stage.get('stage_name', '')}")
                        print(f"    ├─ 学习内容: {stage.get('study_content', '')}")
                        print(f"    ├─ 时间分配: {stage.get('time_allocation', '')}")
                        print(f"    └─ 里程碑: {stage.get('milestone', '')}")
                
                # 推荐资源
                resources = result.get("resources", {})
                resource_list = resources.get("resources", [])[:3]
                if resource_list:
                    print("\n三、推荐资源（前3个）：")
                    for i, resource in enumerate(resource_list, 1):
                        print(f"\n  {i}. [{resource.get('type', '')}] {resource.get('title', '')}")
                        print(f"    ├─ 阶段: {resource.get('phase', '')}")
                        print(f"    ├─ 难度: {resource.get('difficulty', '')}")
                        print(f"    ├─ 时长: {resource.get('duration', '')}")
                        print(f"    └─ 推荐理由: {resource.get('recommendation_reason', '')}")
                
                # 评估反馈
                assessment = result.get("assessment", {})
                summary = assessment.get("assessment_summary", {})
                if summary:
                    print("\n四、评估反馈：")
                    print(f"• 整体评估: {summary.get('overall_rating', '-')}")
                    print(f"• 可行性评分: {summary.get('feasibility_rating', '-')}/10")
                    print(f"• 内容合理性评分: {summary.get('content_rating', '-')}/10")
                    print(f"• 时间安排评分: {summary.get('time_rating', '-')}/10")
                    print(f"• 方法适配性评分: {summary.get('method_rating', '-')}/10")
                
                suggestions = assessment.get("adjustment_suggestions", [])[:2]
                if suggestions:
                    print("\n• 调整建议（前2条）:")
                    for i, suggestion in enumerate(suggestions, 1):
                        print(f"\n  {i}. [{suggestion.get('priority', '')}] {suggestion.get('area', '')}")
                        print(f"    ├─ 问题: {suggestion.get('issue', '')}")
                        print(f"    └─ 建议: {suggestion.get('suggestion', '')}")
                
            except Exception as e:
                print(f"处理失败: {str(e)}")
            
            print("\n" + "-"*70)
    
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        print(f"系统初始化失败: {e}")


if __name__ == "__main__":
    main()