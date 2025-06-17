from langchain_community.chat_models.tongyi import ChatTongyi
import os
from dotenv import load_dotenv

load_dotenv()
client = ChatTongyi(api_key=os.getenv('DASHSCOPE_API_KEY'), model = 'qwen-plus')
response = client.invoke([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁？"},
    ]
)
print(response)