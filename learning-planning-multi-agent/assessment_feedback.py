"""
评估反馈子Agent
负责评估学习计划的合理性、可行性和有效性

核心功能：
- 评估学习计划的各个维度
- 提供阶段性评估指标
- 生成调整建议和优化方案
"""

import os
import json
from typing import Optional, Dict, Any
from base_agent import BaseAgent


class AssessmentFeedbackAgent(BaseAgent):
    """
    评估反馈子Agent，对学习计划进行全面评估
    
    输入：
    - requirement_info: 学习需求信息
    - learning_plan: 学习计划
    
    输出：
    - assessment_summary: 评估摘要（整体评分、各维度评分）
    - assessment_metrics: 阶段性评估指标
    - adjustment_suggestions: 调整建议
    - recommendations: 综合建议
    """
    
    AGENT_NAME = "assessment-feedback"
    PROMPT_FILE = "assessment-feedback-agent.md"
    
    def __init__(self, agent_config: Optional[Dict] = None):
        """
        初始化评估反馈Agent
        
        Args:
            agent_config: Agent特定配置
        """
        super().__init__(agent_config)
    
    def _get_prompt_path(self) -> Optional[str]:
        """获取提示词文件路径"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, ".trae", "agents", self.PROMPT_FILE)
    
    def _get_default_prompt(self) -> str:
        """获取默认系统提示词"""
        return """你是专业**学习效果评估师**，对学习计划进行全面多维度评估，制定科学的评估方法，并提供针对性的调整建议。

## 核心职责
- 从6个维度全面评估学习计划的合理性、可行性和有效性
- 制定阶段性评估指标和方法
- 返回评估方案和具体调整建议

## 输入信息
- requirement_info: 学习需求信息（包含学习目标、现有基础、每日可用时间、学习偏好、时间期望）
- learning_plan: 学习计划（包含目标可行性、预估周期、学习路径、阶段信息）

## 评估维度（6维度）
1. **目标可行性评估 (feasibility_rating)**：目标是否明确、是否符合用户基础和时间约束
2. **内容合理性评估 (content_rating)**：学习内容是否系统完整、是否循序渐进
3. **时间安排评估 (time_rating)**：各阶段时间分配是否合理、是否符合用户每日可用时间
4. **方法适配性评估 (method_rating)**：学习方式是否匹配用户偏好（视频/文字/实操）
5. **进阶逻辑评估 (progression_rating)**：阶段间过渡是否平滑、知识衔接是否合理、是否遵循「基础→进阶→实战」逻辑
6. **个性化匹配评估 (personalization_rating)**：计划是否针对用户具体目标（而非通用模板）、是否考虑了用户的独特需求

## 评估指标
- 过程性指标：学习进度完成率、知识点掌握程度、作业质量、学习活跃度
- 结果性指标：阶段性测试成绩、项目实践完成情况、技能应用能力、目标达成度

## 评分标准（1-10分）
1-2分：完全不可行/不合理，存在严重缺陷
3-4分：有明显问题，需要重大调整
5-6分：基本可行但存在不足，需要改进
7-8分：良好，有少量可优化空间
9-10分：优秀，几乎无需调整

## 强制约束
1. 仅输出**纯标准JSON**，无多余文字、解释、注释
2. 严格遵循固定输出结构，不增删、不修改字段名
3. 评估必须客观、基于输入数据，不能凭空臆断
4. 评分低于5分时，调整建议必须具体且可操作
5. 每项评分必须有对应的理由

