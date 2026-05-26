"""
资源推荐子Agent
负责根据学习需求和学习计划推荐合适的学习资源

核心功能：
- 根据学习目标、阶段、偏好推荐资源
- 支持多种资源类型（视频、文字、实战项目、文档）
- 输出结构化资源列表
"""

import os
import json
from typing import Optional, Dict
from base_agent import BaseAgent


class ResourceRecommenderAgent(BaseAgent):
    """
    资源推荐子Agent，为学习计划匹配资源
    
    输入：
    - requirement_info: 学习需求信息
    - learning_plan: 学习计划
    
    输出：
    - resources: 资源列表（包含阶段、类型、标题、描述、时长、难度、推荐理由）
    """
    
    AGENT_NAME = "resource-recommender"
    PROMPT_FILE = "resource-recommender-agent.md"
    
    # 支持的资源类型
    RESOURCE_TYPES = ["视频教程", "文字教程", "实战项目", "文档资料"]
    
    def __init__(self, agent_config: Optional[Dict] = None):
        """
        初始化资源推荐Agent
        
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
        return """你是专业学习资源推荐专家，仅接收主Agent传递的学习需求和学习计划，匹配学习阶段推荐最合适的学习资源。

## 核心职责
根据学习目标、现有基础、学习偏好和学习阶段，推荐相应的学习资源，输出结构化资源列表。

## 输入信息
- requirement_info: 学习需求信息（包含学习目标、现有基础、每日可用时间、学习偏好、时间期望）
- learning_plan: 学习计划（包含学习路径、阶段信息）

## 资源类型
- 视频教程：适合视觉学习和入门，提供直观的演示和讲解
- 文字教程：适合深入理解和查阅，便于反复研读
- 实战项目：适合技能巩固和实践，提升动手能力
- 文档资料：适合专业知识学习，获取权威信息

## 推荐原则
1. 匹配学习阶段：为每个阶段推荐适合的资源
2. 考虑学习偏好：优先推荐用户偏好的资源类型
3. 平衡难度：根据用户基础推荐合适难度的资源
4. 多样性：同一阶段推荐不同类型的资源供选择

## 强制约束
1. 仅输出**纯标准JSON**，无多余文字、解释、注释
2. 严格遵循固定输出结构，不增删、不修改字段名
3. 资源推荐必须与学习计划的阶段对应
4. 每个阶段至少推荐1个资源

## 输出格式（固定不可修改）
{
  "resources": [
    {
      "phase": "",
      "type": "",
      "title": "",
      "description": "",
      "duration": "",
      "difficulty": "",
      "recommendation_reason": "",
      "url": ""
    }
  ]
}"""
    
    def _get_default_result(self) -> Dict:
        """获取默认返回结果（API调用失败时使用）"""
        return {"resources": []}
    
    def recommend(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """
        根据学习需求和学习计划推荐资源
        
        Args:
            requirement_info: 学习需求信息
            learning_plan: 学习计划
            
        Returns:
            包含资源列表的字典
            
        Raises:
            ValueError: 输入数据无效
        """
        # 验证输入
        if not isinstance(requirement_info, dict) or not isinstance(learning_plan, dict):
            raise ValueError("输入必须是字典类型")
        
        if not requirement_info.get("learning_objective"):
            print(f"[{self.AGENT_NAME}] 警告：缺少学习目标，返回空资源列表")
            return self._get_default_result()
        
        print(f"[{self.AGENT_NAME}] 开始推荐学习资源...")
        
        try:
            # 构建输入数据
            input_data = {
                "requirement_info": requirement_info,
                "learning_plan": learning_plan
            }
            input_json = json.dumps(input_data, ensure_ascii=False)
            
            # 调用API推荐资源
            result = self._call_api(input_json)
            
            print(f"[{self.AGENT_NAME}] 资源推荐完成，共推荐 {len(result.get('resources', []))} 个资源")
            
            return result
        
        except ValueError as e:
            print(f"[{self.AGENT_NAME}] 配置错误: {e}")
            raise
        except RuntimeError as e:
            print(f"[{self.AGENT_NAME}] API调用失败: {e}")
            return self._get_default_result()
        except Exception as e:
            print(f"[{self.AGENT_NAME}] 资源推荐过程发生未知错误: {e}")
            return self._get_default_result()
    
    def process(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """
        处理请求（实现BaseAgent的抽象方法）
        
        Args:
            requirement_info: 学习需求信息
            learning_plan: 学习计划
            
        Returns:
            资源推荐结果
        """
        return self.recommend(requirement_info, learning_plan)
    
    def batch_recommend(self, batch_data: list) -> list:
        """
        批量推荐资源
        
        Args:
            batch_data: 批量数据列表，每个元素包含requirement_info和learning_plan
            
        Returns:
            批量推荐结果列表
        """
        results = []
        for item in batch_data:
            req_info = item.get("requirement_info", {})
            learn_plan = item.get("learning_plan", {})
            result = self.process(req_info, learn_plan)
            results.append(result)
        return results
    
    def validate_result(self, result: Dict) -> bool:
        """
        验证资源推荐结果的有效性
        
        Args:
            result: 资源推荐结果
            
        Returns:
            有效返回True，否则返回False
        """
        if not isinstance(result, dict):
            return False
        
        if "resources" not in result:
            return False
        
        if not isinstance(result["resources"], list):
            return False
        
        required_fields = [
            "phase",
            "type",
            "title",
            "description",
            "duration",
            "difficulty",
            "recommendation_reason"
        ]
        
        for resource in result["resources"]:
            if not isinstance(resource, dict):
                return False
            
            for field in required_fields:
                if field not in resource:
                    return False
            
            # 验证资源类型
            if resource.get("type") not in self.RESOURCE_TYPES:
                print(f"[{self.AGENT_NAME}] 警告：无效的资源类型: {resource.get('type')}")
        
        return True


if __name__ == "__main__":
    # 简单测试
    agent = ResourceRecommenderAgent()
    print(f"[{agent.AGENT_NAME}] 资源推荐Agent初始化完成")
    
    test_requirement = {
        "learning_objective": "学习Python编程",
        "current_foundation": "零基础",
        "daily_available_time": "2小时",
        "learning_preference": "视频",
        "time_expectation": "快速入门"
    }
    
    test_plan = {
        "goal_feasibility": "可行",
        "estimated_duration": "1周",
        "learning_path": {
            "stage_count": 2,
            "stages": [
                {
                    "stage_name": "第一阶段：基础入门",
                    "study_content": "Python基础语法、变量、数据类型",
                    "time_allocation": "3天",
                    "milestone": "掌握基础语法"
                },
                {
                    "stage_name": "第二阶段：实战演练",
                    "study_content": "函数、流程控制、简单项目",
                    "time_allocation": "4天",
                    "milestone": "完成简单项目"
                }
            ]
        }
    }
    
    try:
        result = agent.recommend(test_requirement, test_plan)
        print("\n资源推荐结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n验证结果: {agent.validate_result(result)}")
        print(f"指标: {agent.get_metrics()}")
    except Exception as e:
        print(f"测试失败: {e}")