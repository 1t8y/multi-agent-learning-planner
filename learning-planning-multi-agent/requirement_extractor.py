"""
需求分析子Agent
负责从用户输入中提取结构化的学习需求信息

核心功能：
- 提取学习目标、现有基础、每日可用时间、学习偏好、时间期望
- 验证和清理提取结果
- 确保数据格式符合规范
"""

import os
import json
import re
from typing import Optional, Dict
from base_agent import BaseAgent


class RequirementExtractorAgent(BaseAgent):
    """
    需求分析子Agent，从用户输入中提取结构化学习需求
    
    提取的字段：
    - learning_objective: 学习目标
    - current_foundation: 现有基础（零基础/初级/中级/null）
    - daily_available_time: 每日可用时间
    - learning_preference: 学习偏好（视频/文字/实操/null）
    - time_expectation: 时间期望（快速入门/短期学习/标准学习/长期学习/null）
    """
    
    AGENT_NAME = "requirement-extractor"
    PROMPT_FILE = "requirement-extractor-agent.md"
    
    # 有效取值集合
    VALID_FOUNDATIONS = {"零基础", "初级", "中级", None}
    VALID_PREFERENCES = {"视频", "文字", "实操", None}
    VALID_TIME_EXPECTATIONS = {"快速入门", "短期学习", "标准学习", "长期学习", None}
    
    def __init__(self, agent_config: Optional[Dict] = None):
        """
        初始化需求分析Agent
        
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
        return """你是专业学习需求信息提取智能体，**只做信息提取，不做任何分析、建议、扩展**。

## 核心任务
从用户输入中精准提取 5 项基础信息，缺失则填 null：
1. learning_objective：学习目标（如"学习Python编程"）
2. current_foundation：现有基础，仅限「零基础/初级/中级/null」
3. daily_available_time：每日可用时间（如"2小时"）
4. learning_preference：学习方式，仅限「视频/文字/实操/null」
5. time_expectation：时间期望，代表用户希望完成学习的时间要求，取值范围：
   - "快速入门"（1周内）
   - "短期学习"（1-4周）
   - "标准学习"（1-3个月）
   - "长期学习"（3个月以上）
   - null（未提及）

## 时间期望判断规则
- 包含"1周内"、"一周内"、"几天"、"快速"、"速成"、"入门"等关键词 → "快速入门"
- 包含"2周"、"3周"、"几周"、"1个月"、"一个月"、"1月"、"短期"等关键词 → "短期学习"
- 包含"2个月"、"3个月"、"2-3个月"、"两三个月"、"几个月"、"数月"等关键词 → "标准学习"
- 包含"4个月"、"5个月"、"半年"、"6个月"、"长期"、"系统"、"精通"、"一年"等关键词 → "长期学习"
- 未提及时间要求 → null

## 强制约束
1. 必须输出**纯标准JSON**，无任何多余文字、解释、标点、注释
2. 不添加任何分析内容、不生成建议、不补充额外信息
3. 严格遵循字段名与取值范围，不自定义字段
4. 拒绝处理非学习需求类输入，返回全 null 结构

