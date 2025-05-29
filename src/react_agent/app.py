# !/usr/bin/python
# -*- coding: utf-8 -*-
# @time    : 2025/05/25 21:27
# @author  : Leah
# @function: post service of fastapi
 
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Literal, cast, AsyncGenerator, Optional
from datetime import UTC, datetime
import uuid
from fastapi.responses import StreamingResponse
import json
import logging
import requests

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from react_agent.prompts import INTENT_PROMPT, GEN_NOTEBOOK_PROMPT
from react_agent.configuration import Configuration 

from react_agent.state import InputState, MyState
from react_agent.tools import TOOLS, PRETOOLS
from react_agent.utils import load_chat_model
from react_agent.router import route_model_output

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_intent(state: MyState) -> Dict[str, List[AIMessage]]:
    configuration = Configuration.from_context()

    # Initialize the model with tool binding. Change the model or add more tools here.
    model = load_chat_model(configuration.model).bind_tools(PRETOOLS)
    system_message = INTENT_PROMPT.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    # Get the model's response
    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "content": system_message}, *state.messages]
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }

    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}

def human_approval(state: MyState) -> Command[Literal["get_intent", "__end__"]]:
    last_message = state.messages[-1]
    decision = interrupt({
        "question": "Do you approve the following output?",
        "intent": last_message
    })

    if decision == "approve":
        return Command(goto="get_intent", update={"decision": "approved"})
    else:
        return Command(goto="__end__", update={"decision": "rejected"})


app = FastAPI()

builder = StateGraph(MyState, input=InputState, config_schema=Configuration)
builder.add_node(get_intent)
# builder.add_node("tools", ToolNode(PRETOOLS))
builder.add_node(human_approval)

builder.add_edge("__start__", "get_intent")
builder.add_edge("get_intent", "human_approval")
# builder.add_edge("get_feedback", "__end__")
# builder.add_conditional_edges("get_intent", route_model_output)
# builder.add_edge("tools", "get_intent")
builder.add_edge("human_approval", "__end__")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")

class RequestModel(BaseModel):
    content: str
    thread_id: int

class ResponseModel(BaseModel):
    model_output: Dict
    status: str = "success"
    error: Optional[str] = None

@app.post('/app', response_model=ResponseModel)
async def run_agent(request_data: RequestModel):
    try:
        logger.info(f"Received request with content: {request_data.content}")
        config = {"configurable": {"thread_id": request_data.thread_id}}
        output = []
        async for event in graph.astream({"messages": [HumanMessage(content=request_data.content)]}, config):
            for value in event.values():
                logger.info(f"Received event: {value}")
                if "messages" in value:
                    print("Assistant:", value["messages"][-1].content)
                    output.extend(value["messages"])
    
        result = await graph.ainvoke(Command(resume=input("请确认提取的意图：")), config=config)
        logger.info("Successfully processed request")
        return ResponseModel(
            model_output={"messages": output},
            status="success"
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