from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated, Literal
import uuid
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from contextlib import asynccontextmanager
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, MessagesState, END
from langgraph.checkpoint.memory import InMemorySaver
from .config import get_config, validate_environment, setup_output_directory
import json

# 全局变量存储系统实例和会话
# programming_system = None
active_sessions: Dict[str, Dict[str, Any]] = {}

notebook_structure = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {
                "cell_id": str(uuid.uuid4())  # 自动分配UUID
            },
            "source":["## 欢迎进入 ModelWhale Notebook  \n\n这里你可以编写代码，文档  \n\n### 关于文件目录  \n\n\n**project**：project 目录是本项目的工作空间，可以把将项目运行有关的所有文件放在这里，目录中文件的增、删、改操作都会被保留  \n\n\n**input**：input 目录是数据集的挂载位置，所有挂载进项目的数据集都在这里，未挂载数据集时 input 目录被隐藏  \n\n\n**temp**：temp 目录是临时磁盘空间，训练或分析过程中产生的不必要文件可以存放在这里，目录中的文件不会保存"]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.8.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

# 定义标准的LangChain工具函数
@tool
def gen_notebook(
    notebook_name: Annotated[str, Field(description="Notebook文件名（包含.ipynb后缀）")],
    notebook: Annotated[Optional[str], Field(description="完整的notebook结构，必须是有效的JSON字符串格式", default=None)]
) -> str:
    """生成一个新的Jupyter Notebook文件"""
    return f"生成notebook: {notebook_name}"

@tool  
def add_cell(
    filename: Annotated[str, Field(description="Notebook文件名")],
    content: Annotated[str, Field(description="单元格内容")],
    cell_type: Annotated[str, Field(description="单元格类型", default="code")] = "code",
    cell_index: Annotated[int, Field(description="插入位置（-1表示添加到末尾）", default=-1)] = -1
) -> str:
    """向Notebook添加单元格（代码或Markdown）"""
    return f"添加cell到 {filename}: {cell_type} cell with content: {content[:50]}..."



@tool
def update_cell_by_id(
    filename: Annotated[str, Field(description="Notebook文件名")],
    cell_id: Annotated[str, Field(description="单元格UUID")],
    new_content: Annotated[str, Field(description="新的单元格内容")]
) -> str:
    """通过UUID更新Notebook中的单元格内容"""
    return f"更新cell {cell_id} in {filename}: {new_content[:50]}..."

@tool
def delete_cell_by_id(
    filename: Annotated[str, Field(description="Notebook文件名")],
    cell_id: Annotated[str, Field(description="要删除的单元格UUID")]
) -> str:
    """通过UUID删除Notebook中的单元格"""
    return f"删除cell {cell_id} from {filename}"

@tool
def run_notebook(
    filename: Annotated[str, Field(description="要运行的Notebook文件名")],
    cells: Annotated[List[str], Field(description="需要运行的代码cell ID列表，若为空则运行全部代码单元格", default_factory=list)] = None
) -> str:
    """运行notebook中的代码单元格，返回运行后的notebook内容"""
    return f"运行notebook {filename}, cells: {cells or 'all'} - 执行完成，返回notebook内容以供检查运行结果和错误"

