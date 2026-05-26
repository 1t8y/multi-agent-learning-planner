"""
配置管理模块
提供统一的配置加载和管理功能
"""

import os
import json
from typing import Dict, Optional, Any
from dotenv import load_dotenv


class ConfigManager:
    """配置管理器，负责加载和管理所有配置"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_config()
        return cls._instance
    
    def _init_config(self):
        """初始化配置，按优先级加载"""
        self._load_env()
        self._load_defaults()
        self._load_json_config()
    
    def _load_env(self):
        """加载环境变量"""
        project_root = self._get_project_root()
        env_path = os.path.join(project_root, ".env")
        
        if os.path.exists(env_path):
            load_dotenv(env_path)
        
        self._config['env'] = {
            'deepseek_api_key': os.getenv('DEEPSEEK_API_KEY', ''),
            'hermes_api_key': os.getenv('HERMES_API_KEY', ''),
            'api_base_url': os.getenv('API_BASE_URL', 'https://api.deepseek.com/v1/chat/completions'),
            'hermes_api_base': os.getenv('HERMES_API_BASE', 'http://127.0.0.1:8642')
        }
    
    def _load_defaults(self):
        """加载默认配置"""
        self._config['defaults'] = {
            'model': 'deepseek-chat',
            'max_tokens': 2048,
            'temperature': 0.3,
            'timeout': 30,
            'retry_count': 2,
            'sync_mode': 'trae_to_hermes'
        }
    
    def _load_json_config(self):
        """加载JSON配置文件"""
        config_paths = [
            os.path.join(self._get_project_root(), '.trae', 'config', 'hermes_sync.json'),
            os.path.join(self._get_project_root(), 'config', 'config.json')
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        self._config.update(config_data)
                except Exception as e:
                    self._log_error(f"加载配置文件失败 {config_path}: {e}")
    
    def _get_project_root(self) -> str:
        """获取项目根目录"""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def _log_error(self, message: str):
        """记录错误日志"""
        print(f"[ConfigManager] {message}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点路径访问"""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_api_key(self) -> str:
        """获取API密钥"""
        return self.get('env.deepseek_api_key', '')
    
    def get_api_base_url(self) -> str:
        """获取API基础URL"""
        return self.get('env.api_base_url', 'https://api.deepseek.com/v1/chat/completions')
    
    def get_model_config(self) -> Dict[str, Any]:
        """获取模型配置"""
        return {
            'model': self.get('defaults.model', 'deepseek-chat'),
            'max_tokens': self.get('defaults.max_tokens', 2048),
            'temperature': self.get('defaults.temperature', 0.3),
            'timeout': self.get('defaults.timeout', 30),
            'retry_count': self.get('defaults.retry_count', 2)
        }
    
    def get_hermes_config(self) -> Dict[str, Any]:
        """获取Hermes配置"""
        return {
            'api_base_url': self.get('api_base_url', 'http://127.0.0.1:8642'),
            'api_key': self.get('api_key', ''),
            'auth_type': self.get('auth_type', 'bearer'),
            'cli_path': self.get('cli_path', 'hermes'),
            'sync_mode': self.get('sync_mode', 'trae_to_hermes'),
            'status_mapping': self.get('status_mapping', {}),
            'endpoints': self.get('endpoints', {})
        }
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """获取指定Agent的配置"""
        agent_configs = self.get('agent_configs', {})
        return agent_configs.get(agent_name, {})
    
    def validate(self) -> bool:
        """验证配置完整性"""
        errors = []
        
        if not self.get_api_key():
            errors.append("DEEPSEEK_API_KEY 未配置")
        
        if errors:
            print("[ConfigManager] 配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    def print_summary(self):
        """打印配置摘要"""
        print("\n" + "="*60)
        print("配置摘要")
        print("="*60)
        print(f"API Key: {'已配置' if self.get_api_key() else '未配置'}")
        print(f"API Base URL: {self.get_api_base_url()}")
        print(f"模型: {self.get('defaults.model')}")
        print(f"最大Token: {self.get('defaults.max_tokens')}")
        print(f"温度: {self.get('defaults.temperature')}")
        print(f"Hermes CLI路径: {self.get('cli_path', 'hermes')}")
        print("="*60 + "\n")


# 全局配置实例
config = ConfigManager()


if __name__ == "__main__":
    config.print_summary()
    print("配置验证:", "通过" if config.validate() else "失败")