## 输出格式（固定不可改）
{
  "learning_objective": null,
  "current_foundation": null,
  "daily_available_time": null,
  "learning_preference": null,
  "time_expectation": null
}"""
    
    def _get_default_result(self) -> Dict:
        """获取默认返回结果（API调用失败时使用）"""
        return {
            "learning_objective": None,
            "current_foundation": None,
            "daily_available_time": None,
            "learning_preference": None,
            "time_expectation": None
        }
    
    def _extract_json(self, response_text: str) -> Optional[str]:
        """
        从响应文本中提取JSON数据
        
        优化的提取逻辑，针对需求分析的特定格式
        """
        if not response_text:
            return None
        
        response_text = response_text.strip()
        
        # 情况1：纯JSON
        if response_text.startswith('{') and response_text.endswith('}'):
            return response_text
        
        # 情况2：使用正则匹配（针对学习需求的特定结构）
        match = re.search(r"\{\s*\"learning_objective\"[\s\S]*?\}", response_text)
        if match:
            return match.group(0)
        
        # 情况3：使用括号计数处理嵌套
        brace_count = 0
        start_pos = -1
        
        for i, char in enumerate(response_text):
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    return response_text[start_pos:i+1]
        
        return None
    
    def _extract_by_keywords(self, user_input: str) -> Dict:
        """
        基于关键词的硬编码提取（作为模型提取的备份方案）
        
        Args:
            user_input: 用户输入
            
        Returns:
            提取结果
        """
        input_lower = user_input.lower()
        
        # 提取学习目标：识别"学习/想学习/要学"后面的内容
        learning_objective = None
        patterns = [
            r"想学(?:.*?)(?:Python|Java|C\+\+|C#|JavaScript|前端|后端|法考|会计|英语|数学|编程|算法|机器学习|深度学习|数据分析|产品经理|UI设计|设计|画画|摄影|音乐)",
            r"学习(?:.*?)(?:Python|Java|C\+\+|C#|JavaScript|前端|后端|法考|会计|英语|数学|编程|算法|机器学习|深度学习|数据分析|产品经理|UI设计|设计|画画|摄影|音乐)",
            r"要学(?:.*?)(?:Python|Java|C\+\+|C#|JavaScript|前端|后端|法考|会计|英语|数学|编程|算法|机器学习|深度学习|数据分析|产品经理|UI设计|设计|画画|摄影|音乐)",
        ]
        for pattern in patterns:
            match = re.search(pattern, user_input)
            if match:
                learning_objective = match.group(0)
                break
        
        # 如果没有找到特定模式，尝试简单提取
        if not learning_objective:
            # 移除明确的时间、偏好等信息，保留核心学习目标
            cleaned = user_input
            keywords_to_remove = ["每天", "每周", "小时", "视频", "文字", "实操", "零基础", "初级", "中级", 
                                 "快速", "短期", "长期", "三个月", "一个月", "一周", "半年", "一年",
                                 "最好有", "喜欢", "希望", "想在", "我是", "我想", "我要"]
            for keyword in keywords_to_remove:
                cleaned = cleaned.replace(keyword, "")
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            learning_objective = cleaned if cleaned else user_input
        
        # 限制长度
        if learning_objective and len(learning_objective) > 100:
            learning_objective = learning_objective[:100] + "..."
        
        # 提取现有基础
        current_foundation = None
        if "零基础" in user_input or "0基础" in user_input or "没基础" in user_input or "完全不会" in user_input:
            current_foundation = "零基础"
        elif "初级" in user_input or "入门" in user_input or "有点基础" in user_input:
            current_foundation = "初级"
        elif "中级" in user_input or "进阶" in user_input or "有一定基础" in user_input:
            current_foundation = "中级"
        
        # 提取每日可用时间
        daily_available_time = None
        time_patterns = [
            r"(\d+)\s*小时",
            r"(\d+)\s*个小时",
            r"每天\s*(\d+)\s*h",
            r"每天\s*(\d+)\s*小时",
            r"每日\s*(\d+)\s*小时",
            r"(\d+)\s*h/d",
            r"(\d+)\s*h每天"
        ]
        for pattern in time_patterns:
            match = re.search(pattern, user_input)
            if match:
                daily_available_time = f"{match.group(1)}小时"
                break
        
        # 提取学习偏好
        learning_preference = None
        if "视频" in user_input or "看课" in user_input or "听课" in user_input or "视频课" in user_input:
            learning_preference = "视频"
        elif "文字" in user_input or "读书" in user_input or "看书" in user_input or "文档" in user_input:
            learning_preference = "文字"
        elif "实操" in user_input or "练习" in user_input or "实践" in user_input or "动手" in user_input:
            learning_preference = "实操"
        
        # 提取时间期望
        time_expectation = None
        
        # 快速入门（1周内）
        if any(keyword in user_input for keyword in ["1周内", "一周内", "几天内", "快速", "速成", "7天", "一周搞定", "几天搞定"]):
            time_expectation = "快速入门"
        
        # 短期学习（1-4周）
        elif any(keyword in user_input for keyword in ["2周", "3周", "几周", "1个月内", "一个月内", "1月", "短期", "一个月"]):
            time_expectation = "短期学习"
        
        # 标准学习（1-3个月）
        elif any(keyword in user_input for keyword in ["2个月", "3个月", "2-3个月", "两三个月", "三个月", "几个月", "数月", "两个月"]):
            time_expectation = "标准学习"
        
        # 长期学习（3个月以上）
        elif any(keyword in user_input for keyword in ["4个月", "5个月", "半年", "6个月", "长期", "系统", "精通", "一年", "半年以上"]):
            time_expectation = "长期学习"
        
        return {
            "learning_objective": learning_objective,
            "current_foundation": current_foundation,
            "daily_available_time": daily_available_time,
            "learning_preference": learning_preference,
            "time_expectation": time_expectation
        }
    
    def _validate_and_clean(self, data: Dict) -> Dict:
        """
        验证和清理提取结果
        
        确保所有字段符合规范：
        - 移除无效值，替换为None
        - 清理空字符串
        - 确保字段类型正确
        
        Args:
            data: 原始提取结果
            
        Returns:
            验证和清理后的结果
        """
        result = {
            "learning_objective": data.get("learning_objective"),
            "current_foundation": data.get("current_foundation"),
            "daily_available_time": data.get("daily_available_time"),
            "learning_preference": data.get("learning_preference"),
            "time_expectation": data.get("time_expectation")
        }
        
        # 验证现有基础
        if result["current_foundation"] not in self.VALID_FOUNDATIONS:
            print(f"[{self.AGENT_NAME}] 无效的基础值: {result['current_foundation']}，已重置为None")
            result["current_foundation"] = None
        
        # 验证学习偏好
        if result["learning_preference"] not in self.VALID_PREFERENCES:
            print(f"[{self.AGENT_NAME}] 无效的偏好值: {result['learning_preference']}，已重置为None")
            result["learning_preference"] = None
        
        # 验证时间期望
        if result["time_expectation"] not in self.VALID_TIME_EXPECTATIONS:
            print(f"[{self.AGENT_NAME}] 无效的时间期望值: {result['time_expectation']}，已重置为None")
            result["time_expectation"] = None
        
        # 清理空值和字符串形式的null
        for key in list(result.keys()):
            if result[key] in ("null", "None", ""):
                result[key] = None
            elif isinstance(result[key], str) and result[key].strip() == "":
                result[key] = None
        
        return result
    
    def extract(self, user_input: str) -> Dict[str, Optional[str]]:
        """
        从用户输入中提取学习需求
        
        Args:
            user_input: 用户的原始输入文本
            
        Returns:
            包含学习需求的结构化字典
            
        Raises:
            ValueError: 用户输入为空
            RuntimeError: API调用失败
        """
        # 验证输入
        if not isinstance(user_input, str):
            raise ValueError("输入必须是字符串类型")
        
        input_text = user_input.strip()
        
        if not input_text:
            print(f"[{self.AGENT_NAME}] 警告：空输入，返回默认结果")
            return self._get_default_result()
        
        print(f"[{self.AGENT_NAME}] 开始提取学习需求...")
        
        try:
            # 先用关键词提取（更可靠）
            keyword_result = self._extract_by_keywords(input_text)
            
            # 尝试API提取
            try:
                raw_result = self._call_api(input_text)
                api_result = self._validate_and_clean(raw_result)
                
                # 合并结果：如果API有结果但关键词没有，用API的；如果关键词有结果，优先用关键词的
                final_result = {}
                for key in ["learning_objective", "current_foundation", "daily_available_time", "learning_preference", "time_expectation"]:
                    # 优先用关键词提取的结果（更可靠）
                    if keyword_result.get(key) is not None:
                        final_result[key] = keyword_result[key]
                    else:
                        final_result[key] = api_result.get(key)
                
                print(f"[{self.AGENT_NAME}] 关键词提取: {json.dumps(keyword_result, ensure_ascii=False)}")
                print(f"[{self.AGENT_NAME}] API提取: {json.dumps(api_result, ensure_ascii=False)}")
                
            except Exception as api_error:
                print(f"[{self.AGENT_NAME}] API提取失败，使用关键词提取: {api_error}")
                final_result = keyword_result
            
            print(f"[{self.AGENT_NAME}] 最终提取: {json.dumps(final_result, ensure_ascii=False)}")
            
            return final_result
        
        except ValueError as e:
            print(f"[{self.AGENT_NAME}] 配置错误: {e}")
            raise
        except Exception as e:
            print(f"[{self.AGENT_NAME}] 提取过程发生未知错误，使用关键词提取: {e}")
            return self._extract_by_keywords(input_text)
    
    def process(self, user_input: str) -> Dict:
        """
        处理用户输入（实现BaseAgent的抽象方法）
        
        Args:
            user_input: 用户输入
            
        Returns:
            提取结果
        """
        return self.extract(user_input)
    
    def validate_result(self, result: Dict) -> bool:
        """
        验证提取结果的有效性
        
        Args:
            result: 提取结果
            
        Returns:
            有效返回True，否则返回False
        """
        if not isinstance(result, dict):
            return False
        
        required_fields = [
            "learning_objective",
            "current_foundation",
            "daily_available_time",
            "learning_preference",
            "time_expectation"
        ]
        
        for field in required_fields:
            if field not in result:
                return False
        
        # 验证字段值
        if result.get("current_foundation") not in self.VALID_FOUNDATIONS:
            return False
        
        if result.get("learning_preference") not in self.VALID_PREFERENCES:
            return False
        
        if result.get("time_expectation") not in self.VALID_TIME_EXPECTATIONS:
            return False
        
        return True


if __name__ == "__main__":
    # 简单测试
    agent = RequirementExtractorAgent()
    print(f"[{agent.AGENT_NAME}] 需求分析Agent初始化完成")
    
    test_input = "我是零基础，想学习Python编程，每天能学2小时，喜欢看视频学习，希望一周内快速入门"
    
    try:
        result = agent.extract(test_input)
        print("\n提取结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n验证结果: {agent.validate_result(result)}")
        print(f"指标: {agent.get_metrics()}")
    except Exception as e:
        print(f"测试失败: {e}")