# !/usr/bin/python
# -*- coding: utf-8 -*-
# @time    : 2025/05/27 11:42
# @author  : Leah
# @function: post service of fastapi

from datetime import UTC, datetime
from typing import Dict, List, Literal, cast, Optional
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from project.react_agent.configuration import Configuration
from project.react_agent.state import InputState, MyState
from project.react_agent.tools import APP_TOOLS
from project.react_agent.utils import load_chat_model
from project.react_agent.router import route_model_output
from project.react_agent.prompts import INTENT_PROMPT, SYSTEM_PROMPT, GEN_NOTEBOOK_PROMPT
from langgraph.checkpoint.memory import MemorySaver

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define the function that calls the model

def dissect_problem(state: MyState) -> Dict[str, List[AIMessage]]:
    model = load_chat_model('deepseek/deepseek-reasoner')
    response = cast(
        AIMessage,
        model.invoke(
            [{"role": "system", "content": INTENT_PROMPT}, *state.messages]
        ),
    )
    return {"messages": [response]}

def start2gen(state: MyState) -> Command[Literal["__end__", "gen_notebook"]]:
    if len(state.messages) <= 2:
        print('go to end')
        return Command(goto="__end__")
    last_human_message = state.messages[-2].content
    agent_message = state.messages[-3].content
    model = load_chat_model('deepseek/deepseek-chat')
    system_message = SYSTEM_PROMPT.format(system_time=datetime.now(tz=UTC).isoformat())
    response = cast(
        AIMessage,
        model.invoke(
            [{"role": "system", "content": system_message}, 
             {"role": "user", "content": f'请结合agent拆解"{agent_message}"与用户回答"{last_human_message}"，判断用户是否同意开始生成notebook，同意返回"yes"，否则"no"。'}]
        ),
    )
    if response.content == "yes":
        return Command(goto="gen_notebook", update={"intent": state.messages[-1].content})
    else:
        return Command(goto="__end__")
    
def gen_notebook(state: MyState) -> Dict[str, List[AIMessage]]:
    model = load_chat_model('deepseek/deepseek-coder').bind_tools(APP_TOOLS)  
    notebook_name = str(uuid.uuid4())
    print(f"-----------按要求生成notebook：{state.intent}，notebook名称：{notebook_name}-----------")
    response = cast(
        AIMessage,
        model.invoke(
            [{"role": "system", "content": GEN_NOTEBOOK_PROMPT}, 
             {"role": "user", "content": f"按要求生成notebook：{state.intent}，notebook名称：{notebook_name}"}]
        ),
    )
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    return {"messages": [response]}

app = FastAPI()
# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)
builder.add_node(dissect_problem)
builder.add_node(start2gen)
builder.add_node(gen_notebook)
builder.add_node("tools", ToolNode(APP_TOOLS))

builder.add_edge("__start__", "dissect_problem")
builder.add_edge("dissect_problem", "start2gen")
# builder.add_edge("dissect_problem", "gen_notebook")
builder.add_edge("gen_notebook", "__end__")
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")

class RequestModel(BaseModel):
    content: str
    threadid: str

# class ResponseModel(BaseModel):
#     content: str
#     role: str = "assistant"
#     tool_calls: List[Dict]
#     id: str
#     type: Literal["ai", "function"]

# @app.post('/app', response_model=ResponseModel)
def invoke(_input):
    print(_input, flush=True)
    sys.path.append('/home/mw/project')

    try:
        logger.info(f"Received request with content: {_input['content']}")
        config = {"configurable": {"thread_id": _input['threadid']}}
        result = graph.invoke({"messages": [HumanMessage(content=_input['content'])]}, config)
        print(result)
    
        logger.info("Successfully processed request")
        tool_calls = result['messages'][-1].tool_calls
        tools = [i['name'] for i in tool_calls]
        if "gen_notebook" in tools:
            return {
                "content": f'我将为您生成并自动运行notebook {tool_calls[0]["args"]["notebook_name"]}',
                "tool_calls": [
                    {'id': result["messages"][-1].tool_calls[0]['id'], 'function':{'arguments': tool_calls[0]['args'], 'name': 'gen_notebook'},'type': 'function'},
                    {'id': uuid.uuid4(), 'function':{'arguments': {"cells":[]}, 'name': 'run_notebook'},'type': 'function'}
                    ],
                "id": result["messages"][-1].id,
                "type": result["messages"][-1].type
            }
        else:
            return {
                "content": result["messages"][-1].content,
                "role": "assistant",
                "tool_calls": result["messages"][-1].tool_calls,
                "id": result["messages"][-1].id,
                "type": result["messages"][-1].type
            }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
