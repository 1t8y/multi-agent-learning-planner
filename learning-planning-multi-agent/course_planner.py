"""
课程规划子Agent
负责基于提取的学习需求生成个性化学习计划

核心功能：
- 根据学习目标、基础、时间期望生成分阶段学习计划
- 支持动态调整阶段数量和内容深度
- 输出结构化的学习路径
"""

import os
import json
import re
from typing import Optional, Dict
from base_agent import BaseAgent


class CoursePlannerAgent(BaseAgent):
    """
    课程规划子Agent，生成个性化学习计划
    
    输入：
    - learning_objective: 学习目标
    - current_foundation: 现有基础
    - daily_available_time: 每日可用时间
    - learning_preference: 学习偏好
    - time_expectation: 时间期望
    
    输出：
    - goal_feasibility: 目标可行性评估
    - estimated_duration: 预估周期
    - learning_path: 学习路径（包含阶段信息）
    - resource_recommendations: 资源推荐建议
    """
    
    AGENT_NAME = "course-planner"
    PROMPT_FILE = "course-planner-agent.md"
    
    def __init__(self, agent_config: Optional[Dict] = None):
        """
        初始化课程规划Agent
        
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
        return """你是专业**学习规划专家**，仅接收**需求分析子Agent传递的结构化数据**，不处理原始用户需求、不重新提取信息、不向用户追问，严格按照**链式思考（CoT）** 逻辑完成学习路径规划。

## 核心职责
基于结构化基础信息，通过CoT推导生成**分阶段、可执行、带时间分配与里程碑**的学习计划，仅负责课程规划，不承担需求提取、资源推荐、效果评估等其他任务。

## 输入参数说明
输入数据包含以下字段：
- learning_objective: 学习目标（如"学习Python编程"）
- current_foundation: 现有基础（零基础/初级/中级/null）
- daily_available_time: 每日可用时间（如"2小时"）
- learning_preference: 学习偏好（视频/文字/实操/null）
- time_expectation: 时间期望（快速入门/短期学习/标准学习/长期学习/null）

## 时间期望对应的学习规划策略
1. **快速入门（1周内）**：仅保留最核心、最基础的内容，聚焦入门必备知识
   - 阶段数：1-2个
   - 重点：快速上手、核心概念
   - 省略：高级特性、深入原理

2. **短期学习（1-4周）**：精简但全面的学习路径，覆盖核心技能
   - 阶段数：2-3个
   - 重点：核心知识体系、基础实践
   - 省略：深入进阶内容

3. **标准学习（1-3个月）**：完整的学习路径，系统掌握知识
   - 阶段数：3-4个
   - 重点：完整知识体系、项目实践

4. **长期学习（3个月以上）**：深入全面的学习路径，达到精通水平
   - 阶段数：4-5个
   - 重点：深入原理、高级特性、大量实践

5. **未指定（null）**：默认按标准学习规划

## 链式思考（CoT）执行步骤
1. **需求拆解**：解析学习目标、现有基础、每日可用时间、学习偏好、时间期望，明确核心约束
2. **可行性判断**：评估目标难度与实现可行性，结合时间期望、每日时间与基础估算总周期
3. **阶段划分**：根据时间期望决定阶段数量，按「基础→进阶→实战」拆分学习流程
4. **时间分配**：按时间期望和总周期拆分各阶段时长，匹配每日可用时间
5. **内容规划**：根据时间期望决定内容深度，贴合基础与目标
6. **里程碑设定**：为每个阶段设置可量化、可验证的完成标准
7. **结果整合**：输出结构化、可直接执行的完整学习计划

## 学习计划输出标准
输出必须包含固定结构，确保清晰、可落地：
- 阶段划分：总阶段数、阶段名称（根据时间期望调整）
- 各阶段学习内容：具体知识点/技能点（根据时间期望调整深度）
- 时间分配：阶段总时长、每日学习安排（匹配时间期望）
- 阶段里程碑：可量化的阶段完成判定标准

## 强制约束
1. 仅输出**纯标准JSON**，无多余文字、解释、注释
2. 无有效输入时，所有字段返回「信息不足，无法规划」
3. 严格遵循固定输出结构，不增删、不修改字段名
4. 学习计划贴合用户实际情况和时间期望，具备可执行性
5. 根据time_expectation动态调整学习内容深度和阶段数量

