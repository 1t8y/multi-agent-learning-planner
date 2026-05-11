import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
import requests

load_dotenv()

class DeepSeekAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        self.max_tokens = 4096
        self.temperature = 0.7
        self.context: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        if role not in ["user", "assistant", "system"]:
            raise ValueError("Role must be 'user', 'assistant', or 'system'")
        self.context.append({"role": role, "content": content})

    def set_system_prompt(self, prompt: str) -> None:
        system_msg = next((m for m in self.context if m["role"] == "system"), None)
        if system_msg:
            system_msg["content"] = prompt
        else:
            self.context.insert(0, {"role": "system", "content": prompt})

    def clear_context(self) -> None:
        self.context = []

    def get_context_size(self) -> int:
        return len(self.context)

    def build_prompt(self, user_message: str) -> Dict:
        messages = []
        for msg in self.context:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages
        }

    def call_api(self, user_message: str) -> str:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = self.build_prompt(user_message)
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            assistant_response = result["choices"][0]["message"]["content"]
            
            self.add_message("user", user_message)
            self.add_message("assistant", assistant_response)
            
            return assistant_response
        
        except requests.exceptions.RequestException as e:
            return f"API调用失败: {str(e)}"

    def chat(self, user_message: str) -> str:
        return self.call_api(user_message)

def main():
    agent = DeepSeekAgent()
    
    agent.set_system_prompt("你是一个乐于助人的AI助手，回答要简洁明了。")
    
    print("DeepSeek Agent 已启动！输入 'exit' 或 'quit' 退出对话。")
    print("输入 'clear' 清除对话历史。")
    print("=" * 50)
    
    while True:
        user_input = input("您: ")
        
        if user_input.lower() in ["exit", "quit"]:
            print("再见！")
            break
        
        if user_input.lower() == "clear":
            agent.clear_context()
            agent.set_system_prompt("你是一个乐于助人的AI助手，回答要简洁明了。")
            print("对话历史已清除")
            continue
        
        response = agent.chat(user_input)
        print(f"DeepSeek: {response}")
        print("-" * 50)

if __name__ == "__main__":
    main()