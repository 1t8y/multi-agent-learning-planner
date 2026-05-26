"""
基础Agent类
提供所有子Agent的通用功能和接口定义

核心功能：
- API调用封装（带重试机制）
- JSON响应提取
- 系统提示词加载
- 性能监控与指标收集
"""

import os
import json
import re
import time
from typing import Optional, Dict, Any, Callable
from abc import ABC, abstractmethod
from config import config


class BaseAgent(ABC):
    """
    所有Agent的基类，提供通用功能
    
    Attributes:
        config: Agent配置字典
        api_key: API密钥
        base_url: API基础地址
        model: 使用的模型名称
        max_tokens: 最大token数
        temperature: 温度参数
        timeout: 请求超时时间（秒）
        retry_count: 重试次数
        system_prompt: 系统提示词
        call_count: API调用次数
        error_count: 错误次数
        last_execution_time: 上次执行时间（秒）
    """
    
    def __init__(self, agent_config: Optional[Dict] = None):
        """
        初始化Agent
        
        Args:
            agent_config: Agent特定配置，会覆盖默认配置
        """
        self.config = agent_config or {}
        self._configure()
        self._setup_monitoring()
    
    def _configure(self):
        """配置Agent参数，优先级：Agent配置 > 全局配置 > 默认值"""
        # 从全局配置获取基础参数
        model_config = config.get_model_config()
        
        # API配置
        self.api_key = self.config.get('api_key') or config.get_api_key()
        self.base_url = self.config.get('base_url') or config.get_api_base_url()
        
        # 模型配置
        self.model = self.config.get('model') or model_config.get('model')
        self.max_tokens = self.config.get('max_tokens') or model_config.get('max_tokens')
        self.temperature = self.config.get('temperature') or model_config.get('temperature')
        self.timeout = self.config.get('timeout') or model_config.get('timeout')
        self.retry_count = self.config.get('retry_count') or model_config.get('retry_count')
        
        # 加载系统提示词
        self.system_prompt = self._load_system_prompt()
    
    def _setup_monitoring(self):
        """初始化监控指标"""
        self.last_execution_time = 0.0
        self.call_count = 0
        self.error_count = 0
    
    def _load_system_prompt(self) -> str:
        """
        加载系统提示词
        
        优先从配置的prompt文件加载，如果不存在则使用默认提示词
        """
        prompt_path = self._get_prompt_path()
        
        if prompt_path and os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    return self._parse_markdown_prompt(content)
            except Exception as e:
                print(f"[{self.__class__.__name__}] 加载提示词文件失败: {e}")
        
        return self._get_default_prompt()
    
    def _parse_markdown_prompt(self, content: str) -> str:
        """
        解析Markdown格式的提示词
        
        提取Markdown文件中---分隔符后的内容作为提示词
        """
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
        
        return content.strip()
    
    @abstractmethod
    def _get_prompt_path(self) -> Optional[str]:
        """
        获取提示词文件路径
        
        子类必须实现此方法，返回提示词文件的绝对路径
        """
        pass
    
    @abstractmethod
    def _get_default_prompt(self) -> str:
        """
        获取默认提示词
        
        子类必须实现此方法，提供默认的系统提示词
        """
        pass
    
    @abstractmethod
    def _get_default_result(self) -> Dict:
        """
        获取默认返回结果
        
        子类必须实现此方法，提供API调用失败时的默认返回值
        """
        pass
    
    def _extract_json(self, response_text: str) -> Optional[str]:
        """
        从响应文本中提取JSON数据
        
        支持多种格式：
        1. 纯JSON（以{开头，以}结尾）
        2. 文本中的JSON片段（使用正则匹配）
        3. 嵌套JSON（使用括号计数）
        
        Args:
            response_text: 原始响应文本
        
        Returns:
            提取的JSON字符串，失败返回None
        """
        if not response_text:
            return None
        
        response_text = response_text.strip()
        
        # 情况1：纯JSON
        if response_text.startswith('{') and response_text.endswith('}'):
            return response_text
        
        # 情况2：使用正则匹配
        match = re.search(r"\{[\s\S]*\}", response_text)
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
    
    def _call_api(self, user_message: str) -> Dict:
        """
        调用DeepSeek API
        
        包含重试机制，支持指数退避策略
        
        Args:
            user_message: 用户消息
            
        Returns:
            解析后的JSON响应
            
        Raises:
            ValueError: API密钥未设置
            RuntimeError: API调用失败（已重试最大次数）
        """
        # 验证API密钥
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请检查环境变量或配置文件")
        
        # 构建请求头和负载
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message}
            ]
        }
        
        # 导入requests（延迟导入以优化启动时间）
        import requests
        
        last_exception = None
        
        # 带重试的API调用
        for attempt in range(self.retry_count + 1):
            try:
                start_time = time.time()
                
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # 更新监控指标
                self.last_execution_time = time.time() - start_time
                self.call_count += 1
                
                # 解析响应
                result = response.json()
                raw_response = result["choices"][0]["message"]["content"]
                
                # 提取JSON
                json_str = self._extract_json(raw_response)
                if json_str:
                    return json.loads(json_str)
                
                # 返回默认结果
                return self._get_default_result()
            
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.retry_count:
                    # 指数退避
                    time.sleep(2 ** attempt)
                    print(f"[{self.__class__.__name__}] API调用失败，正在重试 ({attempt+1}/{self.retry_count})...")
                continue
            except json.JSONDecodeError:
                print(f"[{self.__class__.__name__}] JSON解析失败")
                return self._get_default_result()
        
        # 所有重试都失败
        self.error_count += 1
        raise RuntimeError(f"API调用失败（已重试{self.retry_count}次）: {str(last_exception)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取Agent的性能指标
        
        Returns:
            包含调用次数、错误次数、执行时间和成功率的字典
        """
        success_count = self.call_count - self.error_count
        success_rate = 0.0 if self.call_count == 0 else success_count / self.call_count
        
        return {
            'call_count': self.call_count,
            'error_count': self.error_count,
            'last_execution_time': round(self.last_execution_time, 2),
            'success_rate': round(success_rate, 4)
        }
    
    def validate_config(self) -> bool:
        """
        验证配置是否完整
        
        Returns:
            配置有效返回True，否则返回False
        """
        if not self.api_key:
            print(f"[{self.__class__.__name__}] 错误：API密钥未设置")
            return False
        
        if not self.system_prompt:
            print(f"[{self.__class__.__name__}] 错误：系统提示词为空")
            return False
        
        return True
    
    @abstractmethod
    def process(self, *args, **kwargs) -> Dict:
        """
        处理用户请求的抽象方法
        
        子类必须实现此方法，定义具体的业务逻辑
        
        Returns:
            处理结果（字典格式）
        """
        pass