## 输出格式（固定不可修改）
{
  "goal_feasibility": "",
  "estimated_duration": "",
  "learning_path": {
    "stage_count": "",
    "stages": [
      {
        "stage_name": "",
        "study_content": "",
        "time_allocation": "",
        "milestone": ""
      }
    ]
  },
  "resource_recommendations": ""
}"""
    
    def _get_default_result(self) -> Dict:
        """获取默认返回结果（API调用失败时使用）"""
        return {
            "goal_feasibility": "信息不足，无法规划",
            "estimated_duration": "信息不足，无法规划",
            "learning_path": {
                "stage_count": 0,
                "stages": []
            },
            "resource_recommendations": "信息不足，无法规划"
        }
    
    def plan(self, requirement_data: Dict) -> Dict:
        """
        根据学习需求生成学习计划
        
        Args:
            requirement_data: 结构化的学习需求信息
            
        Returns:
            包含学习计划的字典
            
        Raises:
            ValueError: 输入数据无效
            RuntimeError: API调用失败
        """
        # 验证输入
        if not isinstance(requirement_data, dict):
            raise ValueError("输入必须是字典类型")
        
        if not requirement_data.get("learning_objective"):
            print(f"[{self.AGENT_NAME}] 警告：缺少学习目标，返回默认结果")
            return self._get_default_result()
        
        print(f"[{self.AGENT_NAME}] 开始生成学习计划...")
        print(f"[{self.AGENT_NAME}] 输入需求: {json.dumps(requirement_data, ensure_ascii=False)}")
        
        try:
            # 将需求数据转换为JSON字符串作为输入
            input_json = json.dumps(requirement_data, ensure_ascii=False)
            
            # 调用API生成学习计划
            result = self._call_api(input_json)
            
            print(f"[{self.AGENT_NAME}] 学习计划生成完成")
            
            return result
        
        except ValueError as e:
            print(f"[{self.AGENT_NAME}] 配置错误: {e}")
            raise
        except RuntimeError as e:
            print(f"[{self.AGENT_NAME}] API调用失败: {e}")
            return self._get_default_result()
        except json.JSONDecodeError:
            print(f"[{self.AGENT_NAME}] JSON解析失败")
            return self._get_default_result()
        except Exception as e:
            print(f"[{self.AGENT_NAME}] 规划过程发生未知错误: {e}")
            return self._get_default_result()
    
    def process(self, requirement_data: Dict) -> Dict:
        """
        处理学习需求（实现BaseAgent的抽象方法）
        
        Args:
            requirement_data: 学习需求数据
            
        Returns:
            学习计划结果
        """
        return self.plan(requirement_data)
    
    def validate_result(self, result: Dict) -> bool:
        """
        验证学习计划结果的有效性
        
        Args:
            result: 学习计划结果
            
        Returns:
            有效返回True，否则返回False
        """
        if not isinstance(result, dict):
            return False
        
        required_fields = ["goal_feasibility", "estimated_duration", "learning_path"]
        
        for field in required_fields:
            if field not in result:
                return False
        
        learning_path = result.get("learning_path", {})
        if not isinstance(learning_path, dict):
            return False
        
        if "stage_count" not in learning_path or "stages" not in learning_path:
            return False
        
        if not isinstance(learning_path["stages"], list):
            return False
        
        for stage in learning_path["stages"]:
            stage_fields = ["stage_name", "study_content", "time_allocation", "milestone"]
            for field in stage_fields:
                if field not in stage:
                    return False
        
        return True


if __name__ == "__main__":
    # 简单测试
    agent = CoursePlannerAgent()
    print(f"[{agent.AGENT_NAME}] 课程规划Agent初始化完成")
    
    test_requirement = {
        "learning_objective": "学习Python编程",
        "current_foundation": "零基础",
        "daily_available_time": "2小时",
        "learning_preference": "视频",
        "time_expectation": "快速入门"
    }
    
    try:
        result = agent.plan(test_requirement)
        print("\n学习计划:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n验证结果: {agent.validate_result(result)}")
        print(f"指标: {agent.get_metrics()}")
    except Exception as e:
        print(f"测试失败: {e}")