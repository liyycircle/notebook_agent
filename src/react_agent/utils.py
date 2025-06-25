"""Utility & helper functions."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional, TypedDict
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import ToolMessage
import os, uuid
import json


class ConfigSchema(TypedDict):
    kernel_language: str = "python3"


class ToolMessage(ToolMessage):
    code: Literal[200, 400]=200

class RequestModel(BaseModel):
    content: str
    threadid: str
    role: str
    kernel_language: str
    tool_call_id: Optional[str] = None
    references: Optional[List[str]] = None
    status: Optional[str] = 'success'
    tool_name: Optional[str] = None

    def get_valid_nbinfo(self):
        for ref in self.references:
            if ref['type']=='notebook':
                ref_data = ref['data']
                valid_dict = json.loads(ref_data['content'])
                nb_content = valid_dict['Content']['cells']
                ref_data['content'] = [NBCell(cell).agentCell for cell in nb_content]


class NBCell():
    # TODO: 处理img base64
    def __init__(self, nbCell):
      self.agentCell = {
            "cell_id": nbCell['metadata']['id'],
            "cell_type": nbCell['cell_type'],
            "source": nbCell['source'],
            "outputs": nbCell['outputs'] if nbCell['cell_type']=='code' else []
            }
      
      if self.agentCell['cell_type']=='code':
          for output in self.agentCell['outputs']:
              if 'text/html' in output.get('data', {}).keys():
                  del output['data']['text/html']

class ResponseModel(BaseModel):
    content: str
    role: str = "assistant"
    tool_calls: List[Dict] = []
    id: str
    threadid: str
    type: Literal["ai", "function", "stop"]

    def __init__(self, **data):
        if 'tool_calls' in data.keys():
            # 转换 tool_calls 格式
            tool_calls = data["tool_calls"]
            converted_tool_calls = []
            for tc in tool_calls:
                converted_tool_calls.append({
                    "id": tc["id"],
                    "function":{
                        "name": tc["name"],
                        "arguments": tc["args"]
                    },
                    "type": "function"
                })
            data["tool_calls"] = converted_tool_calls

        if data.get('stop', False):
            data = {
                "content": "",
                "role": "assistant",
                "tool_calls": [],
                "id": str(uuid.uuid4()),
                "threadid": data['threadid'],
                "type": "stop"
            }

        super().__init__(**data)

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "role": self.role,
            "tool_calls": self.tool_calls,
            "id": self.id,
            "threadid": self.threadid,
            "type": self.type
        }
    
class ToolResponse(BaseModel):
    run_notebook: str="我将为您运行 notebook。"
    gen_notebook: str="我将为您生成 notebook。"
    add_cell: str="我将为您添加 notebook cell。"
    update_cell_by_id: str="我将为您修改 notebook cell。"

    def __init__(self, summary: str=""):
        super().__init__()
        self.gen_notebook += summary
        self.update_cell_by_id += summary


def get_message_text(msg: BaseMessage) -> str:
    """Get the text content of a message."""
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    provider, model = fully_specified_name.split("/", maxsplit=1)
    if provider == 'tongyi':
        return ChatTongyi(model=model, api_key='sk-66a6fcac623a475d99b9fa23b85d07c0')
    return init_chat_model(model, model_provider=provider)

