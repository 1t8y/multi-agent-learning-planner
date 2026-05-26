import os
import json
import re
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import requests

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

class RequirementAnalyzerAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        self.max_tokens = 2048
        self.temperature = 0.1
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = os.path.join(
            project_root,
            ".trae",
            "agents",
            "requirement-analyzer.md"
        )
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split('\n')
                start_idx = 0
                end_idx = 0
                
                for i, line in enumerate(lines):
                    if line.startswith('---') and start_idx == 0:
                        start_idx = i
                    elif line.startswith('---') and start_idx > 0:
                        end_idx = i
                        break
                
                if end_idx > start_idx:
                    return '\n'.join(lines[end_idx+1:]).strip()
        
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return """你是一个专业的学习需求分析智能体，核心职责是处理用户的自然语言学习需求，提取关键信息并进行深度需求分析。

## 任务流程

### 第一阶段：信息提取
从用户输入中提取以下四个关键信息：
1. 学习目标（learning_objective）：用户的具体学习目标，如"学习Python编程"、"掌握机器学习基础"
2. 现有基础（current_foundation）：用户的知识水平，取值范围："零基础"、"初级"、"中级"，未提及则为 null
3. 每日可用时间（daily_available_time）：用户每天可投入学习的时间，如"2小时"、"1-2小时"
4. 偏好学习方式（learning_preference）：用户偏好的学习方式，取值范围："视频"、"文字"、"实操"，未提及则为 null

### 第二阶段：深度分析
基于提取的信息进行深度需求分析，包括：
1. 目标可行性评估：评估该学习目标的难度和可行性
2. 学习周期预估：根据现有基础和每日可用时间，预估完成该目标所需的大致时间
3. 学习路径建议：建议适合的学习阶段和重点内容
4. 资源推荐方向：根据学习方式偏好，推荐适合的学习资源类型

## 输出要求

必须以标准 JSON 格式输出，包含以下结构：

{
  "basic_info": {
    "learning_objective": "用户的学习目标",
    "current_foundation": "零基础/初级/中级/null",
    "daily_available_time": "用户的每日可用时间",
    "learning_preference": "视频/文字/实操/null"
  },
  "analysis": {
    "goal_feasibility": "目标可行性评估内容",
    "estimated_duration": "预估学习周期",
    "learning_path": "学习路径建议",
    "resource_recommendations": "资源推荐方向"
  }
}

## 注意事项
- 仅处理用户的学习需求分析，不参与其他逻辑
- basic_info 字段缺失时使用 null 值填充
- analysis 部分基于 basic_info 的完整信息进行深度分析
- 输出不得包含任何额外解释或对话内容"""

    def _extract_json(self, response_text: str) -> Optional[str]:
        match = re.search(r"\{[\s\S]*\}", response_text)
        if match:
            return match.group(0)
        return None

    def analyze(self, user_input: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input}
            ]
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            raw_response = result["choices"][0]["message"]["content"]
            
            json_str = self._extract_json(raw_response)
            if json_str:
                return json.loads(json_str)
            else:
                return {
                    "basic_info": {
                        "learning_objective": None,
                        "current_foundation": None,
                        "daily_available_time": None,
                        "learning_preference": None
                    },
                    "analysis": {
                        "goal_feasibility": "无法解析响应",
                        "estimated_duration": "无法预估",
                        "learning_path": "无法建议",
                        "resource_recommendations": "无法推荐"
                    }
                }
        
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API调用失败: {str(e)}")
        except json.JSONDecodeError:
            return {
                "basic_info": {
                    "learning_objective": None,
                    "current_foundation": None,
                    "daily_available_time": None,
                    "learning_preference": None
                },
                "analysis": {
                    "goal_feasibility": "解析失败",
                    "estimated_duration": "无法预估",
                    "learning_path": "无法建议",
                    "resource_recommendations": "无法推荐"
                }
            }

def main():
    analyzer = RequirementAnalyzerAgent()
    
    print("学习需求分析智能体已启动！")
    print("提示词已从配置文件加载")
    print("请输入您的学习需求（输入 'exit' 或 'quit' 退出）")
    print("示例：我是零基础，想学习Python编程，每天能学2小时，喜欢看视频学习")
    print("=" * 60)
    
    while True:
        user_input = input("您: ")
        
        if user_input.lower() in ["exit", "quit"]:
            print("再见！")
            break
        
        try:
            result = analyzer.analyze(user_input)
            print("\n需求分析结果:")
            print("=" * 60)
            print("【基础信息】")
            basic = result.get("basic_info", {})
            print(f"学习目标: {basic.get('learning_objective', '未指定')}")
            print(f"现有基础: {basic.get('current_foundation', '未指定')}")
            print(f"每日可用时间: {basic.get('daily_available_time', '未指定')}")
            print(f"偏好学习方式: {basic.get('learning_preference', '未指定')}")
            print("\n【分析建议】")
            analysis = result.get("analysis", {})
            print(f"目标可行性: {analysis.get('goal_feasibility', '-')}")
            print(f"预估周期: {analysis.get('estimated_duration', '-')}")
            print(f"学习路径: {analysis.get('learning_path', '-')}")
            print(f"资源推荐: {analysis.get('resource_recommendations', '-')}")
        except Exception as e:
            print(f"分析失败: {str(e)}")
        
        print("\n" + "-" * 60 + "\n")

if __name__ == "__main__":
    main()