def create_mock_programming_assistant():
    """创建模拟执行的NotebookAgent系统"""
    config = get_config("notebook_agent")  # 使用NotebookAgent配置
    openai_config = get_config("openai")
    
    llm = ChatOpenAI(
        model=openai_config["model"],
        api_key=openai_config["api_key"],
        base_url=openai_config["base_url"],
        temperature=openai_config["temperature"]
    )
    
    # 绑定NotebookAgent的工具schema
    llm_with_tools = llm.bind_tools([
        gen_notebook,
        add_cell,
        update_cell_by_id,
        delete_cell_by_id,
        run_notebook
    ])
    
    # 创建checkpointer
    checkpointer = InMemorySaver()
    
    # 创建带系统消息的LLM
    system_message = SystemMessage(content="""你是Jupyter Notebook专家，管理有状态的Notebook环境。

重要：
- 你必须既提供清晰的文字回复，又调用适当的工具。永远不要只调用工具而不说话。
- 不要编造数据，不要编造结果，一切分析和总结要基于实际结果。

对话原则：
1. 首先理解用户需求并确认
2. 解释你的计划和步骤
3. 调用工具完成任务
4. 总结完成的工作

工具：
- gen_notebook：生成完整的notebook文件
- add_cell：添加cell到指定位置
- update_cell_by_id：通过ID更新修改cell内容
- delete_cell_by_id：通过ID删除cell
- run_notebook：运行notebook中的代码单元格，返回运行后的notebook内容以供检查运行结果和错误

代码生成原则：
- 请记住Notbeook是有状态的，需要考虑cell的顺序和依赖关系。
- 不要重复定义之前cell中的变量、函数、类等，不要重复导入包。
- 你无法直接"看到"图片，所以画图同时尽量打印数据或相关信息。

记住：始终先解释，再行动，最后总结。""")
    
    def agent_node(state: MessagesState):
        """Notebook代理节点 - 自动处理系统消息"""
        messages = state["messages"]
        if not messages or not (hasattr(messages[0], 'type') and messages[0].type == 'system'):
            messages = [system_message] + messages
        
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    
    # 创建状态图 - 最简洁的写法
    graph = (
        StateGraph(MessagesState)
        .add_node("agent", agent_node)
        .add_edge(START, "agent") 
        .add_edge("agent", END)
        .compile(checkpointer=checkpointer)
    )
    
    return graph

# @asynccontextmanager
# async def lifespan(app: FastAPI):
"""系统生命周期事件处理器"""
global programming_system

print("🤖 模拟编程助手API启动中...")

# 验证环境配置
if not validate_environment():
    raise RuntimeError("环境配置验证失败")

# 设置输出目录
setup_output_directory()

# 创建模拟系统
programming_system = create_mock_programming_assistant()


print("✅ 模拟编程助手API启动完成！")

# yield

# 清理资源
# print("👋 模拟编程助手API关闭中...")

# 初始化FastAPI应用
# app = FastAPI(
#     title="模拟编程助手API",
#     description="基于LLM的编程助手服务（不实际执行工具调用）",
#     version="1.0.0",
#     lifespan=lifespan
# )

# 请求和响应模型
class UserRequest(BaseModel):
    threadid: str
    role: Literal["user"] = "user"
    content: str

class ToolRequest(BaseModel):
    threadid: str
    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str
    status: Literal["success", "error"] = "success"

class ChatRequest(BaseModel):
    """统一的聊天请求，支持用户消息和工具结果"""
    threadid: str
    role: Literal["user", "tool"]
    content: str
    tool_call_id: Optional[str] = None
    status: Optional[Literal["success", "error"]] = None

class ToolCall(BaseModel):
    function: Dict[str, Any]
    id: str
    type: str

class ChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    id: str
    type: str = ""  # 默认值，会在模型验证时被正确设置
    tool_calls: List[ToolCall] = []
    
    @classmethod
    def create(cls, content: str, id: str, tool_calls: List[ToolCall] = None):
        """创建ChatResponse实例，自动设置type字段"""
        if tool_calls is None:
            tool_calls = []
        
        response_type = "tool" if tool_calls else "ai"
        
        return cls(
            content=content,
            id=id,
            type=response_type,
            tool_calls=tool_calls
        )

