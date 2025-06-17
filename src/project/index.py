# !/usr/bin/python
# -*- coding: utf-8 -*-
# @time    : 2025/05/27 11:42
# @author  : Leah
# @function: post service of fastapi

from typing import Dict, List, Literal, cast, TypedDict, Optional
import uuid
import time
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from project.react_agent.configuration import Configuration
from project.react_agent.state import InputState, MyState
from project.react_agent.tools import APP_TOOLS
from project.react_agent.utils import load_chat_model, RequestModel, ResponseModel, ToolResponse
from project.react_agent.prompts import INTENT_PROMPT, GEN_NOTEBOOK_PROMPT
from langgraph.checkpoint.memory import MemorySaver

import logging
from fastapi import FastAPI, HTTPException
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define the function that calls the model
def analyze_intent(state: MyState) -> Command[Literal["__end__", "tool_node", "gen_notebook"]]:
    logger.info(f'历史消息已产生{len(state.messages)}条')
    model = load_chat_model('deepseek/deepseek-chat')
    # model = load_chat_model('tongyi/qwen-plus')
    # 处理工具调用结果
    if isinstance(state.messages[-1], ToolMessage):
        print('state.force_stop', state.force_stop, flush=True)
        # 如果用户要求停止，停止工具list的自动调用
        if state.force_stop:
            return Command(
                goto='__end__', 
                update={"force_stop":False, "messages": [AIMessage(content='')]})
        elif (len(state.tool_calls)>0) and (state.messages[-1].status == 'success'):
            logger.info(f"工具调用成功，继续调用{state.tool_calls[0]['name']}")
            return Command(goto="tool_node")
        elif (len(state.tool_calls)==0) and (state.messages[-1].status == 'success'):
            logger.info("运行成功，继续进入intent节点")
        elif (len(state.tool_calls)==0):
            logger.info("运行失败，继续进入intent节点")
        else:
            pass

    logger.info("分析问题")
    message = [{"role": "system", "content": INTENT_PROMPT}]
    message.extend(state.messages[-min(8, len(state.messages)):])
    response = cast(
        AIMessage,
        model.invoke(message),
    )
    if response.content[0] == "T":
        return Command(goto="gen_notebook", update={"intent": response.content.split('TT')[-1]})
    else:
        return Command(
            goto="__end__", 
            update={"messages": [AIMessage(content=response.content)]})

def gen_notebook(state: MyState) -> Command[Literal["tool_node"]]:
    model = load_chat_model('deepseek/deepseek-coder').bind_tools(APP_TOOLS)  
    # model = load_chat_model('tongyi/qwen-plus').bind_tools(APP_TOOLS)  
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
    # if response.tool_calls:
    #     random_number = str(uuid.uuid4())[-4:]
    #     response.tool_calls[0]['args']['notebook_name'] += '_'+random_number
    #     if len(response.tool_calls) == 1:
    #         response.tool_calls.append({'id': str(uuid.uuid4()), 'name': 'run_notebook', 'args': {'cells':[]}})

    return Command(goto="tool_node", update={"tool_calls": response.tool_calls})

def tool_node(state: MyState) -> Command[Literal["__end__"]]:
    response = state.tool_calls[0]
    print('待处理 state.tool_calls', state.tool_calls  , '---------')
    
    tool_response = ToolResponse(summary = state.intent)
    output = AIMessage(
        content=getattr(tool_response, response['name']),
        tool_calls=[{
            'id': response['id'],
            'name': response['name'],
            'args': response['args']
        }],
        id=str(uuid.uuid4()))
    return Command(goto="__end__", update={"messages": [output], "tool_calls": state.tool_calls[1:]})

app = FastAPI()
# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)
builder.add_node(analyze_intent)
builder.add_node(gen_notebook)
builder.add_node(tool_node)

builder.add_edge("__start__", "analyze_intent")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")

# @app.post('/app', response_model=ResponseModel)
def invoke(_input):
    print(_input, flush=True)
    sys.path.append('/home/mw/project')

    try:
        logger.info(f"Received request with content: {_input['content']}")
        config = {"configurable": {"thread_id": _input['threadid']}}

        if _input['content'] =='system_stop':
            graph.update_state({'force_stop': True}, config)
            return ResponseModel(
                content='',
                tool_calls=[],
                id=str(uuid.uuid4()),
                type='stop'
            )

        if _input['role'] == 'tool':
            request_message = ToolMessage(
                content=_input['content'],
                tool_call_id=_input['tool_call_id'],
                status = 'error' if _input['status']=='failed' else _input['status'])
        elif _input['references']:
            request_message = HumanMessage(content=f"{_input['content']}，请参考用户引用{str(_input['references'])}")
        else:
            request_message = HumanMessage(content=_input['content'])
        start_time = time.time()
        result = graph.invoke({"messages": [request_message]}, config)
        end_time = time.time()
        logger.info(f"Successfully processed request, time cost: {end_time - start_time} 秒")
        return ResponseModel(
            content=result["messages"][-1].content,
            tool_calls=result["messages"][-1].tool_calls,
            id=result["messages"][-1].id,
            type=result["messages"][-1].type
        ).to_dict()

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
