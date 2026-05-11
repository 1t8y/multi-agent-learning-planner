import os
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
print(f"API Key 存在: {api_key is not None}")

if api_key:
    print("正在测试 DeepSeek API...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "deepseek-chat",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "你好"}]
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        result = response.json()
        print(f"API 响应: {result['choices'][0]['message']['content']}")
    except Exception as e:
        print(f"API 测试失败: {e}")