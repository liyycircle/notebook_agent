import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated, Literal
# from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from contextlib import asynccontextmanager
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from .config import get_config, validate_environment, setup_output_directory
import json, uuid

# 全局变量存储系统实例和会话
# programming_system = None
active_sessions: Dict[str, Dict[str, Any]] = {}

notebook_structure = {
    "cells": [
        # {
        #     "cell_type": "markdown",
        #     "metadata": {
        #         "cell_id": str(uuid.uuid4())  # 自动分配UUID
        #     },
        #     "source":["## 欢迎进入 ModelWhale Notebook  \n\n这里你可以编写代码，文档  \n\n### 关于文件目录  \n\n\n**project**：project 目录是本项目的工作空间，可以把将项目运行有关的所有文件放在这里，目录中文件的增、删、改操作都会被保留  \n\n\n**input**：input 目录是数据集的挂载位置，所有挂载进项目的数据集都在这里，未挂载数据集时 input 目录被隐藏  \n\n\n**temp**：temp 目录是临时磁盘空间，训练或分析过程中产生的不必要文件可以存放在这里，目录中的文件不会保存"]
        # }
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

# 创建虚拟工具类，只提供schema不执行
class MockToolException(Exception):
    """自定义异常，用于标识工具调用需要客户端执行"""
    def __init__(self, tool_name: str, args: Dict[str, Any]):
        self.tool_name = tool_name
        self.args = args
        super().__init__(f"Mock tool call: {tool_name}")

# 定义标准的LangChain工具函数
@tool
def gen_notebook(
    notebook_name: Annotated[str, Field(description="Notebook文件名（不含.ipynb后缀）")],
    notebook: Annotated[Optional[str], Field(description="完整且有效的notebook结构", default=None)]
) -> str:
    """生成一个新的Jupyter Notebook文件"""
    return f"生成notebook: {notebook_name}"

@tool  
def add_cell(
    content: Annotated[str, Field(description="单元格内容")],
    cell_type: Annotated[str, Field(description="单元格类型（code/markdown）")],
    cell_index: Annotated[int, Field(description="插入位置（默认-1，表示添加到末尾）")] 
) -> str:
    """向Notebook添加单元格（代码或Markdown）"""
    raise MockToolException("add_cell", {
        # "filename": filename,
        "content": content,
        "cell_type": cell_type,
        "cell_index": cell_index
    })

@tool
def update_cell_by_id(
    # filename: Annotated[str, Field(description="Notebook文件名")],
    cell_id: Annotated[str, Field(description="单元格UUID")],
    new_content: Annotated[str, Field(description="新的单元格内容")]
) -> str:
    """通过UUID更新Notebook中的单元格内容"""
    raise MockToolException("update_cell_by_id", {
        # "filename": filename,
        "cell_id": cell_id,
        "new_content": new_content
    })

# @tool
# def delete_cell_by_id(
#     filename: Annotated[str, Field(description="Notebook文件名")],
#     cell_id: Annotated[str, Field(description="要删除的单元格UUID")]
# ) -> str:
#     """通过UUID删除Notebook中的单元格"""
#     return f"删除cell {cell_id} from {filename}"

@tool
def run_notebook(
    # cells: Annotated[List[str], Field(description="需要运行的代码cell ID列表，若为空则运行全部代码单元格", default_factory=list)] = None
) -> str:
    """运行notebook中的代码单元格，返回运行后的notebook内容"""
    raise MockToolException("run_notebook", {
        # "cells": cells or []
    })

def cleanup_notebook_results_when_needed(threadid: str, programming_system):
    """
    检查是否需要清理run_notebook结果，将历史的notebook内容设置为空
    保持工具调用的完整性，避免LLM提供商报错，同时彻底节省上下文空间
    """
    config = {"configurable": {"thread_id": threadid}}
    
    try:
        # 获取当前状态
        current_state = programming_system.get_state(config)
        messages = current_state.values.get("messages", [])
        
        if not messages:
            return
        # 获取最后一条消息
        last_message = messages[-1]
        # 检查是否是AI消息且包含run_notebook工具调用
        has_run_notebook_call = False
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                if tool_name == 'run_notebook':
                    has_run_notebook_call = True
                    break
        
        # 如果没有run_notebook调用，直接返回
        if not has_run_notebook_call:
            return
        
        # 首先收集所有run_notebook的tool_call_id（排除最新的）
        run_notebook_tool_call_ids = set()
        for i, msg in enumerate(messages[:-1]):               
            if (hasattr(msg, 'type') and msg.type == 'ai' and 
                hasattr(msg, 'tool_calls') and msg.tool_calls):
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get('name', '') if isinstance(tool_call, dict) else getattr(tool_call, 'name', '')
                    if tool_name == 'run_notebook':
                        tool_call_id = tool_call.get('id', '') if isinstance(tool_call, dict) else getattr(tool_call, 'id', '')
                        if tool_call_id:
                            run_notebook_tool_call_ids.add(tool_call_id)

        # 找到所有需要清理的run_notebook结果消息
        messages_to_update = []
        # 遍历消息，找到所有对应历史run_notebook的ToolMessage结果
        for i, msg in enumerate(messages):  
            if (hasattr(msg, 'type') and msg.type == 'tool' and 
                hasattr(msg, 'tool_call_id') and msg.tool_call_id in run_notebook_tool_call_ids):                
                updated_message = ToolMessage(
                    content=msg.status,
                    tool_call_id=msg.tool_call_id,
                    id=msg.id,
                    status=msg.status,
                    threadid=msg.threadid,
                )
                messages_to_update.append(updated_message)
        # 如果有消息需要更新，使用update_state更新
        if messages_to_update:
            programming_system.update_state(config, {"messages": messages_to_update})
    except Exception as e:
        print(f"❌ 清理run_notebook结果时出错: {e}")

def create_mock_programming_assistant():
    """创建使用create_react_agent但不实际执行工具的系统"""
    openai_config = get_config("openai")
    
    llm = ChatOpenAI(
        model=openai_config["model"],
        api_key=openai_config["api_key"],
        base_url=openai_config["base_url"],
        temperature=openai_config["temperature"],
        streaming=False
    )
    
    # 创建checkpointer
    checkpointer = InMemorySaver()

    # summarization_node = SummarizationNode( 
    #     token_counter=count_tokens_approximately,
    #     model=llm,
    #     max_tokens=60000,
    #     max_tokens_before_summary=50000,
    # )
    
    # 使用create_react_agent创建agent，但在工具节点前中断
    graph = create_react_agent(
        model=llm,
        tools=[
            gen_notebook,
            add_cell,
            update_cell_by_id,
            run_notebook
        ],
        # pre_model_hook=summarization_node,
        prompt="""你是Jupyter Notebook专家，管理有状态的Notebook环境。

重要：
- 你必须既提供清晰的文字回复，又调用适当的工具。永远不要只调用工具而不说话。
- 不要编造数据，不要编造结果，一切分析和总结要基于实际结果。
- 你可以通过运行代码查看结果，为后续代码生成提供参考。

对话原则：
1. 首先理解用户需求并确认
2. 解释你的计划和步骤
3. 调用工具完成任务
4. 总结完成的工作

工具：
- gen_notebook：生成notebook文件
- add_cell：添加cell到指定位置
- update_cell_by_id：通过ID更新修改cell内容
- delete_cell_by_id：通过ID删除cell
- run_notebook：运行notebook中的代码单元格，返回运行后的notebook内容，以供检查错误、总结结果和为后续cell提供参考

工作原则：
- 创建Noteook文件再添加代码
- 运行代码可查看结果，为后续代码生成提供参考。
- 当生成可视化图表时使用英文，必须同步以结构化方式输出可视化图表的汇总统计数据或原始数据。
- 调试修改代码时，直接更新cell内容，不要新增cell代码块。
- 每次只生成一个工具调用，不要生成多个工具调用。

记住：始终先解释，再行动，最后总结。""",
        checkpointer=checkpointer,
        interrupt_before=["tools"]
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
# class UserRequest(BaseModel):
#     threadid: str
#     role: Literal["user"] = "user"
#     content: str

# class ToolRequest(BaseModel):
#     threadid: str
#     role: Literal["tool"] = "tool"
#     content: str
#     tool_call_id: str
#     status: Literal["success", "error"] = "success"

# class ChatRequest(BaseModel):
#     """统一的聊天请求，支持用户消息和工具结果"""
#     threadid: str
#     role: Literal["user", "tool"]
#     content: str
#     tool_call_id: Optional[str] = None
#     status: Optional[Literal["success", "error"]] = None

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
    threadid: str 
    
    @classmethod
    def create(cls, content: str, id: str, tool_calls: List[ToolCall] = None, threadid: str = None):
        """创建ChatResponse实例，自动设置type字段"""
        if tool_calls is None:
            tool_calls = []
        
        response_type = "tool" if tool_calls else "ai"
        
        return cls(
            content=content,
            id=id,
            type=response_type,
            tool_calls=tool_calls,
            threadid=threadid
        )

def clean_ansi(text):
    if not isinstance(text, str):
        return text
    # 将unicode转义序列转换为字符串
    text = text.encode().decode('unicode_escape')
    # 移除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

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
                # 确保文件名唯一性

                base_name = tool_args.get('notebook_name', 'notebook').replace('.ipynb', '')
                tool_args['notebook_name'] = f"{base_name}_{str(uuid.uuid4()).split('-')[1]}.ipynb"
                
                # 如果没有提供notebook结构，使用默认结构（作为JSON字符串）
                if 'notebook' not in tool_args or tool_args['notebook'] is None:
                    tool_args['notebook'] = json.dumps(notebook_structure, ensure_ascii=False, indent=2)
                    print(f"Added default notebook_structure as JSON string to gen_notebook call")
            
            tool_call_dict = {
                "function": {
                    "arguments": tool_args,
                    "name": tool_name
                },
                "id": tool_id,
                "type": tool_type
            }
            result["tool_calls"].append(tool_call_dict)
    
    return result

# @app.post("/", response_model=ChatResponse)
# async def chat(request: ChatRequest):
def invoke(request):
    print(f"🔍 ID: {request['threadid']}")
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
            if request["tool_name"] == "run_notebook":
                if request["status"] == "success":
                    content_dict = json.loads(request["content"])
                    cells = content_dict["Content"]['cells']
                    for cell in cells:
                        if cell['cell_type'] == 'code':
                            for output in cell['outputs']:
                                if 'text' in output:
                                    text = ''.join(output['text']) if isinstance(output['text'], list) else output['text']
                                    text = clean_ansi(text)
                                    output['text'] = text
                                if 'data' in output:
                                    filtered_data = {}
                                    for key, value in output['data'].items():
                                        if key in ['text/plain', 'text/markdown', 'text/latex', 'application/json']:
                                            if isinstance(value, list):
                                                filtered_data[key] = [clean_ansi(v) for v in value]
                                            else:
                                                filtered_data[key] = clean_ansi(value)
                                    output['data'] = filtered_data
                    # 将处理后的结果重新序列化回request["content"]
                    request["content"] = json.dumps(content_dict, ensure_ascii=False)
                else:
                    request["content"] = json.loads(clean_ansi(request["content"]))
                                    
            # 如果是工具结果，构建ToolMessage
            if not request["tool_call_id"]:
                raise HTTPException(status_code=400, detail="工具消息缺少tool_call_id")
            
            tool_message = ToolMessage(
                content=request["content"],
                tool_call_id=request["tool_call_id"],
                status = request["status"],
                threadid=request["threadid"]
            )
            print(f"🔍 构建了工具消息，tool_call_id: {request['tool_call_id']}")

            # 工具结果返回后，需要继续执行agent
            # 添加工具消息到当前状态并继续执行
            updates = []
            for chunk in programming_system.stream(
                {"messages": [tool_message]},  # 发送工具消息
                config=config
            ):
                updates.append(chunk)
        else:
            # 如果是用户消息，构建HumanMessage
            messages.append(HumanMessage(content=request["content"], threadid=request["threadid"]))
            print(f"🔍 构建了用户消息")

            # 收集所有更新
            updates = []
            for chunk in programming_system.stream(
                {"messages": messages},
                config=config
            ):
                updates.append(chunk)
        
        print(f"🔍 收集到 {len(updates)} 个更新")

        # 🔑 检查并清理run_notebook结果（在中断检查之前）
        cleanup_notebook_results_when_needed(request["threadid"], programming_system)

        # 检查是否因工具调用而中断
        # 当使用interrupt_before=["tools"]时，如果有工具调用，会在工具节点前中断
        current_state = programming_system.get_state(config)
        print(f"🔍 当前状态: next={current_state.next}, is_interrupted={len(current_state.next) > 0}")

        if current_state.next and "tools" in current_state.next:
            # 如果下一步是工具节点，说明被中断了，需要提取工具调用
            print("🔍 检测到工具调用中断，提取工具调用信息")
            
            # 从当前状态中获取最后的AI消息（包含工具调用）
            if current_state.values.get("messages"):
                last_message = current_state.values["messages"][-1]
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    ai_message = {
                        "content": getattr(last_message, 'content', ''),
                        "id": getattr(last_message, 'id', str(uuid.uuid4())),
                        "tool_calls": [],
                        "type": "ai"
                    }
                    
                    # 转换工具调用格式
                    for tc in last_message.tool_calls:
                        tool_name = tc.get('name', '') if isinstance(tc, dict) else getattr(tc, 'name', '')
                        tool_args = tc.get('args', {}) if isinstance(tc, dict) else getattr(tc, 'args', {})
                        tool_id = tc.get('id', str(uuid.uuid4())) if isinstance(tc, dict) else getattr(tc, 'id', str(uuid.uuid4()))
                        
                        # 特殊处理gen_notebook
                        if tool_name == 'gen_notebook':
                            base_name = tool_args.get('notebook_name', 'notebook').replace('.ipynb', '')
                            tool_args['notebook_name'] = f"{base_name}_{str(uuid.uuid4()).split('-')[1]}.ipynb"
                            
                            if 'notebook' not in tool_args or tool_args['notebook'] is None:
                                tool_args['notebook'] = json.dumps(notebook_structure, ensure_ascii=False, indent=2)
                        
                        ai_message["tool_calls"].append({
                            "function": {
                                "arguments": tool_args,
                                "name": tool_name
                            },
                            "id": tool_id,
                            "type": "function"
                        })
                else:
                    # 如果没有工具调用，返回普通消息
                    ai_message = extract_ai_message_from_updates(updates)
            else:
                ai_message = extract_ai_message_from_updates(updates)
        else:
            # 正常处理，没有中断
            ai_message = extract_ai_message_from_updates(updates)
        
        print(f"🔍 提取AI消息完成，content长度: {len(ai_message.get('content', ''))}")
        print(f"🔍 工具调用数量: {len(ai_message['tool_calls'])}")

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
            tool_calls=tool_call_objects,
            threadid=request["threadid"]
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