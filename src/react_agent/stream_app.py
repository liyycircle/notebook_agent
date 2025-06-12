# !/usr/bin/python
# -*- coding: utf-8 -*-
# @time    : 2025/05/27 11:42
# @author  : Leah
# @function: post service of fastapi with streaming support

from typing import Dict, List, Literal, cast, TypedDict, Optional, AsyncGenerator
import uuid
import time
import json
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from react_agent.configuration import Configuration
from react_agent.state import InputState, MyState
from react_agent.tools import APP_TOOLS
from react_agent.utils import load_chat_model, RequestModel, ResponseModel, ToolResponse
from react_agent.prompts import INTENT_PROMPT, GEN_NOTEBOOK_PROMPT
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
def analyze_intent(state: MyState) -> Command[Literal["__end__", "tool_node", "gen_notebook"]]:
    model = load_chat_model('deepseek/deepseek-chat')
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
            logger.info("工具list调用完成")
            return Command(
                goto="__end__", 
                update={"messages": [AIMessage(content=state.messages[-1].content)]})
        else:
            pass
    else:
        logger.info("分析问题")
        response = cast(
            AIMessage,
            model.invoke(
                [{"role": "system", "content": INTENT_PROMPT}, *state.messages]
            ),
        )
        if response.content[0] == "T":
            return Command(goto="gen_notebook", update={"intent": response.content[2:]})
        else:
            return Command(
                goto="__end__", 
                update={"messages": [AIMessage(content=response.content)]})

def gen_notebook(state: MyState) -> Dict:
    model = load_chat_model('deepseek/deepseek-coder').bind_tools(APP_TOOLS)  
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
    print('待处理 state.tool_calls', state.tool_calls  , '---------')
    
    tool_response = ToolResponse(notebook_name=state.notebook_name, summary = state.intent)
    output = AIMessage(
        content=getattr(tool_response, response['name']),
        tool_calls=[{
            'id': response['id'],
            'name': response['name'],
            'args': response['args']
        }],
        id=uuid.uuid4())
    return {"messages": [output]}

app = FastAPI()
# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)
builder.add_node(analyze_intent)
builder.add_node(gen_notebook)
builder.add_node(tool_node)

builder.add_edge("__start__", "analyze_intent")
builder.add_edge("gen_notebook", "tool_node")
builder.add_edge("tool_node", "__end__")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")

async def stream_response(request_data: RequestModel) -> AsyncGenerator[str, None]:
    try:
        logger.info(f"Received request with content: {request_data.content}")
        config = {"configurable": {"thread_id": request_data.threadid}}

        if request_data.content == 'system_stop':
            graph.update_state(config, {'force_stop': True})
            response = ResponseModel(
                content='',
                tool_calls=[],
                id=str(uuid.uuid4()),
                type='stop'
            )
            yield f"data: {json.dumps(response.to_dict())}\n\n"
            return

        if request_data.role == 'tool':
            request_message = ToolMessage(
                content=request_data.content,
                tool_call_id=request_data.tool_call_id,
                status='error' if request_data.status=='failed' else request_data.status)
        else:
            request_message = HumanMessage(content=request_data.content)

        start_time = time.time()
        async for event in graph.astream({"messages": [request_message]}, config):
            for value in event.values():
                if "messages" in value:
                    response = ResponseModel(
                        content=value["messages"][-1].content,
                        tool_calls=value["messages"][-1].tool_calls if hasattr(value["messages"][-1], 'tool_calls') else [],
                        id=value["messages"][-1].id,
                        type=value["messages"][-1].type if hasattr(value["messages"][-1], 'type') else 'ai'
                    )
                    yield f"data: {json.dumps(response.to_dict())}\n\n"

        end_time = time.time()
        logger.info(f"Successfully processed request, time cost: {end_time - start_time} 秒")

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        error_response = ResponseModel(
            content=f"Error: {str(e)}",
            tool_calls=[],
            id=str(uuid.uuid4()),
            type='ai'
        )
        yield f"data: {json.dumps(error_response.to_dict())}\n\n"

@app.post('/app')
async def run_agent(request_data: RequestModel):
    return StreamingResponse(
        stream_response(request_data),
        media_type='text/event-stream'
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