import requests
from dotenv import load_dotenv
import os

load_dotenv()
def chat_with_model(message:str):
    url = 'https://llm-ai.talentnet.vn/api/chat/completions'
    headers = {
        'Authorization': f'Bearer {os.getenv("OPENWEB_UI_API")}',
        'Content-Type': 'application/json'
    }
    data = {
      "model": "gpt-oss:120b",
      "messages": [
        {
          "role": "user",
          "content": message
        }
      ],
      "reasoning": { "effort": "low" },

      "temperature": 0.1,
      "top_p": 0.1,
      "stream": False,
      
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()['choices'][0]['message']['content']
