"""Utility & helper functions."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional

class RequestModel(BaseModel):
    content: str
    threadid: str
    role: str
    tool_call_id: Optional[str] = None
    status: Optional[str] = 'success'
    tool_name: Optional[str] = None

class ResponseModel(BaseModel):
    content: str
    role: str = "assistant"
    tool_calls: List[Dict] = Field(default_factory=list)
    id: str
    type: Literal["ai", "function", "stop"]

    def __init__(self, **data):
        if len(data["tool_calls"]) > 0:
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
        super().__init__(**data)

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "role": self.role,
            "tool_calls": self.tool_calls,
            "id": self.id,
            "type": self.type
        }
    
class ToolResponse(BaseModel):
    run_notebook: str="我将为您运行notebook"
    gen_notebook: str="我将为您生成notebook"

    def __init__(self, notebook_name: str):
        super().__init__()
        self.run_notebook = f"我将为您运行notebook {notebook_name}"
        self.gen_notebook = f"我将为您生成notebook {notebook_name}"

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
    return init_chat_model(model, model_provider=provider)
