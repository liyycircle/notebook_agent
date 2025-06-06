# !/usr/bin/python
# -*- coding: utf-8 -*-
# @time    : 2025/05/27 11:42
# @author  : Leah
# @function: post service of fastapi

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast, TypedDict, Optional
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from react_agent.configuration import Configuration
from react_agent.state import InputState, MyState
from react_agent.tools import APP_TOOLS
from react_agent.utils import load_chat_model, RequestModel, ResponseModel, ToolResponse
from react_agent.prompts import INTENT_PROMPT, TF_PROMPT, GEN_NOTEBOOK_PROMPT
from langgraph.checkpoint.memory import MemorySaver

import logging
from fastapi import FastAPI, HTTPException

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define the function that calls the model
def pre_node(state: MyState) -> Command[Literal["__end__", "dissect_problem"]]:
    # 路由节点
    if len(state.messages)>2:
        model = load_chat_model('deepseek/deepseek-chat')
        # 处理工具返回
  
        if isinstance(state.messages[-1], ToolMessage):
            if (state.auto_dissect) or (state.messages[-1].status == 'error'):
                logger.info("强制拆解问题")
                return Command(goto="dissect_problem", update = {"auto_dissect":False})
            elif len(state.tool_calls)>0:
                print(state.tool_calls, flush=True)
                logger.info(f"工具调用成功，继续调用{state.tool_calls[0]['name']}")
                return Command(goto="tool_node")
            else:
                logger.info("工具调用成功")
                return Command(
                    goto="__end__", 
                    update={"messages": [AIMessage(content=state.messages[-1].content)]})
        else:
            call_message = f'请结合agent拆解"{state.messages[-2].content}"与用户回答"{state.messages[-1].content}"，判断用户是否同意拆解结果，同意（或是）返回"yes"，否则"no"'
            print(call_message, flush=True)
            response = cast(
                AIMessage,
                model.invoke([
                    {"role": "system", "content": TF_PROMPT},
                    {"role": "system", "content": call_message}]))
            if response.content == "yes":
                logger.info("用户同意开始生成notebook")
                return Command(goto="gen_notebook", update={"intent": state.messages[-2].content})
            else:
                logger.info("用户不同意开始生成notebook，重新拆解问题")
                return Command(goto="dissect_problem")
    else:
        logger.info("开始拆解问题")
        return Command(goto="dissect_problem")


def dissect_problem(state: MyState) -> Command[Literal["__end__"]]:
    model = load_chat_model('deepseek/deepseek-reasoner')
    response = cast(
        AIMessage,
        model.invoke(
            [{"role": "system", "content": INTENT_PROMPT}, *state.messages]
        ),
    )
    return Command(goto="__end__", update={"messages": [response]})

def gen_notebook(state: MyState) -> Dict:
    model = load_chat_model('deepseek/deepseek-coder').bind_tools(APP_TOOLS)  
    # state.intent = state.messages[-1].content # for quick debug
    logger.info(f"按要求生成notebook：{state.intent}")
    response = cast(
        AIMessage,
        model.invoke(
            [{"role": "system", "content": GEN_NOTEBOOK_PROMPT}, 
             {"role": "user", "content": f"按要求生成notebook：{state.intent}"}, *state.messages]
        ),
    )
    if state.is_last_step and response.tool_calls:
        return {
            "tool_calls": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    
    # 确保返回所有工具调用
    # TODO：notebook_name处理
    print('response.tool_calls', response.tool_calls, flush=True)
    if response.tool_calls:
        random_number = str(uuid.uuid4())[-4:]
        response.tool_calls[0]['args']['notebook_name'] += '_'+random_number

    return {
        "tool_calls": response.tool_calls,
        "notebook_name": response.tool_calls[0]['args']['notebook_name']
    }

def tool_node(state: MyState) -> Dict:
    response = state.tool_calls.pop(0) # 删除并返回第一项
    auto_dissect = len(state.tool_calls)==0
    print('待处理 state.tool_calls', state.tool_calls  , '---------')
    
    tool_response = ToolResponse(notebook_name=state.notebook_name)
    output = AIMessage(
        content=getattr(tool_response, response['name']),
        tool_calls=[{
            'id': response['id'],
            'name': response['name'],
            'args': response['args']
        }],
        id=uuid.uuid4())
    return {"messages": [output], "auto_dissect": auto_dissect}

app = FastAPI()
# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)
builder.add_node(pre_node)
builder.add_node(dissect_problem)
builder.add_node(gen_notebook)
builder.add_node(tool_node)

builder.add_edge("__start__", "pre_node")
builder.add_edge("gen_notebook", "tool_node")
builder.add_edge("tool_node", "__end__")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")

@app.post('/app', response_model=ResponseModel)
def run_agent(request_data: RequestModel):
    try:
        logger.info(f"Received request with content: {request_data.content}")
        config = {"configurable": {"thread_id": request_data.threadid}}

        # 检查是否是终止请求
        if request_data.content=='system_stop':
            # 获取当前状态
            current_state = checkpointer.get(config)
            if current_state and isinstance(current_state, list):
                # 只删除最后一个状态
                current_state.pop()
                # 更新状态
                checkpointer.put(config, current_state)
            
            return ResponseModel(
                content="",
                tool_calls=[],
                id=str(uuid.uuid4()),
                type="stop"
            )

        if request_data.role == 'tool':
            request_message = ToolMessage(
                content=request_data.content,
                tool_call_id=request_data.tool_call_id,
                status = request_data.status)
        else:
            request_message = HumanMessage(content=request_data.content)

        result = graph.invoke({"messages": [request_message]}, config)
        logger.info("Successfully processed request")
        return ResponseModel(
            content=result["messages"][-1].content,
            tool_calls=result["messages"][-1].tool_calls,
            id=result["messages"][-1].id,
            type=result["messages"][-1].type
        )

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

if __name__ == '__main__':
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8080,
        workers=1,
        log_level="info"
    )