def extract_ai_message_from_updates(updates: List[Any]) -> Dict[str, Any]:
    """从更新中提取最后一个AI消息的完整信息"""
    last_ai_message = None
    
    for update in updates:
        if isinstance(update, tuple):
            # 处理子图更新
            _, update_content = update
        else:
            update_content = update
            
        for node_name, node_update in update_content.items():
            if isinstance(node_update, dict) and "messages" in node_update:
                messages = node_update["messages"]
                if messages:
                    last_message = messages[-1]
                    # 只处理AI消息
                    if hasattr(last_message, 'type') and last_message.type == 'ai':
                        last_ai_message = last_message
                    elif hasattr(last_message, '__class__') and 'AIMessage' in last_message.__class__.__name__:
                        last_ai_message = last_message
    
    if not last_ai_message:
        return {
            "content": "处理完成",
            "id": str(uuid.uuid4()),
            "tool_calls": [],
            "type": "ai"
        }
    
    # 调试：打印AI消息的详细信息
    print(f"AI Message type: {type(last_ai_message)}")
    print(f"AI Message content repr: {repr(getattr(last_ai_message, 'content', 'No content'))}")
    print(f"AI Message content type: {type(getattr(last_ai_message, 'content', None))}")
    print(f"AI Message full dict: {last_ai_message.__dict__ if hasattr(last_ai_message, '__dict__') else 'No dict'}")
    if hasattr(last_ai_message, 'tool_calls'):
        print(f"Tool calls count: {len(last_ai_message.tool_calls) if last_ai_message.tool_calls else 0}")
        if last_ai_message.tool_calls:
            for i, tc in enumerate(last_ai_message.tool_calls):
                print(f"Tool call {i}: type={type(tc)}, content={tc}")
    else:
        print("No tool_calls attribute")
    
    # 提取消息信息
    result = {
        "content": getattr(last_ai_message, 'content', ''),
        "id": getattr(last_ai_message, 'id', str(uuid.uuid4())),
        "tool_calls": [],
        "type": "ai"
    }
    
    # 提取工具调用信息
    if hasattr(last_ai_message, 'tool_calls') and last_ai_message.tool_calls:
        for tool_call in last_ai_message.tool_calls:
            # 处理不同的tool_call结构
            if hasattr(tool_call, '__dict__'):
                # 如果是对象，尝试获取属性
                tool_name = getattr(tool_call, 'name', '') or getattr(tool_call, 'function', {}).get('name', '')
                tool_args = getattr(tool_call, 'args', {}) or getattr(tool_call, 'function', {}).get('arguments', {})
                tool_id = getattr(tool_call, 'id', str(uuid.uuid4()))
                tool_type = getattr(tool_call, 'type', 'function')
            elif isinstance(tool_call, dict):
                # 如果是字典，直接访问
                tool_name = tool_call.get('name', '') or tool_call.get('function', {}).get('name', '')
                tool_args = tool_call.get('args', {}) or tool_call.get('function', {}).get('arguments', {})
                tool_id = tool_call.get('id', str(uuid.uuid4()))
                tool_type = tool_call.get('type', 'function')
            else:
                # 其他情况，尝试转换为字符串查看
                print(f"Unexpected tool_call type: {type(tool_call)}, content: {tool_call}")
                continue
            
            # 特殊处理：如果是gen_notebook且没有notebook参数，添加默认值
            if tool_name == 'gen_notebook':
                tool_args['notebook_name'] = tool_args['notebook_name'].split('.')[0] + '_' + str(uuid.uuid4()).split('-')[1] + '.ipynb'
                if 'notebook' not in tool_args or not tool_args['notebook']:
                    tool_args['notebook'] = json.dumps(notebook_structure)  # 确保是JSON格式
                    print(f"Added default notebook_structure to gen_notebook call")
            
            tool_call_dict = {
                "function": {
                    "arguments": tool_args,
                    "name": tool_name
                },
                "id": tool_id,
                "type": 'function'
            }
            result["tool_calls"].append(tool_call_dict)
    
    return result

