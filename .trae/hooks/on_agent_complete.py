import os
import json
import requests
from typing import Dict, Optional


class HermesSyncHook:
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'hermes_sync.json'
        )
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _get_hermes_task_id(self, agent_name: str) -> Optional[str]:
        agent_config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'agents',
            f'{agent_name}.md'
        )
        if os.path.exists(agent_config_path):
            with open(agent_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'hermes_task_id:' in content:
                    import re
                    match = re.search(r'hermes_task_id:\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
        return None
    
    def _build_headers(self) -> Dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        auth_type = self.config.get('auth_type', 'bearer')
        api_key = self.config.get('api_key', '')
        
        if auth_type == 'bearer' and api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        return headers
    
    def _get_endpoint(self, endpoint_key: str, **kwargs) -> str:
        base_url = self.config.get('api_base_url', 'http://127.0.0.1:8642')
        endpoint = self.config.get('endpoints', {}).get(endpoint_key, '')
        
        for key, value in kwargs.items():
            endpoint = endpoint.replace(f'{{{key}}}', str(value))
        
        return f'{base_url}{endpoint}'
    
    def update_hermes_task_status(self, agent_name: str, status: str) -> bool:
        task_id = self._get_hermes_task_id(agent_name)
        if not task_id:
            print(f"[Hermes Sync] 未找到 Agent '{agent_name}' 的 hermes_task_id 配置")
            return False
        
        hermes_status = self._map_status_to_hermes(status)
        if not hermes_status:
            print(f"[Hermes Sync] 不支持的状态: {status}")
            return False
        
        return self._send_status_update(task_id, hermes_status)
    
    def _map_status_to_hermes(self, trae_status: str) -> Optional[str]:
        mapping = self.config.get('status_mapping', {}).get('trae_to_hermes', {})
        return mapping.get(trae_status.lower())
    
    def _send_status_update(self, task_id: str, status: str) -> bool:
        endpoint = self._get_endpoint('job', job_id=task_id)
        headers = self._build_headers()
        
        payload = {
            'status': status,
            'updated_at': self._get_current_timestamp()
        }
        
        try:
            response = requests.patch(endpoint, headers=headers, json=payload)
            if response.status_code == 200:
                print(f"[Hermes Sync] 任务 {task_id} 状态更新成功: {status}")
                return True
            else:
                print(f"[Hermes Sync] 任务 {task_id} 状态更新失败: {response.status_code} - {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[Hermes Sync] 任务 {task_id} 状态更新异常: {str(e)}")
            return False
    
    def _get_current_timestamp(self) -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
    
    def on_agent_complete(self, agent_name: str, result: Optional[Dict] = None, error: Optional[Exception] = None):
        status = 'completed' if result is not None and error is None else 'failed'
        print(f"[Hermes Sync Hook] Agent '{agent_name}' 执行完成，状态: {status}")
        self.update_hermes_task_status(agent_name, status)


def main():
    hook = HermesSyncHook()
    
    import sys
    if len(sys.argv) >= 3:
        agent_name = sys.argv[1]
        status = sys.argv[2]
        hook.update_hermes_task_status(agent_name, status)
    else:
        print("用法: python on_agent_complete.py <agent_name> <status>")


if __name__ == '__main__':
    main()