## 输出格式（固定不可修改）
{
  "assessment_summary": {
    "overall_rating": "",
    "feasibility_rating": 0,
    "content_rating": 0,
    "time_rating": 0,
    "method_rating": 0,
    "progression_rating": 0,
    "personalization_rating": 0
  },
  "assessment_metrics": [
    {
      "phase": "",
      "metrics": [
        {
          "name": "",
          "description": "",
          "target_value": "",
          "measurement_method": ""
        }
      ]
    }
  ],
  "adjustment_suggestions": [
    {
      "area": "",
      "issue": "",
      "suggestion": "",
      "priority": ""
    }
  ],
  "recommendations": []
}"""
    
    def _get_default_result(self) -> Dict:
        """获取默认返回结果（API调用失败时使用）"""
        return {
            "assessment_summary": {
                "overall_rating": "获取失败",
                "feasibility_rating": 0,
                "content_rating": 0,
                "time_rating": 0,
                "method_rating": 0,
                "progression_rating": 0,
                "personalization_rating": 0,
                "score_average": 0,
            },
            "assessment_metrics": [],
            "adjustment_suggestions": [],
            "recommendations": []
        }
    
    def assess(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """
        评估学习计划
        
        Args:
            requirement_info: 学习需求信息
            learning_plan: 学习计划
            
        Returns:
            包含评估结果的字典
            
        Raises:
            ValueError: 输入数据无效
        """
        # 验证输入
        if not isinstance(requirement_info, dict) or not isinstance(learning_plan, dict):
            raise ValueError("输入必须是字典类型")
        
        if not requirement_info.get("learning_objective"):
            print(f"[{self.AGENT_NAME}] 警告：缺少学习目标，返回默认评估结果")
            return self._get_default_result()
        
        print(f"[{self.AGENT_NAME}] 开始评估学习计划...")
        
        try:
            # 构建输入数据
            input_data = {
                "requirement_info": requirement_info,
                "learning_plan": learning_plan
            }
            input_json = json.dumps(input_data, ensure_ascii=False)
            
            # 调用API评估
            result = self._call_api(input_json)
            
            print(f"[{self.AGENT_NAME}] 评估完成")
            
            return result
        
        except ValueError as e:
            print(f"[{self.AGENT_NAME}] 配置错误: {e}")
            raise
        except RuntimeError as e:
            print(f"[{self.AGENT_NAME}] API调用失败: {e}")
            return self._get_default_result()
        except Exception as e:
            print(f"[{self.AGENT_NAME}] 评估过程发生未知错误: {e}")
            return self._get_default_result()
    
    def process(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """
        处理请求（实现BaseAgent的抽象方法）
        
        Args:
            requirement_info: 学习需求信息
            learning_plan: 学习计划
            
        Returns:
            评估结果
        """
        return self.assess(requirement_info, learning_plan)
    
    def batch_assess(self, batch_data: list) -> list:
        """
        批量评估学习计划
        
        Args:
            batch_data: 批量数据列表
            
        Returns:
            批量评估结果列表
        """
        results = []
        for item in batch_data:
            result = self.process(item['requirement_info'], item['learning_plan'])
            results.append(result)
        return results
    
    def validate_result(self, result: Dict) -> bool:
        """
        验证评估结果的有效性
        
        Args:
            result: 评估结果
            
        Returns:
            有效返回True，否则返回False
        """
        if not isinstance(result, dict):
            return False
        
        required_keys = ['assessment_summary', 'assessment_metrics', 
                         'adjustment_suggestions', 'recommendations']
        
        for key in required_keys:
            if key not in result:
                return False
        
        # 验证评估摘要（6维度）
        summary = result['assessment_summary']
        summary_fields = ['overall_rating', 'feasibility_rating',
                         'content_rating', 'time_rating', 'method_rating',
                         'progression_rating', 'personalization_rating']
        
        for field in summary_fields:
            if field not in summary:
                return False
        
        # 验证评估指标
        for metric_group in result['assessment_metrics']:
            if 'phase' not in metric_group or 'metrics' not in metric_group:
                return False
            
            for metric in metric_group['metrics']:
                metric_fields = ['name', 'description', 'target_value', 'measurement_method']
                for field in metric_fields:
                    if field not in metric:
                        return False
        
        # 验证调整建议
        for suggestion in result['adjustment_suggestions']:
            suggestion_fields = ['area', 'issue', 'suggestion', 'priority']
            for field in suggestion_fields:
                if field not in suggestion:
                    return False
        
        return True


if __name__ == "__main__":
    # 简单测试
    agent = AssessmentFeedbackAgent()
    print(f"[{agent.AGENT_NAME}] 评估反馈Agent初始化完成")
    
    test_requirement = {
        "learning_objective": "学习Python编程",
        "current_foundation": "零基础",
        "daily_available_time": "2小时",
        "learning_preference": "视频",
        "time_expectation": "快速入门"
    }
    
    test_plan = {
        "goal_feasibility": "目标可行，适合一周内快速入门",
        "estimated_duration": "约1周",
        "learning_path": {
            "stage_count": 2,
            "stages": [
                {
                    "stage_name": "第一阶段：快速入门",
                    "study_content": "Python基础语法、数据类型、基本控制流程",
                    "time_allocation": "4天",
                    "milestone": "能够编写简单的Python程序"
                },
                {
                    "stage_name": "第二阶段：实战演练",
                    "study_content": "函数定义与调用、常用内置函数、简单项目实战",
                    "time_allocation": "3天",
                    "milestone": "能够完成简单的自动化脚本"
                }
            ]
        }
    }
    
    try:
        result = agent.assess(test_requirement, test_plan)
        print("\n评估结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n验证结果: {agent.validate_result(result)}")
        print(f"指标: {agent.get_metrics()}")
    except Exception as e:
        print(f"测试失败: {e}")