# @app.post("/", response_model=ChatResponse)
# async def chat(request: ChatRequest):
def invoke(request):
    """统一的对话接口，支持用户消息和工具结果"""
    global programming_system, active_sessions
    
    if not programming_system:
        raise HTTPException(status_code=500, detail="系统未初始化")
    
    # 使用threadid作为会话标识
    config = {"configurable": {"thread_id": request["threadid"]}}
    
    try:
        print(f"🔍 处理消息: {request['content']}")
        print(f"🔍 消息角色: {request['role']}")
        
        # 构建消息列表
        messages = []
        
        if request["role"] == "tool":
            # 如果是工具结果，构建ToolMessage
            if not request["tool_call_id"]:
                raise HTTPException(status_code=400, detail="工具消息缺少tool_call_id")
            
            from langchain_core.messages import ToolMessage
            tool_message = ToolMessage(
                content=request["content"],
                tool_call_id=request["tool_call_id"]
            )
            messages.append(tool_message)
            print(f"🔍 构建了工具消息，tool_call_id: {request['tool_call_id']}")
        else:
            # 如果是用户消息，构建HumanMessage
            messages.append(HumanMessage(content=request["content"]))
            print(f"🔍 构建了用户消息")
        
        # 收集所有更新
        updates = []
        
        for chunk in programming_system.stream(
            {"messages": messages},
            config=config
        ):
            updates.append(chunk)
        
        print(f"🔍 收集到 {len(updates)} 个更新")
        
        # 提取AI消息
        ai_message = extract_ai_message_from_updates(updates)
        print(f"🔍 提取AI消息完成，content长度: {len(ai_message.get('content', ''))}")
        
        # 检查是否有工具调用
        has_tool_calls = len(ai_message["tool_calls"]) > 0
        print(f"🔍 工具调用数量: {len(ai_message['tool_calls'])}")
        
        print(f"🔍 准备构建响应")
        
        # 安全地构建ToolCall对象
        tool_call_objects = []
        for tc in ai_message["tool_calls"]:
            try:
                tool_call_objects.append(ToolCall(**tc))
            except Exception as tc_error:
                print(f"❌ 构建ToolCall对象失败: {tc_error}, 原始数据: {tc}")
                # 使用更安全的方式构建
                tool_call_objects.append(ToolCall(
                    function=tc.get("function", {}),
                    id=tc.get("id", str(uuid.uuid4())),
                    type=tc.get("type", "function")
                ))
        
        response = ChatResponse.create(
            content=ai_message["content"],
            id=ai_message["id"],
            tool_calls=tool_call_objects
        )
        
        print(f"✅ 响应构建完成")
        return response.model_dump()
            
    except Exception as e:
        print(f"❌ 处理请求出错: {str(e)}")
        print(f"❌ 错误类型: {type(e)}")
        import traceback
        print(f"❌ 错误堆栈: {traceback.format_exc()}")
        
        # 清理会话
        if request["threadid"] in active_sessions:
            del active_sessions[request["threadid"]]
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

# @app.get("/threads")
# async def get_active_threads():
#     """获取活跃线程列表"""
#     return {
#         "active_threads": list(active_sessions.keys()),
#         "count": len(active_sessions)
#     }

# @app.delete("/threads/{threadid}")
# async def clear_thread(threadid: str):
#     """清理指定线程"""
#     if threadid in active_sessions:
#         del active_sessions[threadid]
#         return {"message": f"线程 {threadid} 已清理"}
#     else:
#         raise HTTPException(status_code=404, detail="线程不存在")

# @app.get("/info")
# async def root():
#     """返回API信息"""
#     return {
#         "message": "模拟NotebookAgent API",
#         "version": "1.0.0",
#         "description": "基于NotebookAgent的编程助手服务，LLM生成工具调用但不实际执行",
#         "agent_info": {
#             "type": "notebook_agent",
#             "prompt": "使用原始NotebookAgent的prompt和工具",
#             "capabilities": [
#                 "Notebook管理（创建、读取、修改）",
#                 "代码单元格运行",
#                 "代码生成和分析",
#                 "用户交互管理"
#             ]
#         },
#         "endpoints": {
#             "chat": "POST /chat - 发送消息，获取包含tool_calls的响应",
#             "sessions": "GET /sessions - 查看活跃会话",
#             "clear_session": "DELETE /sessions/{session_id} - 清理会话"
#         },
#         "usage": {
#             "chat": "发送 {'message': '你的消息', 'session_id': '可选的会话ID'} 到 /chat",
#             "note": "系统使用NotebookAgent的完整prompt和工具，但不实际执行工具调用，所有工具调用信息返回在tool_calls字段中"
#         }
#     }

# 运行服务的主函数
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)