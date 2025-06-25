# !/usr/bin/python
# -*- coding: utf-8 -*-
# @time    : 2025/05/27 11:42
# @author  : Leah
# @function: post service of fastapi

from typing import Dict, List, Literal, cast, TypedDict, Optional
import uuid
import time
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from project.react_agent.configuration import Configuration
from project.react_agent.state import InputState, MyState
from project.react_agent.tools import APP_TOOLS
from project.react_agent.utils import ConfigSchema, RequestModel, ResponseModel, ToolResponse, ToolMessage
from project.react_agent.utils import load_chat_model
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
def analyze_intent(state: MyState, config) -> Command[Literal["__end__", "tool_node", "gen_notebook"]]:
    logger.info(f'历史消息已产生{len(state.messages)}条，message 长度为{len(str(state.messages))}')
    model = load_chat_model('deepseek/deepseek-chat')
    # 处理工具调用结果
    if isinstance(state.messages[-1], ToolMessage):
        print('state.force_stop', state.force_stop, flush=True)
        # 如果用户要求停止，停止工具list的自动调用
        if state.force_stop:
            return Command(
                goto='__end__', 
                update={"force_stop":False, "messages": [AIMessage(content='')]})
        # 工具链接出错
        if state.messages[-1].code == 400:
            return Command(
                goto='__end__', 
                update={"tool_calls": [], "messages": [AIMessage(content=state.messages[-1].content)]})
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
    message = [{"role": "system", "content": f"你使用的编程语言是{config.get('configurable', {}).get('kernel_language')}"+INTENT_PROMPT}]
    message.extend(state.messages[-min(10, len(state.messages)):])
    response = cast(
        AIMessage,
        model.invoke(message),
    )
    logger.info(f"分析问题结果：{response.content}")
    if response.content[0:2] == "TT":
        return Command(goto="gen_notebook", update={"intent": response.content.split('TT')[-1]})
    else:
        return Command(
            goto="__end__", 
            update={"messages": [AIMessage(content=response.content.split('TT')[0])]}) # 同时与用户 & 编程专家对话时，只保留用户对话

def gen_notebook(state: MyState, config) -> Command[Literal["tool_node"]]:
    model = load_chat_model('deepseek/deepseek-coder').bind_tools(APP_TOOLS)  
    logger.info(f"按要求生成notebook：{state.intent}")
    message = [
        {"role": "system", "content": f"你使用的编程语言是{config.get('configurable', {}).get('kernel_language')}"+GEN_NOTEBOOK_PROMPT},
        {"role": "user", "content": state.intent}]
    message.extend(state.messages[-min(6, len(state.messages)):])
    response = cast(AIMessage, model.invoke(message))
    if not response.tool_calls:
        return Command(goto="gen_notebook")
    else:
        last_tool_call = response.tool_calls[-1]
        if last_tool_call['name'] != 'run_notebook':
            logger.info('未监测到运行工具，添加run_notebook')
            response.tool_calls.append({'id': str(uuid.uuid4()), 'name': 'run_notebook', 'args': {'cells':[]}})
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
    # TODO: remove this node, only for local testing
    # return Command(goto="tools", update={"messages": [output], "tool_calls": state.tool_calls[1:]})
    return Command(goto="__end__", update={"messages": [output], "tool_calls": state.tool_calls[1:]})

app = FastAPI()
# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=ConfigSchema)
builder.add_node(analyze_intent)
builder.add_node(gen_notebook)
builder.add_node(tool_node)

builder.add_edge("__start__", "analyze_intent")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")

# @app.post('/app', response_model=ResponseModel)
def invoke(_input):
    sys.path.append('/home/mw/project')
    request_data = RequestModel(
        content=_input['content'],
        threadid=_input['threadid'],
        role=_input['role'],
        kernel_language=_input['kernel_language'],
        tool_call_id = _input.get('tool_call_id', None),
        references = _input.get('references', []),
        status = _input.get('status', 'success'),
        tool_name = _input.get('tool_name', None)
    )
    request_data.get_valid_nbinfo()

    try:
        logger.info(f"Received request with content: {request_data.content}")
        config = {"configurable": {
            "thread_id": request_data.threadid,
            "kernel_language": request_data.kernel_language}}
        current_state = graph.get_state(config=config)

        # if request_data.content =='system_stop':
        #     graph.update_state({'force_stop': True}, config)
        #     return ResponseModel(threadid = request_data.threadid).stop().to_dict()
        
        # 处理不同的消息类型
        if request_data.role == 'tool':
            # 返回工具时，上一条请求了工具
            if current_state.values['messages'][-1].tool_calls:
                request_message = ToolMessage(
                    content=request_data.content,
                    tool_call_id=request_data.tool_call_id,
                    status = request_data.status)
            # 返回工具时，上一条没请求工具，直接终止
            else:
                logger.warning('agent 没请求工具，但接收到工具型消息！')
                return ResponseModel(threadid = request_data.threadid, stop=True)
        # 普通消息
        else:
            # 正常的消息处理
            request_message = HumanMessage(content=request_data.content)
            # 返回消息，但上一条请求了工具，接上工具链，并覆盖原始请求content
            if current_state.values:
                if current_state.values['messages'][-1].tool_calls:
                    logger.warning('上一条请求了工具，但返回消息型')
                    last_tool_call = current_state.values['messages'][-1].tool_calls
                    request_message = ToolMessage(
                        content='出现了一些意外，重新和我聊聊你的需求吧', 
                        tool_call_id=last_tool_call[0]['id'],
                        status = 'success',
                        code = 400)      

        start_time = time.time()
        result = graph.invoke({"messages": [request_message], "kernel_language": request_data.kernel_language}, config)
        end_time = time.time()
        logger.info(f"Successfully processed request, time cost: {end_time - start_time} 秒")
        return ResponseModel(
            content=result["messages"][-1].content,
            tool_calls=result["messages"][-1].tool_calls,
            id=result["messages"][-1].id,
            type=result["messages"][-1].type,
            threadid = request_data.threadid
        ).to_dict()

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
