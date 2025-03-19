import requests 
import json 
from datetime import datetime 

def ai_api(content, conversation_history=None):
    additional_info = input("请输入要求：")
    """智能对话处理引擎（2025年3月15日版）"""
    # 初始化对话历史 
    conversation_history = conversation_history or [
        {
            "role": "system",
            "content": '''你是一个全能助手，严格按照指示办事，不说废话 '''

        }
    ]
 
    # 构建对话记录 
    conversation_history.append({"role":  "user", "content": additional_info+":"+content})
    
    # API调用参数 
    url = "https://api.siliconflow.cn/v1/chat/completions" 
    headers = {
        "Authorization": "Bearer sk-yskiidfcfdruqfqlpaqenznjmzufllminwwkatftofmogmvs",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "THUDM/glm-4-9b-chat",
        "messages": conversation_history,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 2048,
        "response_format": {"type": "text"}  # 确保结构化输出 
    }
 
    # 处理流式响应 
    full_response = ""
    with requests.post(url,  json=payload, headers=headers, stream=True) as response:
        for line in response.iter_lines(): 
            if line:
                decoded_line = line.decode('utf-8').lstrip('data:  ')
                try:
                    chunk = json.loads(decoded_line)
                    if "content" in chunk["choices"][0]["delta"]:
                        content_part = chunk["choices"][0]["delta"]["content"]
                        print(content_part, end="", flush=True)
                        full_response += content_part 
                except:
                    continue 
 
    # 更新对话历史 
    conversation_history.append({ 
        "role": "assistant",
        "content": full_response 
    })
    
    return full_response,conversation_history
# while True:
#     content = input("\n请输入问题：")
#     history = ai_api(content)