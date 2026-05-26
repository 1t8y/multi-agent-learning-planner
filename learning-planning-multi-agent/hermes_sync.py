"""
Hermes 同步客户端
负责与 Hermes Kanban 进行状态同步

核心功能：
- 读取配置文件
- 执行 Hermes CLI 命令
- 更新 Kanban 任务状态
- 支持 claim + complete 工作流程
"""

import os
import json
import subprocess
from typing import Dict, Optional, Any


class HermesSyncClient:
    """
    Hermes Kanban 同步客户端
    
    提供与 Hermes Kanban 的状态同步功能，支持：
    - 任务认领 (claim)
    - 任务完成 (complete)
    - 任务重置 (reclaim)
    - 状态查询
    
    Attributes:
        config_path: 配置文件路径
        config: 配置字典
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 Hermes 同步客户端
        
        Args:
            config_path: 配置文件路径，默认为 .trae/config/hermes_sync.json
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                '.trae',
                'config',
                'hermes_sync.json'
            )
        self.config_path = config_path
        self.config = self._load_config()
        
        print(f"[Hermes Sync] 已初始化，配置文件: {self.config_path}")
    
    def _load_config(self) -> Dict:
        """
        加载配置文件
        
        优先从指定路径加载JSON配置，如果不存在则返回默认配置
        
        Returns:
            配置字典
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Hermes Sync] 加载配置文件失败: {e}")
        
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            'api_base_url': 'http://127.0.0.1:8642',
            'api_key': '',
            'auth_type': 'bearer',
            'endpoints': {
                'chat_completions': '/v1/chat/completions',
                'responses': '/v1/responses',
                'runs': '/v1/runs',
                'run_status': '/v1/runs/{run_id}',
                'run_events': '/v1/runs/{run_id}/events',
                'run_stop': '/v1/runs/{run_id}/stop',
                'jobs': '/api/jobs',
                'job': '/api/jobs/{job_id}'
            },
            'status_mapping': {
                'trae_to_hermes': {
                    'running': 'in_progress',
                    'completed': 'completed',
                    'failed': 'failed'
                },
                'hermes_to_trae': {
                    'in_progress': 'running',
                    'completed': 'completed',
                    'failed': 'failed'
                }
            },
            'webhook': {
                'enabled': False,
                'url': '',
                'secret': ''
            },
            'sync_mode': 'trae_to_hermes',
            'cli_path': 'hermes'
        }
    
    def _get_cli_path(self) -> str:
        """
        获取 Hermes CLI 路径
        
        Returns:
            CLI 可执行文件路径
        """
        return self.config.get('cli_path', 'hermes')
    
    def _run_cli_command(self, command: str) -> tuple:
        """
        执行 CLI 命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            (success: bool, stdout: str, stderr: str)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return (result.returncode == 0, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (False, '', '命令超时')
        except Exception as e:
            return (False, '', str(e))
    
    def update_kanban_task(self, task_id: str, action: str) -> bool:
        """
        使用 Hermes CLI 更新 Kanban 任务状态
        
        Args:
            task_id: 任务ID（如 t_d7888e7c）
            action: 操作类型（completed/running/failed）
        
        Returns:
            bool: 是否成功
        """
        cli_path = self._get_cli_path()
        
        if action == 'completed':
            # 先 claim 再 complete（Hermes Kanban 工作流程）
            claim_cmd = f'{cli_path} kanban claim {task_id}'
            claim_success, claim_out, claim_err = self._run_cli_command(claim_cmd)
            
            if claim_success or 'Claimed' in claim_out:
                print(f"[Hermes Sync] 任务 {task_id} 已认领")
            else:
                # 任务可能已经被认领或处于其他状态，继续执行
                print(f"[Hermes Sync] 任务 {task_id} 认领状态: {claim_out or claim_err}")
            
            # 然后完成
            complete_cmd = f'{cli_path} kanban complete {task_id}'
            success, stdout, stderr = self._run_cli_command(complete_cmd)
            
            if success or 'Completed' in stdout:
                print(f"[Hermes Sync] Kanban 任务 {task_id} 已完成: {stdout.strip()}")
                return True
            else:
                print(f"[Hermes Sync] Kanban 任务 {task_id} 完成失败: {stderr.strip() if stderr else stdout}")
                return False
                
        elif action == 'running':
            command = f'{cli_path} kanban claim {task_id}'
            success, stdout, stderr = self._run_cli_command(command)
            
            if success:
                print(f"[Hermes Sync] Kanban 任务 {task_id} 已认领: {stdout.strip()}")
                return True
            else:
                print(f"[Hermes Sync] Kanban 任务 {task_id} 认领失败: {stderr.strip()}")
                return False
                
        elif action == 'failed':
            command = f'{cli_path} kanban reclaim {task_id}'
            success, stdout, stderr = self._run_cli_command(command)
            
            if success:
                print(f"[Hermes Sync] Kanban 任务 {task_id} 已重置: {stdout.strip()}")
                return True
            else:
                print(f"[Hermes Sync] Kanban 任务 {task_id} 重置失败: {stderr.strip()}")
                return False
        else:
            print(f"[Hermes Sync] 不支持的操作: {action}")
            return False
    
    def update_job_status(self, job_id: str, status: str) -> bool:
        """
        更新任务状态（适配 Kanban 任务）
        
        Args:
            job_id: 任务ID
            status: 状态（running/completed/failed）
        
        Returns:
            bool: 是否成功
        """
        return self.update_kanban_task(job_id, status)
    
    def _map_status(self, status: str, direction: str = 'trae_to_hermes') -> Optional[str]:
        """
        映射状态（Trae ↔ Hermes）
        
        Args:
            status: 原始状态
            direction: 映射方向（trae_to_hermes/hermes_to_trae）
        
        Returns:
            映射后的状态
        """
        mapping = self.config.get('status_mapping', {}).get(direction, {})
        return mapping.get(status.lower())
    
    def is_available(self) -> bool:
        """
        检查 Hermes CLI 是否可用
        
        Returns:
            bool: CLI是否可用
        """
        cli_path = self._get_cli_path()
        success, stdout, stderr = self._run_cli_command(f'{cli_path} --version')
        return success
    
    def get_agent_task_id(self, agent_name: str) -> Optional[str]:
        """
        从 Agent 配置文件获取 Hermes 任务 ID
        
        Args:
            agent_name: Agent名称（如 requirement-extractor-agent）
        
        Returns:
            任务ID或None
        """
        agent_md_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '.trae',
            'agents',
            f'{agent_name}.md'
        )
        
        if os.path.exists(agent_md_path):
            with open(agent_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                import re
                match = re.search(r'hermes_task_id:\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        return None
    
    def list_kanban_tasks(self) -> Optional[str]:
        """
        列出 Kanban 任务
        
        Returns:
            任务列表字符串或None
        """
        cli_path = self._get_cli_path()
        command = f'{cli_path} kanban list'
        success, stdout, stderr = self._run_cli_command(command)
        
        if success:
            return stdout
        else:
            print(f"[Hermes Sync] 获取任务列表失败: {stderr}")
            return None
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务状态字符串或None
        """
        cli_path = self._get_cli_path()
        command = f'{cli_path} kanban show {task_id}'
        success, stdout, stderr = self._run_cli_command(command)
        
        if success:
            return stdout
        else:
            print(f"[Hermes Sync] 获取任务 {task_id} 状态失败: {stderr}")
            return None
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("\n" + "="*60)
        print("Hermes Sync 配置摘要")
        print("="*60)
        print(f"API 基础URL: {self.config.get('api_base_url')}")
        print(f"CLI 路径: {self.config.get('cli_path')}")
        print(f"同步模式: {self.config.get('sync_mode')}")
        print(f"Webhook 启用: {self.config.get('webhook', {}).get('enabled', False)}")
        print("状态映射:")
        for direction, mapping in self.config.get('status_mapping', {}).items():
            print(f"  {direction}: {mapping}")
        print("="*60 + "\n")


if __name__ == "__main__":
    # 简单测试
    client = HermesSyncClient()
    client.print_config_summary()
    
    print(f"Hermes CLI 可用: {client.is_available()}")
    
    # 测试任务状态获取
    test_task_id = "t_d7888e7c"
    status = client.get_task_status(test_task_id)
    if status:
        print(f"\n任务 {test_task_id} 状态:")
        print(status)