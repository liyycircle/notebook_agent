"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from datetime import UTC, datetime
import asyncio
from typing import Dict, List, Literal, cast
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from react_agent.configuration import Configuration 

from react_agent.state import InputState, MyState
from react_agent.utils import ResponseModel, RequestModel
import logging
from fastapi import FastAPI

logger = logging.getLogger(__name__)
app = FastAPI()

# Define the function that calls the model

def call_model(state: MyState) -> Dict[str, List[AIMessage]]:
    return {"messages": [AIMessage(content="测试", tool_calls=[])]}

def ask_human(state: MyState) -> MyState:   
    last_message = state.messages[-1]
    response = interrupt({
        "question": "若同意生成以上内容，请回答「确认」，否则请提供修正描述",
        "llm_output": last_message
    })
    if response.strip() == "确认":
        return Command(goto="approved_node")
    else:
        return Command(goto="__end__")

def approved_node(state: MyState) -> MyState:
    print("✅ Approved path taken.")
    return state

# Define a new graph
builder = StateGraph(MyState, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node(ask_human)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")
builder.add_edge("call_model", "__end__")


# Compile the builder into an executable graph
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer, name="Notebook Agent")
config = {"configurable": {"thread_id": uuid.uuid4()}}
    
@app.post('/app', response_model=ResponseModel)
def main(request_data: RequestModel):
    config = {"configurable": {"thread_id": request_data.threadid}}
    result = graph.invoke(HumanMessage(content=request_data.content), config)
    return ResponseModel(
        content=result["messages"][-1].content,
        tool_calls=[],
        id=str(uuid.uuid4()),
        type='stop'
)

# 生成针对tmall_order_report.csv的数据分析notebook
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